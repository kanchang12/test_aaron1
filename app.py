import os
import asyncio
import base64
import json
import uuid
import time
import queue
import threading
import collections
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from twilio.rest import Client
import openai
import audioop # This is a built-in module, no need to pip install
import websockets
import aiohttp # Used by websockets for async HTTP connections

# Import the ElevenLabs Client
from elevenlabs.client import ElevenLabs
from elevenlabs import Voice, VoiceSettings, play

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Configuration ---
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
ELEVENLABS_AGENT_ID = os.environ.get('ELEVENLABS_AGENT_ID')

MONITOR_PHONE_NUMBERS_STR = os.environ.get('MONITOR_PHONE_NUMBERS', '')
MONITOR_PHONE_NUMBERS = [num.strip() for num in MONITOR_PHONE_NUMBERS_STR.split(',') if num.strip()]

ANALYSIS_INTERVAL_SECONDS = int(os.environ.get('ANALYSIS_INTERVAL_SECONDS', 10))
CALL_POLLING_INTERVAL_SECONDS = int(os.environ.get('CALL_POLLING_INTERVAL_SECONDS', 15))

# Secret key for Flask and Flask-SocketIO (essential for sessions and security)
# !!! IMPORTANT: Replace 'your_super_secret_default_key_replace_me_in_prod' with a strong, random key in production !!!
SECRET_KEY = os.environ.get('SECRET_KEY', 'your_super_secret_default_key_replace_me_in_prod')


# --- Input Validation ---
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, OPENAI_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, SECRET_KEY]):
    print("❌ Missing environment variables! Ensure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, OPENAI_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, and SECRET_KEY are set.")
    exit(1)

if not MONITOR_PHONE_NUMBERS:
    print("❌ No phone numbers specified! Add your Twilio numbers to MONITOR_PHONE_NUMBERS environment variable (comma-separated).")
    exit(1)

# --- Initialize Clients ---
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai.api_key = OPENAI_API_KEY
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)


# --- Flask App Setup ---
app = Flask(__name__)

# Configure Flask app with the SECRET_KEY
app.config['SECRET_KEY'] = SECRET_KEY

# Initialize Flask-SocketIO WITHOUT a message queue
# This means it will ONLY work correctly with a single Gunicorn worker.
socketio = SocketIO(
    app,
    cors_allowed_origins="*", # Adjust for production security if needed
    async_mode='threading' # Still good to specify, as you have threads
)

# --- Global Data Stores (In-memory for simplicity) ---
# Note: With multiple workers and no Redis, these in-memory stores would NOT be shared.
# However, since we're forcing a single worker, this is okay.
live_data = {
    'active_calls': {},
    'call_stats': {
        'total_calls': 0,
        'in_progress': 0,
        'completed': 0,
        'analyzed_segments': 0,
        'average_quality_score': 0.0
    }
}

