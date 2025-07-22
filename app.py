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
import audioop
import websockets
import aiohttp # For async HTTP client in websockets

# Import the ElevenLabs Client
from elevenlabs.client import ElevenLabs
from elevenlabs import Voice, VoiceSettings, play

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
ELEVENLABS_AGENT_ID = os.environ.get('ELEVENLABS_AGENT_ID') # Crucial for Conversational AI

MONITOR_PHONE_NUMBERS_STR = os.environ.get('MONITOR_PHONE_NUMBERS', '')
MONITOR_PHONE_NUMBERS = [num.strip() for num in MONITOR_PHONE_NUMBERS_STR.split(',') if num.strip()]

ANALYSIS_INTERVAL_SECONDS = int(os.environ.get('ANALYSIS_INTERVAL_SECONDS', 10))
CALL_POLLING_INTERVAL_SECONDS = int(os.environ.get('CALL_POLLING_INTERVAL_SECONDS', 15))


# --- Input Validation ---
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, OPENAI_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID]):
    print("❌ Missing environment variables! Ensure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, OPENAI_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID are set.")
    exit(1)

if not MONITOR_PHONE_NUMBERS:
    print("❌ No phone numbers specified! Add your Twilio numbers to MONITOR_PHONE_NUMBERS environment variable (comma-separated).")
    exit(1)

# --- Initialize Clients ---
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai.api_key = OPENAI_API_KEY
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
app.config['REDIS_URL'] = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# --- Flask App Setup ---
app = Flask(__name__)
# Use 'threading' async_mode for simplicity when integrating with a separate asyncio thread
# For pure async (eventlet/gevent), you'd need to adapt the ElevenLabsAgentStream more carefully.
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading', # Keep this as you're using threads
    message_queue=REDIS_URL # <--- ADD THIS LINE
)

