import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import openai
import json
import datetime
from collections import defaultdict, deque
import threading
import requests
import time
from twilio.rest import Client
import base64

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY') 
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')

# SPECIFY YOUR PHONE NUMBERS TO MONITOR
MONITOR_PHONE_NUMBERS = [
    '+1234567890',  # Your Twilio phone number 1
    '+0987654321',  # Your Twilio phone number 2
    # Add more numbers as needed
]

if not all([OPENAI_API_KEY, ELEVENLABS_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN]):
    print("❌ Missing environment variables! Set OPENAI_API_KEY, ELEVENLABS_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN")
    exit(1)

if not MONITOR_PHONE_NUMBERS:
    print("❌ No phone numbers specified! Add your Twilio numbers to MONITOR_PHONE_NUMBERS list")
    exit(1)

openai.api_key = OPENAI_API_KEY
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Live call data storage
live_data = {
    'active_calls': {},
    'total_calls': 0,
    'analyzed_calls': 0,
    'quality_scores': defaultdict(lambda: defaultdict(list)),
    'live_scores': {},
    'call_history': deque(maxlen=100)
}

# Quality factors
QUALITY_FACTORS = [
    'politeness', 'objection_handling', 'product_knowledge', 
    'customer_happiness', 'communication_clarity', 'problem_resolution',
    'listening_skills', 'empathy'
]