# --- ElevenLabs Conversational AI Stream Manager ---
class ElevenLabsAgentStream:
    def __init__(self, call_sid, elevenlabs_api_key, elevenlabs_agent_id, socketio_ref):
        self.call_sid = call_sid
        self.elevenlabs_api_key = elevenlabs_api_key
        self.elevenlabs_agent_id = elevenlabs_agent_id
        self.socketio = socketio_ref
        self.websocket = None
        self.audio_queue = asyncio.Queue()
        self.stop_event = asyncio.Event()
        self.thread = None
        self.loop = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        print(f"ElevenLabsAgentStream initialized for Call SID: {self.call_sid}")

    async def _connect(self):
        ws_url = f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={self.elevenlabs_agent_id}"
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json" # This header is good for the initial payload
        }
        try:
            # Attempt to establish the WebSocket connection
            self.websocket = await websockets.connect(ws_url, extra_headers=headers)
            print(f"✅ ElevenLabs Agent WebSocket connected for {self.call_sid}")

            # Send the initial configuration message, including the agent_id
            # The agent_id is sent as a parameter in this JSON message, not in the URL path
            await self.websocket.send(json.dumps({
                "api_key": self.elevenlabs_api_key,
                "agent_id": self.elevenlabs_agent_id,
                "text_input_mode": "raw",
                "sample_rate": 8000,
                "can_be_interrupted": True
            }))
            self.reconnect_attempts = 0
            return True # Indicate successful connection and initial setup
        except Exception as e:
            # Handle connection failure
            print(f"❌ Failed to connect ElevenLabs Agent WebSocket for {self.call_sid}: {e}")
            self.websocket = None # Ensure websocket is None on failure
            return False # Indicate connection failure

    async def _send_audio(self):
        while not self.stop_event.is_set():
            try:
                audio_chunk = await self.audio_queue.get()
                if audio_chunk is None: # Sentinel to break loop gracefully
                    break
                if self.websocket and self.websocket.open:
                    audio_payload = base64.b64encode(audio_chunk).decode('utf-8')
                    await self.websocket.send(json.dumps({
                        "audio": audio_payload,
                        "content_type": "audio/pcm",
                        "sample_rate": 8000
                    }))
                else:
                    print(f"WebSocket not open for {self.call_sid}, dropping audio. Attempting reconnect...")
                    if not self.stop_event.is_set() and self.reconnect_attempts < self.max_reconnect_attempts:
                        self.reconnect_attempts += 1
                        print(f"Attempting reconnect for {self.call_sid} (Attempt {self.reconnect_attempts})...")
                        await asyncio.sleep(1)
                        if await self._connect():
                            print(f"Reconnected for {self.call_sid}.")
                        else:
                            print(f"Reconnect failed for {self.call_sid}. Re-queueing audio for next attempt.")
                            # Re-queue the audio if reconnect fails to attempt sending it later
                            await self.audio_queue.put(audio_chunk)
                    else:
                        print(f"Max reconnect attempts reached or stop event set for {self.call_sid}. Discarding audio.")

            except Exception as e:
                print(f"❌ Error sending audio to ElevenLabs for {self.call_sid}: {e}")
                await asyncio.sleep(0.1) # Small delay to prevent tight loop on error

    async def _receive_events(self):
        while not self.stop_event.is_set():
            try:
                if self.websocket:
                    message = await self.websocket.recv()
                    event = json.loads(message)

                    if event['type'] == 'user_transcript':
                        transcript_chunk = event['text']
                        if transcript_chunk.strip():
                            print(f"📝 ElevenLabs Transcript ({self.call_sid}): {transcript_chunk}")
                            call_data = live_data['active_calls'].get(self.call_sid)
                            if call_data:
                                call_data['transcripts'].append(transcript_chunk)
                                # Pass full transcript history for context
                                analysis_result = analyze_agent_response(transcript_chunk, call_data['transcripts'])
                                call_data['analysis'].append(analysis_result)
                                live_data['call_stats']['analyzed_segments'] += 1

                                if analysis_result and analysis_result.get('overall_score') is not None:
                                    if live_data['call_stats']['analyzed_segments'] > 0:
                                        current_total = live_data['call_stats']['average_quality_score'] * (live_data['call_stats']['analyzed_segments'] - 1)
                                        live_data['call_stats']['average_quality_score'] = \
                                            (current_total + analysis_result['overall_score']) / live_data['call_stats']['analyzed_segments']
                                    else:
                                        live_data['call_stats']['average_quality_score'] = analysis_result['overall_score']

                                self.socketio.emit('live_analysis', {
                                    'call_sid': self.call_sid,
                                    'transcript_chunk': transcript_chunk,
                                    'analysis_result': analysis_result,
                                    'timestamp': datetime.now().strftime("%H:%M:%S")
                                })
                    elif event['type'] == 'agent_output':
                        # Handle agent audio output here if needed, e.g., send to Twilio
                        pass
                    elif event['type'] == 'pong':
                        # Handle pong messages to keep connection alive if necessary
                        pass
                    else:
                        print(f"ElevenLabs Agent Event ({self.call_sid}): {event['type']} - {event}")

                else:
                    await asyncio.sleep(0.1) # Small delay if WebSocket is not yet connected

            except websockets.exceptions.ConnectionClosedOK:
                print(f"ElevenLabs Agent WebSocket for {self.call_sid} closed gracefully.")
                if not self.stop_event.is_set() and self.reconnect_attempts < self.max_reconnect_attempts:
                    self.reconnect_attempts += 1
                    print(f"Attempting reconnect for {self.call_sid} (Attempt {self.reconnect_attempts})...")
                    await asyncio.sleep(1)
                    if await self._connect():
                        print(f"Reconnected for {self.call_sid}.")
                else:
                    self.stop_event.set() # Stop if max reconnects reached or explicitly stopped
            except Exception as e:
                print(f"❌ Error receiving from ElevenLabs for {self.call_sid}: {e}")
                if not self.stop_event.is_set() and self.reconnect_attempts < self.max_reconnect_attempts:
                    self.reconnect_attempts += 1
                    print(f"Attempting reconnect for {self.call_sid} (Attempt {self.reconnect_attempts})...")
                    await asyncio.sleep(1)
                    if await self._connect():
                        print(f"Reconnected for {self.call_sid}.")
                else:
                    self.stop_event.set() # Stop if max reconnects reached or explicitly stopped
                await asyncio.sleep(0.1) # Small delay to prevent tight loop on error

    async def _run(self):
        connected = await self._connect()
        if not connected:
            print(f"Could not establish initial connection for {self.call_sid}. Stopping stream.")
            return

        # Run send and receive tasks concurrently
        await asyncio.gather(
            self._send_audio(),
            self._receive_events(),
            return_exceptions=False # Allows handling exceptions within each coroutine
        )
        print(f"ElevenLabs Agent Stream finished for {self.call_sid}")

    def start(self):
        # Start the asyncio event loop in a new thread
        self.thread = threading.Thread(target=self._run_async_in_thread, daemon=True)
        self.thread.start()

    def _run_async_in_thread(self):
        # Each thread needs its own asyncio event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run())
        self.loop.close()
        print(f"Async loop closed for ElevenLabsAgentStream for {self.call_sid}")

    async def _async_stop(self):
        # Set stop event to signal coroutines to exit
        self.stop_event.set()
        await self.audio_queue.put(None) # Put sentinel to unblock _send_audio
        if self.websocket and self.websocket.open:
            await self.websocket.close() # Close the WebSocket connection
            print(f"ElevenLabs Agent WebSocket for {self.call_sid} closed.")

    def stop(self):
        # Schedule the async stop method to run in the stream's event loop
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._async_stop(), self.loop)
        else:
            print(f"ElevenLabsAgentStream for {self.call_sid} is not running, no explicit stop needed.")

    def send_audio(self, audio_chunk_pcm):
        # Add audio chunk to the queue from a different thread (e.g., Flask request handler)
        if self.loop and self.loop.is_running() and not self.stop_event.is_set():
            try:
                asyncio.run_coroutine_threadsafe(self.audio_queue.put(audio_chunk_pcm), self.loop)
            except Exception as e:
                print(f"Error putting audio into queue for {self.call_sid}: {e}")
        else:
            print(f"Error: ElevenLabs Agent Stream for {self.call_sid} is not running or stopped. Audio dropped.")