# --- Global Data Stores (In-memory for simplicity, consider Redis for production) ---
live_data = {
    'active_calls': {},  # call_sid: { 'number': ..., 'start_time': ..., 'duration': ..., 'transcripts': [], 'analysis': [], 'elevenlabs_agent_stream': ElevenLabsAgentStreamInstance }
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
        ws_url = f"wss://api.elevenlabs.io/v1/conversational-ai-stream/{self.elevenlabs_agent_id}"
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        try:
            self.websocket = await websockets.connect(ws_url, extra_headers=headers)
            print(f"✅ ElevenLabs Agent WebSocket connected for {self.call_sid}")

            # Send initial configuration message
            await self.websocket.send(json.dumps({
                "api_key": self.elevenlabs_api_key, # Redundant if in header, but good to be explicit
                "agent_id": self.elevenlabs_agent_id,
                "text_input_mode": "raw", # We will send audio directly, not text
                "sample_rate": 8000, # Twilio's media stream sample rate
                "can_be_interrupted": True # Allow agent to be interrupted
            }))
            self.reconnect_attempts = 0 # Reset on successful connection
            return True
        except Exception as e:
            print(f"❌ Failed to connect ElevenLabs Agent WebSocket for {self.call_sid}: {e}")
            self.websocket = None
            return False

    async def _send_audio(self):
        while not self.stop_event.is_set():
            try:
                audio_chunk = await self.audio_queue.get()
                if audio_chunk is None: # Sentinel
                    break
                if self.websocket and self.websocket.open:
                    # ElevenLabs expects audio in a specific format (e.g., 16-bit PCM).
                    # The `audio_chunk` passed here should already be 16-bit PCM.
                    audio_payload = base64.b64encode(audio_chunk).decode('utf-8')
                    await self.websocket.send(json.dumps({
                        "audio": audio_payload,
                        "content_type": "audio/pcm",
                        "sample_rate": 8000
                    }))
                else:
                    print(f"WebSocket not open for {self.call_sid}, dropping audio.")
                    # Try to reconnect if not explicitly stopped
                    if not self.stop_event.is_set() and self.reconnect_attempts < self.max_reconnect_attempts:
                        self.reconnect_attempts += 1
                        print(f"Attempting reconnect for {self.call_sid} (Attempt {self.reconnect_attempts})...")
                        await asyncio.sleep(1) # Small delay before reconnect
                        if await self._connect():
                             print(f"Reconnected for {self.call_sid}.")
                        else:
                             print(f"Reconnect failed for {self.call_sid}. Queueing audio for next attempt.")
                             # Re-add chunk to queue if reconnect failed to prevent loss
                             await self.audio_queue.put(audio_chunk) # Put it back
                    else:
                        print(f"Max reconnect attempts reached or stopped for {self.call_sid}. Discarding audio.")

            except Exception as e:
                print(f"❌ Error sending audio to ElevenLabs for {self.call_sid}: {e}")
                # Consider what to do with the audio chunk on error (requeue, discard)
                await asyncio.sleep(0.1) # Prevent busy loop on error

    async def _receive_events(self):
        while not self.stop_event.is_set():
            try:
                if self.websocket:
                    message = await self.websocket.recv()
                    event = json.loads(message)

                    if event['type'] == 'user_transcript':
                        transcript_chunk = event['text']
                        if transcript_chunk.strip(): # Only process non-empty transcripts
                            print(f"📝 ElevenLabs Transcript ({self.call_sid}): {transcript_chunk}")
                            call_data = live_data['active_calls'].get(self.call_sid)
                            if call_data:
                                call_data['transcripts'].append(transcript_chunk)
                                # Trigger analysis on this new transcript chunk
                                analysis_result = analyze_agent_response(transcript_chunk, call_data['transcripts'])
                                call_data['analysis'].append(analysis_result)
                                live_data['call_stats']['analyzed_segments'] += 1

                                if analysis_result and analysis_result.get('overall_score') is not None:
                                    # Update average quality score (simple rolling average for demonstration)
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
                        # This is the agent's response, often TTS or text. You might want to display this too.
                        print(f"🗣️ ElevenLabs Agent Output ({self.call_sid}): {event.get('text', '[audio]')}")
                        # You could emit this as well if your dashboard shows agent responses.
                    elif event['type'] == 'pong':
                        # Keep-alive signal, can be ignored or used for monitoring
                        pass
                    else:
                        print(f"ElevenLabs Agent Event ({self.call_sid}): {event['type']} - {event}")

                else: # WebSocket not connected
                    await asyncio.sleep(0.1) # Wait a bit before checking again

            except websockets.exceptions.ConnectionClosedOK:
                print(f"ElevenLabs Agent WebSocket for {self.call_sid} closed gracefully.")
                # Attempt to reconnect if not explicitly stopped
                if not self.stop_event.is_set() and self.reconnect_attempts < self.max_reconnect_attempts:
                    self.reconnect_attempts += 1
                    print(f"Attempting reconnect for {self.call_sid} (Attempt {self.reconnect_attempts})...")
                    await asyncio.sleep(1)
                    if await self._connect():
                        print(f"Reconnected for {self.call_sid}.")
                else:
                    self.stop_event.set() # Stop if max reconnects hit
            except Exception as e:
                print(f"❌ Error receiving from ElevenLabs for {self.call_sid}: {e}")
                if not self.stop_event.is_set() and self.reconnect_attempts < self.max_reconnect_attempts:
                    self.reconnect_attempts += 1
                    print(f"Attempting reconnect for {self.call_sid} (Attempt {self.reconnect_attempts})...")
                    await asyncio.sleep(1)
                    if await self._connect():
                        print(f"Reconnected for {self.call_sid}.")
                else:
                    self.stop_event.set() # Stop if max reconnects hit
                await asyncio.sleep(0.1) # Prevent busy loop on error

    async def _run(self):
        connected = await self._connect()
        if not connected:
            print(f"Could not establish initial connection for {self.call_sid}. Stopping stream.")
            return

        # Run send and receive concurrently
        await asyncio.gather(
            self._send_audio(),
            self._receive_events(),
            return_exceptions=False # Propagate exceptions immediately
        )
        print(f"ElevenLabs Agent Stream finished for {self.call_sid}")

    def start(self):
        self.thread = threading.Thread(target=self._run_async_in_thread, daemon=True)
        self.thread.start()

    def _run_async_in_thread(self):
        # Create a new event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run())
        self.loop.close()
        print(f"Async loop closed for ElevenLabsAgentStream for {self.call_sid}")


    async def stop(self):
        self.stop_event.set()
        await self.audio_queue.put(None) # Send sentinel to stop audio sender
        if self.websocket and self.websocket.open:
            await self.websocket.close()
            print(f"ElevenLabs Agent WebSocket for {self.call_sid} closed.")
        # if self.loop and self.loop.is_running(): # this can cause issues if not graceful
        #     self.loop.stop() # Attempt to stop the loop
        #     print(f"Async loop attempted to stop for {self.call_sid}")


    def send_audio(self, audio_chunk_pcm):
        """Puts a PCM audio chunk into the queue for sending."""
        # This is called from the Flask/Twilio media stream thread
        # Need to ensure this is thread-safe with the asyncio loop
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.audio_queue.put(audio_chunk_pcm), self.loop)
        else:
            print(f"Error: ElevenLabs Agent Stream for {self.call_sid} is not running. Audio dropped.")