class LiveCallMonitor:
    def __init__(self):
        self.monitoring = False
        self.processed_calls = set()
    
    def start_monitoring(self):
        """Start polling for live calls"""
        self.monitoring = True
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        print("🎧 Started live call monitoring")
    
    def monitor_loop(self):
        """Main monitoring loop - polls APIs every 3 seconds"""
        while self.monitoring:
            try:
                self.poll_active_calls()
                time.sleep(3)  # Poll every 3 seconds
            except Exception as e:
                print(f"❌ Monitoring error: {e}")
                time.sleep(5)
    
    def poll_active_calls(self):
        """Poll Twilio for active calls ONLY on specified numbers"""
        try:
            current_call_sids = set()
            print(f"🔍 Polling for active calls on {len(MONITOR_PHONE_NUMBERS)} numbers...")
            
            # Check each monitored phone number
            for phone_number in MONITOR_PHONE_NUMBERS:
                print(f"📞 Checking calls for {phone_number}...")
                
                # Check calls TO this number
                calls_to = twilio_client.calls.list(
                    to=phone_number, 
                    status='in-progress', 
                    limit=5
                )
                print(f"   Calls TO {phone_number}: {len(calls_to)}")
                
                # Check calls FROM this number  
                calls_from = twilio_client.calls.list(
                    from_=phone_number,
                    status='in-progress',
                    limit=5
                )
                print(f"   Calls FROM {phone_number}: {len(calls_from)}")
                
                # Process all calls for this number
                all_calls = calls_to + calls_from
                
                if all_calls:
                    print(f"✅ Found {len(all_calls)} active calls for {phone_number}")
                
                for call in all_calls:
                    call_sid = call.sid
                    current_call_sids.add(call_sid)
                    
                    if call_sid not in live_data['active_calls']:
                        # New call detected
                        print(f"🆕 NEW CALL DETECTED: {call.from_} → {call.to}")
                        self.handle_new_call(call, phone_number)
                    else:
                        # Update existing call
                        self.update_call(call_sid, call)
            
            # Show total active calls found
            if current_call_sids:
                print(f"📊 Total active calls found: {len(current_call_sids)}")
            else:
                print("📊 No active calls found on any monitored numbers")
            
            # Remove ended calls
            ended_calls = set(live_data['active_calls'].keys()) - current_call_sids
            for call_sid in ended_calls:
                self.handle_call_end(call_sid)
                
        except Exception as e:
            print(f"❌ Error polling calls: {e}")
            import traceback
            traceback.print_exc()
    
    def handle_new_call(self, call, monitored_number):
        """Handle new call detection"""
        call_sid = call.sid
        live_data['total_calls'] += 1
        
        live_data['active_calls'][call_sid] = {
            'sid': call_sid,
            'from': call.from_,
            'to': call.to,
            'monitored_number': monitored_number,
            'start_time': call.start_time or datetime.datetime.now(),
            'status': call.status,
            'transcript': '',
            'analysis': {},
            'duration': 0
        }
        
        print(f"📞 New call on {monitored_number}: {call.from_} → {call.to}")
        
        # Start transcript polling for this call
        self.start_transcript_polling(call_sid)
        
        # Emit to dashboard
        socketio.emit('call_started', {
            'call_sid': call_sid,
            'from': call.from_,
            'to': call.to,
            'monitored_number': monitored_number,
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    def update_call(self, call_sid, call):
        """Update existing call data"""
        if call_sid in live_data['active_calls']:
            call_info = live_data['active_calls'][call_sid]
            call_info['status'] = call.status
            
            # Calculate duration
            if call.start_time:
                duration = (datetime.datetime.now() - call.start_time).total_seconds()
                call_info['duration'] = int(duration)
    
    def start_transcript_polling(self, call_sid):
        """Start polling for call transcripts/recordings"""
        def poll_transcript():
            time.sleep(5)  # Wait a bit for call to start
            
            while call_sid in live_data['active_calls']:
                try:
                    # Try to get call recording/transcript
                    call = twilio_client.calls(call_sid).fetch()
                    
                    # Simulate getting transcript data (replace with actual ElevenLabs call)
                    transcript_chunk = self.get_transcript_chunk(call_sid)
                    
                    if transcript_chunk:
                        self.process_transcript(call_sid, transcript_chunk)
                    
                    time.sleep(10)  # Poll transcript every 10 seconds
                    
                except Exception as e:
                    print(f"Transcript polling error for {call_sid}: {e}")
                    break
        
        threading.Thread(target=poll_transcript, daemon=True).start()
    
    def get_transcript_chunk(self, call_sid):
        """Get transcript chunk (implement ElevenLabs API call here)"""
        try:
            # This is where you'd call ElevenLabs API to get transcript
            # For now, simulate with dummy data
            
            import random
            
            if random.random() > 0.7:  # 30% chance of new transcript
                sample_responses = [
                    "Thank you for calling, how can I help you today?",
                    "I understand your concern, let me look into that for you.",
                    "I'd be happy to assist you with that issue.",
                    "Can you please provide me with your account number?",
                    "I've found the information you need. Here's what I can tell you..."
                ]
                return random.choice(sample_responses)
            
            return None
            
        except Exception as e:
            print(f"Error getting transcript: {e}")
            return None
    
    def process_transcript(self, call_sid, transcript_chunk):
        """Process transcript chunk and analyze quality"""
        if call_sid not in live_data['active_calls']:
            return
        
        # Add to call transcript
        live_data['active_calls'][call_sid]['transcript'] += transcript_chunk + ' '
        
        # Analyze with OpenAI
        analysis = self.analyze_agent_response(transcript_chunk)
        live_data['active_calls'][call_sid]['analysis'] = analysis
        
        # Update live scores
        if 'overall_score' in analysis:
            live_data['live_scores'][call_sid] = analysis['overall_score']
            live_data['analyzed_calls'] += 1
        
        # Store quality scores
        for factor in QUALITY_FACTORS:
            if factor in analysis:
                live_data['quality_scores'][call_sid][factor].append(analysis[factor])
        
        # Emit live update
        socketio.emit('live_analysis', {
            'call_sid': call_sid,
            'transcript': transcript_chunk,
            'analysis': analysis,
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    def analyze_agent_response(self, transcript):
        """Analyze agent response with OpenAI"""
        try:
            prompt = f"""
            Analyze this call center agent response for quality metrics:
            
            Agent Response: "{transcript}"
            
            Rate each factor from 1-10 and return ONLY valid JSON:
            
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
            
        except Exception as e:
            print(f"OpenAI analysis error: {e}")
            return {
                'politeness': 5, 'objection_handling': 5, 'product_knowledge': 5,
                'customer_happiness': 5, 'communication_clarity': 5, 
                'problem_resolution': 5, 'listening_skills': 5, 'empathy': 5,
                'overall_score': 5, 'strengths': [], 'improvements': [], 'sentiment': 'neutral'
            }
    
    def handle_call_end(self, call_sid):
        """Handle call end"""
        if call_sid in live_data['active_calls']:
            call_info = live_data['active_calls'][call_sid]
            call_info['end_time'] = datetime.datetime.now()
            
            # Move to history
            live_data['call_history'].append(call_info)
            del live_data['active_calls'][call_sid]
            
            # Clean up scores
            if call_sid in live_data['live_scores']:
                del live_data['live_scores'][call_sid]
            
            print(f"📞 Call ended: {call_sid}")
            
            # Emit to dashboard
            socketio.emit('call_ended', {
                'call_sid': call_sid,
                'final_analysis': call_info.get('analysis', {})
            })

# Initialize monitor
monitor = LiveCallMonitor()

@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'monitoring': monitor.monitoring,
        'active_calls': len(live_data['active_calls']),
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/api/stats')
def get_stats():
    """Get current stats"""
    # Calculate averages
    all_scores = []
    factor_averages = {}
    
    for call_sid, factors in live_data['quality_scores'].items():
        for factor, scores in factors.items():
            if scores:
                if factor not in factor_averages:
                    factor_averages[factor] = []
                factor_averages[factor].extend(scores)
    
    for factor in QUALITY_FACTORS:
        if factor in factor_averages:
            avg = sum(factor_averages[factor]) / len(factor_averages[factor])
            factor_averages[factor] = round(avg, 1)
        else:
            factor_averages[factor] = 0.0
    
    # Live average
    live_avg = 0.0
    if live_data['live_scores']:
        live_avg = round(sum(live_data['live_scores'].values()) / len(live_data['live_scores']), 1)
    
    return jsonify({
        'total_calls': live_data['total_calls'],
        'analyzed_calls': live_data['analyzed_calls'],
        'active_calls': len(live_data['active_calls']),
        'live_average': live_avg,
        'factor_averages': factor_averages,
        'agents_count': len(set(call['to'] for call in live_data['active_calls'].values()))
    })

@app.route('/test-twilio', methods=['GET'])
def test_twilio():
    """Test Twilio connection and show recent calls"""
    try:
        # Test connection
        account = twilio_client.api.accounts(TWILIO_ACCOUNT_SID).fetch()
        print(f"✅ Twilio connection successful: {account.friendly_name}")
        
        # Get recent calls (last 10)
        recent_calls = twilio_client.calls.list(limit=10)
        print(f"📞 Found {len(recent_calls)} recent calls")
        
        call_info = []
        for call in recent_calls:
            call_info.append({
                'sid': call.sid,
                'from': call.from_,
                'to': call.to,
                'status': call.status,
                'start_time': str(call.start_time),
                'direction': call.direction
            })
            print(f"   {call.from_} → {call.to} | Status: {call.status} | {call.start_time}")
        
        return jsonify({
            'status': 'success',
            'account_name': account.friendly_name,
            'monitored_numbers': MONITOR_PHONE_NUMBERS,
            'recent_calls': call_info
        })
        
    except Exception as e:
        print(f"❌ Twilio connection failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/simulate-call', methods=['POST'])
def simulate_call():
    """Simulate a call for testing"""
    try:
        # Create fake call data
        fake_call_sid = f"fake_call_{int(time.time())}"
        
        live_data['total_calls'] += 1
        live_data['active_calls'][fake_call_sid] = {
            'sid': fake_call_sid,
            'from': '+1234567890',
            'to': MONITOR_PHONE_NUMBERS[0] if MONITOR_PHONE_NUMBERS else '+0987654321',
            'monitored_number': MONITOR_PHONE_NUMBERS[0] if MONITOR_PHONE_NUMBERS else '+0987654321',
            'start_time': datetime.datetime.now(),
            'status': 'in-progress',
            'transcript': '',
            'analysis': {},
            'duration': 0
        }
        
        print(f"🎭 SIMULATED CALL: {fake_call_sid}")
        
        # Emit to dashboard
        socketio.emit('call_started', {
            'call_sid': fake_call_sid,
            'from': '+1234567890',
            'to': MONITOR_PHONE_NUMBERS[0] if MONITOR_PHONE_NUMBERS else '+0987654321',
            'monitored_number': MONITOR_PHONE_NUMBERS[0] if MONITOR_PHONE_NUMBERS else '+0987654321',
            'timestamp': datetime.datetime.now().isoformat()
        })
        
        # Start generating fake transcript
        def generate_fake_transcript():
            time.sleep(3)
            fake_responses = [
                "Thank you for calling, how can I help you today?",
                "I understand your concern about your account.",
                "Let me look that up for you right away.",
                "I can definitely help you resolve this issue.",
                "Is there anything else I can assist you with?"
            ]
            
            for i, response in enumerate(fake_responses):
                if fake_call_sid not in live_data['active_calls']:
                    break
                    
                monitor.process_transcript(fake_call_sid, response)
                time.sleep(5)
                
            # End fake call after 30 seconds
            time.sleep(10)
            if fake_call_sid in live_data['active_calls']:
                monitor.handle_call_end(fake_call_sid)
        
        threading.Thread(target=generate_fake_transcript, daemon=True).start()
        
        return jsonify({'status': 'success', 'call_sid': fake_call_sid})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook/call-start', methods=['POST'])
def twilio_call_start():
    """Twilio webhook when call starts"""
    from twilio.twiml import VoiceResponse
    
    call_sid = request.form.get('CallSid')
    from_number = request.form.get('From')
    to_number = request.form.get('To')
    
    print(f"🔔 Twilio webhook: Call {call_sid} from {from_number} to {to_number}")
    
    # Create call record
    live_data['total_calls'] += 1
    live_data['active_calls'][call_sid] = {
        'sid': call_sid,
        'from': from_number,
        'to': to_number,
        'start_time': datetime.datetime.now(),
        'status': 'in-progress',
        'transcript': '',
        'analysis': {},
        'duration': 0
    }
    
    # Create TwiML response with media streaming
    response = VoiceResponse()
    
    # Start media streaming
    response.start().stream(
        url=f'wss://{request.host}/audio-stream/{call_sid}',
        track='both_tracks'
    )
    
    # Connect the call
    response.dial(to_number)
    
    # Emit to dashboard
    socketio.emit('call_started', {
        'call_sid': call_sid,
        'from': from_number,
        'to': to_number,
        'timestamp': datetime.datetime.now().isoformat()
    })
    
    return str(response)

@app.route('/webhook/call-end', methods=['POST'])
def twilio_call_end():
    """Twilio webhook when call ends"""
    call_sid = request.form.get('CallSid')
    duration = int(request.form.get('CallDuration', 0))
    
    print(f"🔚 Call ended: {call_sid}, duration: {duration}s")
    
    if call_sid in live_data['active_calls']:
        monitor.handle_call_end(call_sid)
    
    return '', 200

@socketio.on('connect', namespace='/audio-stream')
def handle_audio_connect():
    print(f"🎧 Audio stream connected")

@socketio.on('media', namespace='/audio-stream')
def handle_media_stream(data):
    """Handle incoming audio stream from Twilio"""
    try:
        call_sid = data.get('streamSid', '').replace('MZ', '').replace('ST', '')
        
        if 'media' in data and 'payload' in data['media']:
            # Get audio data
            audio_payload = data['media']['payload']
            
            # Decode base64 audio (mulaw format from Twilio)
            import audioop
            audio_data = base64.b64decode(audio_payload)
            
            # Convert mulaw to linear PCM
            linear_audio = audioop.ulaw2lin(audio_data, 2)
            
            # Process audio chunk for transcription
            transcript_chunk = process_audio_for_transcription(linear_audio)
            
            if transcript_chunk and call_sid in live_data['active_calls']:
                monitor.process_transcript(call_sid, transcript_chunk)
                
    except Exception as e:
        print(f"❌ Audio processing error: {e}")

def process_audio_for_transcription(audio_data):
    """Convert audio to transcript using Whisper API"""
    try:
        # Create temporary wav file
        import tempfile
        import wave
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            with wave.open(temp_file.name, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(8000)  # 8kHz (Twilio default)
                wav_file.writeframes(audio_data)
            
            # Send to OpenAI Whisper
            with open(temp_file.name, 'rb') as audio_file:
                transcript = openai.Audio.transcribe(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )
                return transcript.text
                
    except Exception as e:
        print(f"❌ Whisper transcription error: {e}")
        return None

@app.route('/start-monitoring', methods=['POST'])
def start_monitoring():
    """Start the monitoring system"""
    monitor.start_monitoring()
    return jsonify({'status': 'success', 'message': 'Live monitoring started'})

@socketio.on('connect')
def handle_connect():
    """WebSocket connection"""
    emit('connected', {'status': 'Connected to live call monitoring'})

@socketio.on('get_live_data')
def handle_get_live_data():
    """Send live dashboard data"""
    active_calls_data = []
    
    for call_sid, call_info in live_data['active_calls'].items():
        active_calls_data.append({
            'call_sid': call_sid,
            'from': call_info['from'],
            'to': call_info['to'], 
            'monitored_number': call_info.get('monitored_number', 'Unknown'),
            'duration': call_info.get('duration', 0),
            'latest_score': live_data['live_scores'].get(call_sid, 0),
            'analysis': call_info.get('analysis', {})
        })
    
    emit('live_data_update', {
        'active_calls': active_calls_data,
        'total_calls': live_data['total_calls'],
        'analyzed_calls': live_data['analyzed_calls']
    })

if __name__ == '__main__':
    print("🎧 Live Call Quality Monitoring System")
    print("📊 Quality Factors: Politeness, Objection Handling, Knowledge, Customer Happiness")
    print("🔧 Using Environment Variables for API Keys")
    print(f"📞 Monitoring Phone Numbers: {', '.join(MONITOR_PHONE_NUMBERS)}")
    print("🌐 Dashboard: http://localhost:5000")
    print("🧪 Test Twilio: http://localhost:5000/test-twilio")
    print("🎭 Simulate Call: Click 'Simulate Call' button on dashboard")
    print("▶️  Starting monitoring automatically...")
    print("\n" + "="*50)
    print("If you don't see any calls:")
    print("1. Click 'Test Twilio' to verify connection")
    print("2. Check your phone numbers in MONITOR_PHONE_NUMBERS")
    print("3. Click 'Simulate Call' to test the dashboard")
    print("4. Make a real call to/from your monitored numbers")
    print("="*50 + "\n")
    
    # Auto-start monitoring after 2 seconds
    threading.Timer(2.0, monitor.start_monitoring).start()
    
    # Use eventlet for better WebSocket support in production
    socketio.run(app, debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))

# For gunicorn deployment
def create_app():
    # Auto-start monitoring when app starts
    threading.Timer(2.0, monitor.start_monitoring).start()
    return app