# --- Background Call Monitoring Thread ---
class LiveCallMonitor:
    def __init__(self):
        self.polling_thread = None
        self.stop_event = threading.Event()

    def start_polling(self):
        if self.polling_thread is None or not self.polling_thread.is_alive():
            self.stop_event.clear()
            self.polling_thread = threading.Thread(target=self._poll_calls_loop)
            self.polling_thread.daemon = True
            self.polling_thread.start()
            print("📞 Started Twilio call polling thread.")
        else:
            print("📞 Twilio call polling thread already running.")

    def stop_polling(self):
        self.stop_event.set()
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=5)
            print("📞 Stopped Twilio call polling thread.")

    def _poll_calls_loop(self):
        while not self.stop_event.is_set():
            self.poll_active_calls()
            time.sleep(CALL_POLLING_INTERVAL_SECONDS)

    def poll_active_calls(self):
        try:
            current_call_sids = set()
            for phone_number in MONITOR_PHONE_NUMBERS:
                calls_to = twilio_client.calls.list(
                    to=phone_number,
                    status='in-progress',
                    limit=20
                )
                calls_from = twilio_client.calls.list(
                    from_=phone_number,
                    status='in-progress',
                    limit=20
                )
                all_calls = calls_to + calls_from

                for call in all_calls:
                    call_sid = call.sid
                    current_call_sids.add(call_sid)
                    if call_sid not in live_data['active_calls']:
                        self.handle_new_call(call)
                    else:
                        self.update_call_status(call_sid, call)

            ended_calls = set(live_data['active_calls'].keys()) - current_call_sids
            for call_sid in ended_calls:
                self.handle_call_end(call_sid)

        except Exception as e:
            print(f"❌ Error polling calls: {e}")

    def handle_new_call(self, call_obj):
        call_sid = call_obj.sid
        if call_sid in live_data['active_calls']:
            return

        print(f"🎉 New call detected: {call_sid} from {call_obj.from_formatted} to {call_obj.to_formatted}")

        elevenlabs_agent_stream = ElevenLabsAgentStream(
            call_sid=call_sid,
            elevenlabs_api_key=ELEVENLABS_API_KEY,
            elevenlabs_agent_id=ELEVENLABS_AGENT_ID,
            socketio_ref=socketio
        )
        elevenlabs_agent_stream.start()

        live_data['active_calls'][call_sid] = {
            'number': call_obj.from_formatted,
            'to_number': call_obj.to_formatted,
            'start_time': datetime.now(),
            'duration': '00:00',
            'status': call_obj.status,
            'transcripts': [],
            'analysis': [],
            'elevenlabs_agent_stream': elevenlabs_agent_stream
        }
        live_data['call_stats']['total_calls'] += 1
        live_data['call_stats']['in_progress'] += 1
        
        socketio.emit('call_started', {
            'call_sid': call_sid,
            'number': call_obj.from_formatted,
            'to_number': call_obj.to_formatted,
            'start_time': live_data['active_calls'][call_sid]['start_time'].strftime("%Y-%m-%d %H:%M:%S")
        })

    def update_call_status(self, call_sid, twilio_call_object):
        if call_sid in live_data['active_calls']:
            call_data = live_data['active_calls'][call_sid]
            call_data['status'] = twilio_call_object.status
            duration_td = datetime.now() - call_data['start_time']
            call_data['duration'] = str(duration_td).split('.')[0]

    def handle_call_end(self, call_sid):
        if call_sid in live_data['active_calls']:
            call_data = live_data['active_calls'].pop(call_sid)
            print(f"👋 Call ended: {call_sid} (Duration: {call_data['duration']})")
            live_data['call_stats']['in_progress'] = max(0, live_data['call_stats']['in_progress'] - 1)
            live_data['call_stats']['completed'] += 1

            elevenlabs_stream = call_data.get('elevenlabs_agent_stream')
            if elevenlabs_stream:
                elevenlabs_stream.stop()

            socketio.emit('call_ended', {
                'call_sid': call_sid,
                'duration': call_data['duration'],
                'final_transcripts': call_data['transcripts'],
                'final_analysis': call_data['analysis']
            })