# --- Background Call Monitoring Thread ---
class LiveCallMonitor:
    def __init__(self):
        self.polling_thread = None
        self.stop_event = threading.Event()

    def start_polling(self):
        if self.polling_thread is None or not self.polling_thread.is_alive():
            self.stop_event.clear()
            self.polling_thread = threading.Thread(target=self._poll_calls_loop)
            self.polling_thread.daemon = True # Allow program to exit even if thread is running
            self.polling_thread.start()
            print("📞 Started Twilio call polling thread.")

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
        """Poll Twilio for active calls ONLY on specified numbers"""
        try:
            current_call_sids = set()
            # print(f"🔍 Polling for active calls on {len(MONITOR_PHONE_NUMBERS)} numbers...")
            for phone_number in MONITOR_PHONE_NUMBERS:
                # Check calls TO this number
                calls_to = twilio_client.calls.list(
                    to=phone_number,
                    status='in-progress',
                    limit=5
                )
                # Check calls FROM this number
                calls_from = twilio_client.calls.list(
                    from_=phone_number,
                    status='in-progress',
                    limit=5
                )
                all_calls = calls_to + calls_from

                for call in all_calls:
                    call_sid = call.sid
                    current_call_sids.add(call_sid)
                    if call_sid not in live_data['active_calls']:
                        self.handle_new_call(call, phone_number)
                    else:
                        self.update_call(call_sid, call)

            ended_calls = set(live_data['active_calls'].keys()) - current_call_sids
            for call_sid in ended_calls:
                self.handle_call_end(call_sid)

        except Exception as e:
            print(f"❌ Error polling calls: {e}")

    def handle_new_call(self, call, phone_number):
        """Handles a newly detected active call."""
        print(f"🎉 New call detected: {call.sid} from {call.from_formatted} to {call.to_formatted}")
        live_data['active_calls'][call.sid] = {
            'number': call.from_formatted,
            'to_number': call.to_formatted,
            'start_time': datetime.now(),
            'duration': '00:00',
            'status': call.status,
            'transcripts': [],
            'analysis': []
        }
        live_data['call_stats']['total_calls'] += 1
        live_data['call_stats']['in_progress'] += 1
        socketio.emit('call_started', {
            'call_sid': call.sid,
            'number': call.from_formatted,
            'to_number': call.to_formatted,
            'start_time': live_data['active_calls'][call.sid]['start_time'].strftime("%Y-%m-%d %H:%M:%S")
        })

    def update_call(self, call_sid, twilio_call_object):
        """Updates an existing call's status and duration."""
        if call_sid in live_data['active_calls']:
            call_data = live_data['active_calls'][call_sid]
            call_data['status'] = twilio_call_object.status
            duration_td = datetime.now() - call_data['start_time']
            call_data['duration'] = str(duration_td).split('.')[0] # Format to HH:MM:SS

    def handle_call_end(self, call_sid):
        """Handles an ended call."""
        if call_sid in live_data['active_calls']:
            call_data = live_data['active_calls'].pop(call_sid)
            print(f"👋 Call ended: {call_sid} (Duration: {call_data['duration']})")
            live_data['call_stats']['in_progress'] = max(0, live_data['call_stats']['in_progress'] - 1)
            live_data['call_stats']['completed'] += 1

            # Stop the ElevenLabs Agent stream if it exists for this call
            elevenlabs_stream = call_data.get('elevenlabs_agent_stream')
            if elevenlabs_stream:
                # Need to run stop coroutine in its thread's loop
                if elevenlabs_stream.loop and elevenlabs_stream.loop.is_running():
                    asyncio.run_coroutine_threadsafe(elevenlabs_stream.stop(), elevenlabs_stream.loop)
                    # Optionally wait for thread to finish if not daemonized, but daemon is fine here.
                else:
                    print(f"ElevenLabsAgentStream for {call_sid} not running, no explicit stop needed.")


            socketio.emit('call_ended', {
                'call_sid': call_sid,
                'duration': call_data['duration'],
                'final_transcripts': call_data['transcripts'],
                'final_analysis': call_data['analysis']
            })

call_monitor = LiveCallMonitor()


# --- OpenAI Analysis Function ---
def analyze_agent_response(transcript_chunk, full_transcript_history):
    """Analyze agent response with OpenAI"""
    try:
        # Use the full transcript history for better context, but primarily analyze the latest chunk
        context_transcript = " ".join(full_transcript_history[-3:]) # Last 3 chunks for context

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
        return {'error': 'JSON Decode Error', 'message': str(e)}
    except Exception as e:
        print(f"❌ OpenAI analysis error: {e}")
        return {
            'politeness': 5, 'objection_handling': 5, 'product_knowledge': 5,
            'customer_happiness': 5, 'communication_clarity': 5,
            'problem_resolution': 5, 'listening_skills': 5, 'empathy': 5,
            'overall_score': 5, 'strengths': ['Error during analysis'], 'improvements': [], 'sentiment': 'neutral'
        }


# --- Flask Routes ---
@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'twilio_polling_active': call_monitor.polling_thread and call_monitor.polling_thread.is_alive(),
        'active_calls_count': len(live_data['active_calls']),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/stats')
def get_stats():
    """Get current stats"""
    return jsonify({
        'total_calls': live_data['call_stats']['total_calls'],
        'active_calls': live_data['call_stats']['in_progress'],
        'completed_calls': live_data['call_stats']['completed'],
        'analyzed_segments': live_data['call_stats']['analyzed_segments'],
        'average_quality_score': round(live_data['call_stats']['average_quality_score'], 1) if live_data['call_stats']['analyzed_segments'] > 0 else 0.0,
        'agents_count': len(set(call['to_number'] for call in live_data['active_calls'].values()))
    })

@app.route('/test-twilio', methods=['GET'])
def test_twilio():
    """Test Twilio connection and show recent calls"""
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
    """Simulate a call for testing (without actual Twilio/ElevenLabs connection)"""
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
            'analysis': []
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
            time.sleep(3) # Simulate call starting
            fake_segments = [
                "Hello, thank you for calling. How may I assist you today?",
                "I understand you're having an issue with your internet connection. Let me check that for you.",
                "Yes, I can confirm that. We'll need to reset your router. Can you do that for me now?",
                "Excellent. Please wait a moment while it reboots.",
                "Great! Is there anything else I can help you with today?"
            ]
            for i, segment in enumerate(fake_segments):
                if fake_call_sid not in live_data['active_calls']:
                    break # Call ended during simulation

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
                time.sleep(5) # Simulate delay between segments

            time.sleep(5) # Simulate call ending
            if fake_call_sid in live_data['active_calls']:
                call_monitor.handle_call_end(fake_call_sid)

        threading.Thread(target=generate_fake_transcript_and_analysis, daemon=True).start()

        return jsonify({'status': 'success', 'call_sid': fake_call_sid})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/webhook/call-start', methods=['POST'])
def twilio_call_start():
    """Twilio webhook when call starts - initiates media stream and ElevenLabs agent stream."""
    from twilio.twiml.voice_response import VoiceResponse

    call_sid = request.form.get('CallSid')
    from_number = request.form.get('From')
    to_number = request.form.get('To')

    print(f"🔔 Twilio webhook: Call {call_sid} from {from_number} to {to_number}")

    # Initialize ElevenLabs Agent Stream for this call
    elevenlabs_agent_stream = ElevenLabsAgentStream(
        call_sid=call_sid,
        elevenlabs_api_key=ELEVENLABS_API_KEY,
        elevenlabs_agent_id=ELEVENLABS_AGENT_ID,
        socketio_ref=socketio # Pass socketio reference for emitting
    )
    elevenlabs_agent_stream.start() # Start the separate thread for ElevenLabs WebSocket

    # Store the stream object in live_data
    live_data['active_calls'][call_sid] = {
        'number': from_number,
        'to_number': to_number,
        'start_time': datetime.now(),
        'duration': '00:00',
        'status': 'in-progress',
        'transcripts': [],
        'analysis': [],
        'elevenlabs_agent_stream': elevenlabs_agent_stream # Store the stream manager
    }
    live_data['call_stats']['total_calls'] += 1
    live_data['call_stats']['in_progress'] += 1

    # Create TwiML response with media streaming
    response = VoiceResponse()
    # The URL for the stream should be accessible from Twilio.
    # On Koyeb/Heroku, this would be your app's public URL.
    stream_url = f'wss://{request.host}/audio-stream/{call_sid}'
    response.start().stream(
        url=stream_url,
        track='both_tracks' # Stream audio from both agent and customer
    )
    # Connect the call to its destination (e.g., an agent, another number)
    response.dial(to_number)

    # Emit to dashboard that call started
    socketio.emit('call_started', {
        'call_sid': call_sid,
        'number': from_number,
        'to_number': to_number,
        'start_time': live_data['active_calls'][call_sid]['start_time'].strftime("%Y-%m-%d %H:%M:%S")
    })

    return str(response)