call_monitor = LiveCallMonitor()


# --- OpenAI Analysis Function ---
def analyze_agent_response(transcript_chunk, full_transcript_history):
    try:
        context_transcript = " ".join(full_transcript_history[-5:])

        prompt = f"""
        Analyze the *latest agent response* from the following conversation for quality metrics.
        The full conversation context is: "{context_transcript}"

        Latest Agent Response: "{transcript_chunk}"

        Rate each factor from 1-10 (1 being poor, 10 being excellent) and provide short strengths/improvements.
        Return ONLY valid JSON.
        Factors to rate: politeness, objection_handling, product_knowledge, customer_happiness, communication_clarity, problem_resolution, listening_skills, empathy.

        Example JSON structure:
        {{
            "politeness": 8,
            "objection_handling": 7,
            "product_knowledge": 8,
            "customer_happiness": 7,
            "communication_clarity": 9,
            "problem_resolution": 6,
            "listening_skills": 8,
            "empathy": 7,
            "overall_score": 8,
            "strengths": ["clear communication"],
            "improvements": ["more empathy"],
            "sentiment": "positive"
        }}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )

        result = json.loads(response.choices[0].message.content)
        return result

    except json.JSONDecodeError as e:
        print(f"❌ OpenAI analysis JSON decode error: {e}. Raw response: {response.choices[0].message.content}")
        return {'error': 'JSON Decode Error', 'message': str(e), 'overall_score': 0, 'sentiment': 'neutral'}
    except Exception as e:
        print(f"❌ OpenAI analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'politeness': 5, 'objection_handling': 5, 'product_knowledge': 5,
            'customer_happiness': 5, 'communication_clarity': 5,
            'problem_resolution': 5, 'listening_skills': 5, 'empathy': 5,
            'overall_score': 5, 'strengths': ['Error during analysis'], 'improvements': [], 'sentiment': 'neutral'
        }


# --- Flask Routes ---
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'twilio_polling_active': call_monitor.polling_thread and call_monitor.polling_thread.is_alive(),
        'active_calls_count': len(live_data['active_calls']),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/stats')
def get_stats():
    return jsonify({
        'total_calls': live_data['call_stats']['total_calls'],
        'in_progress': live_data['call_stats']['in_progress'],
        'completed': live_data['call_stats']['completed'],
        'analyzed_segments': live_data['call_stats']['analyzed_segments'],
        'average_quality_score': round(live_data['call_stats']['average_quality_score'], 1) if live_data['call_stats']['analyzed_segments'] > 0 else 0.0,
        'agents_count': len(set(call['to_number'] for call in live_data['active_calls'].values()))
    })

@app.route('/test-twilio', methods=['GET'])
def test_twilio():
    try:
        account = twilio_client.api.accounts(TWILIO_ACCOUNT_SID).fetch()
        recent_calls = twilio_client.calls.list(limit=5)
        call_info = [{
            'sid': call.sid, 'from': call.from_, 'to': call.to,
            'status': call.status, 'start_time': str(call.start_time), 'direction': call.direction
        } for call in recent_calls]
        return jsonify({
            'status': 'success', 'account_name': account.friendly_name,
            'monitored_numbers': MONITOR_PHONE_NUMBERS, 'recent_calls': call_info
        })
    except Exception as e:
        print(f"❌ Twilio connection failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/simulate-call', methods=['POST'])
def simulate_call():
    try:
        fake_call_sid = f"fake_call_{int(time.time())}"
        fake_from = "+15551234567"
        fake_to = MONITOR_PHONE_NUMBERS[0] if MONITOR_PHONE_NUMBERS else "+15559876543"

        live_data['active_calls'][fake_call_sid] = {
            'number': fake_from,
            'to_number': fake_to,
            'start_time': datetime.now(),
            'duration': '00:00',
            'status': 'in-progress',
            'transcripts': [],
            'analysis': [],
            'elevenlabs_agent_stream': None
        }
        live_data['call_stats']['total_calls'] += 1
        live_data['call_stats']['in_progress'] += 1

        print(f"🎭 SIMULATED CALL: {fake_call_sid} from {fake_from} to {fake_to}")

        socketio.emit('call_started', {
            'call_sid': fake_call_sid,
            'number': fake_from,
            'to_number': fake_to,
            'start_time': live_data['active_calls'][fake_call_sid]['start_time'].strftime("%Y-%m-%d %H:%M:%S")
        })

        def generate_fake_transcript_and_analysis():
            time.sleep(3)
            fake_segments = [
                "Hello, thank you for calling. How may I assist you today?",
                "I understand you're having an issue with your internet connection. Let me check that for you.",
                "Yes, I can confirm that. We'll need to reset your router. Can you do that for me now?",
                "Excellent. Please wait a moment while it reboots.",
                "Great! Is there anything else I can help you with today?"
            ]
            for i, segment in enumerate(fake_segments):
                if fake_call_sid not in live_data['active_calls']:
                    break

                call_data = live_data['active_calls'].get(fake_call_sid)
                if call_data:
                    call_data['transcripts'].append(segment)
                    analysis_result = analyze_agent_response(segment, call_data['transcripts'])
                    call_data['analysis'].append(analysis_result)
                    live_data['call_stats']['analyzed_segments'] += 1

                    if analysis_result and analysis_result.get('overall_score') is not None:
                        if live_data['call_stats']['analyzed_segments'] > 0:
                            current_total = live_data['call_stats']['average_quality_score'] * (live_data['call_stats']['analyzed_segments'] - 1)
                            live_data['call_stats']['average_quality_score'] = \
                                (current_total + analysis_result['overall_score']) / live_data['call_stats']['analyzed_segments']
                        else:
                            live_data['call_stats']['average_quality_score'] = analysis_result['overall_score']


                    socketio.emit('live_analysis', {
                        'call_sid': fake_call_sid,
                        'transcript_chunk': segment,
                        'analysis_result': analysis_result,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    })
                time.sleep(5)

            time.sleep(5)
            if fake_call_sid in live_data['active_calls']:
                call_monitor.handle_call_end(fake_call_sid)

        threading.Thread(target=generate_fake_transcript_and_analysis, daemon=True).start()

        return jsonify({'status': 'success', 'call_sid': fake_call_sid})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/call-start', methods=['POST'])
def twilio_call_start():
    from twilio.twiml.voice_response import VoiceResponse

    call_sid = request.form.get('CallSid')
    from_number = request.form.get('From')
    to_number = request.form.get('To')

    print(f"🔔 Twilio webhook: Call {call_sid} from {from_number} to {to_number}")

    call_obj = twilio_client.calls(call_sid).fetch()
    call_monitor.handle_new_call(call_obj)

    response = VoiceResponse()
    stream_url = f'wss://{request.host}/audio-stream/{call_sid}'
    response.start().stream(
        url=stream_url,
        track='both_tracks'
    )
    response.dial(to_number)

    return str(response)

@app.route('/webhook/call-end', methods=['POST'])
def twilio_call_end():
    call_sid = request.form.get('CallSid')
    print(f"🔚 Call ended webhook received for: {call_sid}")
    call_monitor.handle_call_end(call_sid)
    return '', 200

# --- Flask-SocketIO Event Handlers for Twilio Media Stream ---
@socketio.on('connect', namespace='/audio-stream')
def handle_audio_stream_connect():
    print(f"🎧 Twilio Media Stream WebSocket connected.")

@socketio.on('message', namespace='/audio-stream')
def handle_media_stream_message(message):
    try:
        payload = message

        event_type = payload.get('event')
        call_sid = payload.get('call_sid')

        if event_type == 'start':
            print(f"Twilio Media Stream 'start' event for CallSid: {call_sid}")
            if call_sid not in live_data['active_calls']:
                call_obj = twilio_client.calls(call_sid).fetch()
                call_monitor.handle_new_call(call_obj)
        elif event_type == 'media':
            audio_payload = payload['media']['payload']

            if call_sid and call_sid in live_data['active_calls']:
                call_data = live_data['active_calls'][call_sid]
                elevenlabs_stream = call_data.get('elevenlabs_agent_stream')

                if elevenlabs_stream:
                    audio_data_mulaw = base64.b64decode(audio_payload)
                    pcm_audio = audioop.ulaw2lin(audio_data_mulaw, 2)

                    elevenlabs_stream.send_audio(pcm_audio)
                else:
                    print(f"No ElevenLabs Agent Stream found for Call SID {call_sid}. Audio dropped.")
            else:
                print(f"Media received for unknown or ended Call SID: {call_sid}. Audio dropped.")

        elif event_type == 'stop':
            print(f"Twilio Media Stream 'stop' event for CallSid: {call_sid}")
            call_monitor.handle_call_end(call_sid)

    except Exception as e:
        print(f"❌ Error handling Twilio Media Stream message: {e}")
        import traceback
        traceback.print_exc()

@socketio.on('disconnect', namespace='/audio-stream')
def handle_audio_stream_disconnect():
    print("🎧 Twilio Media Stream WebSocket disconnected.")


# --- Flask-SocketIO Event Handlers for Dashboard Frontend ---
@socketio.on('connect')
def handle_dashboard_connect():
    print("🌐 Dashboard client connected via WebSocket.")
    emit('connected', {'status': 'Connected to live call monitoring system!'})
    handle_get_live_data()

@socketio.on('get_live_data')
def handle_get_live_data():
    active_calls_data = []

    for call_sid, call_info in live_data['active_calls'].items():
        active_calls_data.append({
            'call_sid': call_sid,
            'from': call_info['number'],
            'to': call_info['to_number'],
            'duration': call_info['duration'],
            'status': call_info['status'],
            'latest_transcript': call_info['transcripts'][-1] if call_info['transcripts'] else '',
            'latest_analysis': call_info['analysis'][-1] if call_info['analysis'] else {},
            'overall_score': call_info['analysis'][-1].get('overall_score', 0) if call_info['analysis'] else 0
        })

    emit('live_data_update', {
        'active_calls': active_calls_data,
        'total_calls': live_data['call_stats']['total_calls'],
        'in_progress_calls': live_data['call_stats']['in_progress'],
        'completed_calls': live_data['call_stats']['completed'],
        'average_overall_quality': round(live_data['call_stats']['average_quality_score'], 1)
    })


# --- Application Entry Point ---
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎧 Live Call Quality Monitoring System with ElevenLabs Conversational AI")
    print("📊 Quality Factors: Politeness, Objection Handling, Knowledge, Customer Happiness")
    print("🔧 Using Environment Variables for API Keys")
    print(f"📞 Monitoring Phone Numbers: {', '.join(MONITOR_PHONE_NUMBERS)}")
    print("🌐 Dashboard: http://localhost:5000")
    print("🧪 Test Twilio: http://localhost:5000/test-twilio")
    print("🎭 Simulate Call: Click 'Simulate Call' button on dashboard (simulates analysis, not ElevenLabs agent)")
    print("▶️  Starting Twilio call polling automatically...")
    print("="*50 + "\n")

    call_monitor.start_polling()

    socketio.run(app, debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), allow_unsafe_werkzeug=True)

# Gunicorn entry point (used by Koyeb)
# WARNING: This setup will only work correctly with a SINGLE Gunicorn worker.
# If Gunicorn is configured with multiple workers (default for some platforms),
# real-time updates and inter-call communication via WebSockets will be unreliable.
# For multi-worker setups, a message queue like Redis IS REQUIRED for Flask-SocketIO.