@app.route('/webhook/call-end', methods=['POST'])
def twilio_call_end():
    """Twilio webhook when call ends"""
    call_sid = request.form.get('CallSid')
    # duration = int(request.form.get('CallDuration', 0)) # CallDuration isn't always reliable directly after end

    print(f"🔚 Call ended webhook received for: {call_sid}")

    # The LiveCallMonitor's handle_call_end will clean up the ElevenLabs stream
    call_monitor.handle_call_end(call_sid)

    return '', 200

@socketio.on('connect', namespace='/audio-stream')
def handle_audio_stream_connect():
    """Handles Twilio Media Stream WebSocket connections."""
    print(f"🎧 Twilio Media Stream WebSocket connected.")

@socketio.on('message', namespace='/audio-stream')
def handle_media_stream_message(message):
    """Processes incoming audio from Twilio Media Stream."""
    # Twilio sends messages as JSON
    # This endpoint gets 'message' type events from Twilio (not 'media')
    # Twilio Docs: https://www.twilio.com/docs/voice/api/streaming#message-payload-description
    try:
        # if isinstance(message, str): # messages could be strings if not JSON
        #     payload = json.loads(message)
        # else:
        payload = message # Flask-SocketIO might already parse JSON

        event_type = payload.get('event')
        call_sid = payload.get('call_sid') # Use call_sid directly if present, or infer from streamSid later

        # Twilio Media Stream events: 'start', 'media', 'stop', 'mark'
        if event_type == 'start':
            # This is sent once at the beginning of the stream
            print(f"Twilio Media Stream 'start' event for CallSid: {call_sid}")
        elif event_type == 'media':
            # This is where the actual audio data comes in
            chunk_id = payload['sequence_number']
            audio_payload = payload['media']['payload']
            # audio_chunk_type = payload['media']['chunk'] # "start", "middle", "end"

            if call_sid and call_sid in live_data['active_calls']:
                call_data = live_data['active_calls'][call_sid]
                elevenlabs_stream = call_data.get('elevenlabs_agent_stream')

                if elevenlabs_stream:
                    # Decode base64 audio (mulaw from Twilio)
                    audio_data_mulaw = base64.b64decode(audio_payload)
                    # Convert mulaw to 16-bit linear PCM (ElevenLabs expects PCM)
                    # Twilio's audio is typically 8kHz mono mulaw
                    pcm_audio = audioop.ulaw2lin(audio_data_mulaw, 2) # 2 bytes per sample = 16-bit

                    # Send PCM audio to the ElevenLabs Agent Stream queue
                    elevenlabs_stream.send_audio(pcm_audio)
                else:
                    print(f"No ElevenLabs Agent Stream found for Call SID {call_sid}. Audio dropped.")
            else:
                print(f"Media received for unknown or ended Call SID: {call_sid}. Audio dropped.")

        elif event_type == 'stop':
            print(f"Twilio Media Stream 'stop' event for CallSid: {call_sid}")
            # The call_end webhook should handle clean up, but can add redundancy here.
            # However, avoid race conditions if handle_call_end is already running.

    except json.JSONDecodeError as e:
        print(f"❌ Error decoding Twilio Media Stream JSON: {e} - Message: {message}")
    except Exception as e:
        print(f"❌ Error handling Twilio Media Stream message: {e}")
        import traceback
        traceback.print_exc()

@socketio.on('disconnect', namespace='/audio-stream')
def handle_audio_stream_disconnect():
    """Handles disconnection of Twilio Media Stream WebSocket."""
    print("🎧 Twilio Media Stream WebSocket disconnected.")
    # Note: Flask-SocketIO's disconnect event doesn't easily provide the CallSid
    # You would need to map session IDs to CallSids if you want to clean up
    # ElevenLabs streams here. Best to rely on the /webhook/call-end for cleanup.


@socketio.on('connect')
def handle_dashboard_connect():
    """WebSocket connection from dashboard frontend"""
    emit('connected', {'status': 'Connected to live call monitoring'})

@socketio.on('get_live_data')
def handle_get_live_data():
    """Send live dashboard data"""
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

    # Start the Twilio call polling thread immediately
    call_monitor.start_polling()

    # Important: For Gunicorn deployment, use the `create_app` function.
    # For local dev, run with `python app.py` which will use Flask's dev server.
    socketio.run(app, debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), allow_unsafe_werkzeug=True) # allow_unsafe_werkzeug for older Flask/Werkzeug versions with Flask-SocketIO

# For gunicorn deployment
def create_app():
    # Only start background polling here if you're sure it runs once per process
    # Or, preferably, run the LiveCallMonitor in a separate worker Dyno/process
    call_monitor.start_polling() # Ensure this only starts once
    return app
