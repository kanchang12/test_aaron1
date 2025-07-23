import os
import json
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from openai import OpenAI
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# --- Configuration ---
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
XELION_API_KEY = os.environ.get('XELION_API_KEY', '')

# File upload settings
UPLOAD_FOLDER = 'audio_uploads'
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'flac', 'm4a'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Secret key for Flask
SECRET_KEY = os.environ.get('SECRET_KEY', 'your_super_secret_default_key_replace_me_in_prod')

# --- Input Validation ---
if not all([OPENAI_API_KEY, ELEVENLABS_API_KEY, SECRET_KEY]):
    print("❌ Missing environment variables! Ensure OPENAI_API_KEY, ELEVENLABS_API_KEY, and SECRET_KEY are set.")
    exit(1)

# Create upload directory
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Initialize OpenAI Client ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Flask App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading'
)

# --- Global Data Stores ---
call_data_store = {
    'completed_calls': {},  # call_id -> call data
    'daily_stats': {},      # date -> stats
    'overall_stats': {
        'total_calls': 0,
        'successful_calls': 0,
        'failed_calls': 0,
        'positive_interactions': 0,
        'negative_interactions': 0,
        'neutral_interactions': 0,
        'average_call_duration': 0.0,
        'total_call_duration': 0.0,
        'kpi_averages': {}
    }
}

# --- Audio Transcription Function ---
def transcribe_audio(audio_file_path: str) -> str:
    """Transcribe audio file using OpenAI Whisper"""
    try:
        print(f"🎵 Starting transcription for: {audio_file_path}")
        
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        
        print(f"✅ Transcription completed. Length: {len(transcript)} characters")
        return transcript
        
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        import traceback
        traceback.print_exc()
        return ""

# --- Enhanced KPI Analysis Function ---
def analyze_call_transcript(transcript: str, call_metadata: Dict) -> Dict:
    """Analyze call transcript with 18 comprehensive KPIs for call success/failure and user sentiment"""
    
    prompt = f"""
    Analyze this call transcript carefully and provide accurate analysis based on what actually happened.
    
    Call Details:
    - Duration: {call_metadata.get('duration', 'unknown')} seconds
    - Agent: {call_metadata.get('agent_id', 'unknown')}
    - Source: {call_metadata.get('source', 'unknown')}
    
    Transcript: "{transcript}"

    Instructions:
    1. Read the ENTIRE transcript carefully
    2. Identify the customer's main issue/complaint
    3. Determine if the issue was actually resolved
    4. Rate based on what ACTUALLY happened, not ideal scenarios
    5. Consider the customer's emotional journey from start to finish

    Rate each KPI from 1-10 based on actual performance:
    - 1-3: Poor (major issues, customer upset, unresolved)
    - 4-6: Average (adequate but room for improvement)
    - 7-8: Good (effective, customer satisfied)
    - 9-10: Excellent (exceptional service, delighted customer)

    For call_outcome:
    - "success": Issue fully resolved, customer satisfied
    - "partial_success": Some progress but not fully resolved
    - "failure": Issue not resolved, customer still upset

    For interaction_sentiment:
    - "positive": Customer ended happy/satisfied
    - "negative": Customer ended frustrated/angry
    - "neutral": Customer neutral throughout
    - "mixed": Customer started negative but ended positive (or vice versa)

    Respond with ONLY this JSON structure:

    {{
        "call_success_rate": 8,
        "first_call_resolution": 7,
        "issue_identification": 8,
        "solution_effectiveness": 7,
        "customer_satisfaction": 8,
        "user_interaction_sentiment": 7,
        "customer_effort_score": 8,
        "wait_time_satisfaction": 6,
        "communication_clarity": 9,
        "listening_skills": 8,
        "empathy_emotional_intelligence": 7,
        "product_service_knowledge": 8,
        "call_control_flow": 8,
        "information_gathering": 7,
        "follow_up_commitment": 6,
        "compliance_adherence": 8,
        "call_handling_efficiency": 7,
        "professionalism_courtesy": 9,
        "overall_score": 7.7,
        "call_outcome": "success",
        "interaction_sentiment": "positive",
        "primary_reason": "Issue resolved effectively",
        "customer_emotion_start": "frustrated",
        "customer_emotion_end": "satisfied",
        "agent_performance_rating": 8,
        "strengths": ["clear communication", "empathy", "problem solving"],
        "improvements": ["faster resolution", "better follow-up"],
        "key_moments": ["customer complaint", "solution provided", "satisfaction achieved"],
        "call_tags": ["support", "resolved", "positive"]
    }}
    """

    try:
        # Try up to 2 times to get valid JSON from OpenAI
        for attempt in range(2):
            try:
                print(f"📊 OpenAI analysis attempt {attempt + 1}/2")
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,  # Lower temperature for more consistent output
                    max_tokens=1200
                )

                response_text = response.choices[0].message.content
                print(f"📊 OpenAI raw response: '{response_text}'")
                print(f"📊 Response length: {len(response_text) if response_text else 0}")
                
                if not response_text or response_text.strip() == "":
                    print("❌ Empty response from OpenAI")
                    if attempt == 1:  # Last attempt
                        return create_default_analysis_result(error="Empty response from OpenAI after retries")
                    continue
                
                response_text = response_text.strip()
                
                # Try to extract JSON from response if it's wrapped in other text
                if "```json" in response_text:
                    print("📊 Found JSON code block, extracting...")
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    if json_end != -1:
                        response_text = response_text[json_start:json_end].strip()
                elif "{" in response_text and "}" in response_text:
                    # Find the JSON object
                    print("📊 Extracting JSON object...")
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1
                    response_text = response_text[json_start:json_end]
                
                print(f"📊 Cleaned response for parsing: '{response_text[:200]}...'")
                
                if not response_text.startswith("{"):
                    print("❌ Response doesn't start with JSON")
                    if attempt == 1:  # Last attempt
                        return create_default_analysis_result(error=f"Invalid JSON format: {response_text[:100]}")
                    continue

                result = json.loads(response_text)
                print("✅ Successfully parsed JSON from OpenAI")
                break  # Success, exit retry loop
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error on attempt {attempt + 1}: {e}")
                if attempt == 1:  # Last attempt
                    return create_default_analysis_result(error=f"JSON Decode Error after retries: {str(e)}")
                continue
                
            except Exception as e:
                print(f"❌ OpenAI API error on attempt {attempt + 1}: {e}")
                if attempt == 1:  # Last attempt
                    return create_default_analysis_result(error=f"OpenAI API Error: {str(e)}")
                continue
        
        # Ensure all required KPI fields are present with default values
        required_kpis = [
            "call_success_rate", "first_call_resolution", "issue_identification", "solution_effectiveness",
            "customer_satisfaction", "user_interaction_sentiment", "customer_effort_score", "wait_time_satisfaction",
            "communication_clarity", "listening_skills", "empathy_emotional_intelligence", "product_service_knowledge",
            "call_control_flow", "information_gathering", "follow_up_commitment", "compliance_adherence",
            "call_handling_efficiency", "professionalism_courtesy"
        ]
        
        for kpi in required_kpis:
            if kpi not in result:
                result[kpi] = 5  # Default neutral score
                
        # Calculate overall score if not provided
        if "overall_score" not in result:
            kpi_scores = [result.get(kpi, 5) for kpi in required_kpis]
            result["overall_score"] = round(sum(kpi_scores) / len(kpi_scores), 1)
                
        return result

    except Exception as e:
        print(f"❌ Unexpected error in analysis: {e}")
        import traceback
        traceback.print_exc()
        return create_default_analysis_result(error=f"Unexpected Error: {str(e)}")

def create_default_analysis_result(error: str = "Unknown error") -> Dict:
    """Create default analysis result when analysis fails"""
    default_kpis = {
        "call_success_rate": 5, "first_call_resolution": 5, "issue_identification": 5, "solution_effectiveness": 5,
        "customer_satisfaction": 5, "user_interaction_sentiment": 5, "customer_effort_score": 5, "wait_time_satisfaction": 5,
        "communication_clarity": 5, "listening_skills": 5, "empathy_emotional_intelligence": 5, "product_service_knowledge": 5,
        "call_control_flow": 5, "information_gathering": 5, "follow_up_commitment": 5, "compliance_adherence": 5,
        "call_handling_efficiency": 5, "professionalism_courtesy": 5
    }
    
    return {
        **default_kpis,
        "overall_score": 5.0,
        "call_outcome": "unknown",
        "interaction_sentiment": "neutral",
        "primary_reason": f"Analysis failed: {error}",
        "customer_emotion_start": "unknown",
        "customer_emotion_end": "unknown",
        "agent_performance_rating": 5,
        "strengths": ["Analysis failed"],
        "improvements": ["Retry analysis"],
        "key_moments": [],
        "call_tags": ["analysis_error"]
    }

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def update_overall_stats(analysis_result: Dict, call_duration: float):
    """Update overall statistics with new call data"""
    stats = call_data_store['overall_stats']
    
    stats['total_calls'] += 1
    stats['total_call_duration'] += call_duration
    stats['average_call_duration'] = stats['total_call_duration'] / stats['total_calls']
    
    # Update success/failure counts
    call_outcome = analysis_result.get('call_outcome', 'unknown')
    if call_outcome == 'success':
        stats['successful_calls'] += 1
    elif call_outcome == 'failure':
        stats['failed_calls'] += 1
    
    # Update sentiment counts
    sentiment = analysis_result.get('interaction_sentiment', 'neutral')
    if sentiment == 'positive':
        stats['positive_interactions'] += 1
    elif sentiment == 'negative':
        stats['negative_interactions'] += 1
    else:
        stats['neutral_interactions'] += 1
    
    # Update KPI averages
    kpi_fields = [
        "call_success_rate", "first_call_resolution", "issue_identification", "solution_effectiveness",
        "customer_satisfaction", "user_interaction_sentiment", "customer_effort_score", "wait_time_satisfaction",
        "communication_clarity", "listening_skills", "empathy_emotional_intelligence", "product_service_knowledge",
        "call_control_flow", "information_gathering", "follow_up_commitment", "compliance_adherence",
        "call_handling_efficiency", "professionalism_courtesy"
    ]
    
    for kpi in kpi_fields:
        if kpi in analysis_result:
            current_avg = stats['kpi_averages'].get(kpi, 0)
            new_avg = ((current_avg * (stats['total_calls'] - 1)) + analysis_result[kpi]) / stats['total_calls']
            stats['kpi_averages'][kpi] = round(new_avg, 2)

def update_daily_stats(date_str: str, analysis_result: Dict):
    """Update daily statistics"""
    if date_str not in call_data_store['daily_stats']:
        call_data_store['daily_stats'][date_str] = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'positive_sentiment': 0,
            'negative_sentiment': 0,
            'neutral_sentiment': 0,
            'average_score': 0.0
        }
    
    daily = call_data_store['daily_stats'][date_str]
    daily['total_calls'] += 1
    
    # Update daily outcome counts
    if analysis_result.get('call_outcome') == 'success':
        daily['successful_calls'] += 1
    elif analysis_result.get('call_outcome') == 'failure':
        daily['failed_calls'] += 1
    
    # Update daily sentiment counts
    sentiment = analysis_result.get('interaction_sentiment', 'neutral')
    if sentiment == 'positive':
        daily['positive_sentiment'] += 1
    elif sentiment == 'negative':
        daily['negative_sentiment'] += 1
    else:
        daily['neutral_sentiment'] += 1
    
    # Update daily average score
    current_avg = daily['average_score']
    overall_score = analysis_result.get('overall_score', 5.0)
    daily['average_score'] = ((current_avg * (daily['total_calls'] - 1)) + overall_score) / daily['total_calls']

# --- Flask Routes ---
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/debug/calls')
def debug_calls():
    """Debug endpoint to see all stored calls"""
    return jsonify({
        'completed_calls': call_data_store['completed_calls'],
        'overall_stats': call_data_store['overall_stats'],
        'total_stored': len(call_data_store['completed_calls']),
        'call_ids': list(call_data_store['completed_calls'].keys())
    })

@app.route('/debug/latest')
def debug_latest():
    """Debug endpoint to see latest call details"""
    calls = list(call_data_store['completed_calls'].values())
    if calls:
        latest = sorted(calls, key=lambda x: x['timestamp'], reverse=True)[0]
        return jsonify({
            'latest_call': latest,
            'analysis_keys': list(latest.get('analysis', {}).keys()),
            'has_transcript': bool(latest.get('transcript')),
            'transcript_length': len(latest.get('transcript', ''))
        })
    return jsonify({'message': 'No calls found'})

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'total_calls_analyzed': call_data_store['overall_stats']['total_calls'],
        'timestamp': datetime.now().isoformat()
    })

# --- ElevenLabs Webhook Endpoint - FIXED ---
@app.route('/webhook/elevenlabs/transcript', methods=['POST'])
def elevenlabs_transcript_webhook():
    """Receive post-call transcript from ElevenLabs"""
    try:
        data = request.get_json()
        
        # LOG THE ENTIRE PAYLOAD TO DEBUG
        print(f"📞 ElevenLabs webhook payload: {json.dumps(data, indent=2)}")
        
        # Try multiple possible field names for transcript
        transcript = ""
        possible_transcript_fields = [
            'transcript', 'full_transcript', 'text', 'content', 
            'transcription', 'speech_text', 'result', 'output'
        ]
        
        # Check main level fields
        for field in possible_transcript_fields:
            if field in data and data[field]:
                transcript_data = data[field]
                # Handle if transcript is a list/array
                if isinstance(transcript_data, list):
                    transcript = ' '.join(str(item) for item in transcript_data if item)
                elif isinstance(transcript_data, str):
                    transcript = transcript_data
                else:
                    transcript = str(transcript_data)
                
                if transcript.strip():
                    print(f"📞 Found transcript in field '{field}': {len(transcript)} characters")
                    break
        
        # Check nested objects
        if not transcript and 'data' in data:
            for field in possible_transcript_fields:
                if field in data['data'] and data['data'][field]:
                    transcript_data = data['data'][field]
                    # Handle if transcript is a list/array
                    if isinstance(transcript_data, list):
                        transcript = ' '.join(str(item) for item in transcript_data if item)
                    elif isinstance(transcript_data, str):
                        transcript = transcript_data
                    else:
                        transcript = str(transcript_data)
                    
                    if transcript.strip():
                        print(f"📞 Found transcript in data.{field}: {len(transcript)} characters")
                        break
        
        # If still no transcript, try to build it from messages array
        if not transcript and 'messages' in data:
            print("📞 Building transcript from messages array...")
            transcript_parts = []
            for message in data['messages']:
                if 'role' in message and 'message' in message and message['message']:
                    role = message['role'].title()  # Agent/User
                    content = message['message']
                    transcript_parts.append(f"{role}: {content}")
            
            transcript = '\n'.join(transcript_parts)
            if transcript:
                print(f"📞 Built transcript from messages: {len(transcript)} characters")
        
        # Try transcript_summary if available
        if not transcript and 'analysis' in data and 'transcript_summary' in data['analysis']:
            transcript = data['analysis']['transcript_summary']
            print(f"📞 Using transcript_summary: {len(transcript)} characters")
        
        # Extract other fields with multiple possible names
        call_id = (data.get('conversation_id') or data.get('call_id') or 
                  data.get('id') or data.get('session_id') or str(uuid.uuid4()))
        
        agent_id = (data.get('agent_id') or data.get('user_id') or 
                   data.get('operator_id') or 'unknown')
        
        # Try to get duration from metadata
        duration = 0
        if 'metadata' in data and 'call_duration_secs' in data['metadata']:
            duration = data['metadata']['call_duration_secs']
        else:
            duration = (data.get('duration_seconds') or data.get('duration') or 
                       data.get('call_duration') or data.get('length') or 0)
        
        call_type = (data.get('call_type') or data.get('type') or 
                    data.get('category') or 'unknown')
        
        print(f"📞 Extracted - Call ID: {call_id}, Agent: {agent_id}, Duration: {duration}s")
        print(f"📞 Transcript length: {len(transcript)} characters")
        
        if not transcript or not str(transcript).strip():
            print(f"❌ No transcript found in ElevenLabs webhook")
            print(f"📞 Available top-level keys: {list(data.keys())}")
            if 'data' in data:
                print(f"📞 Available data keys: {list(data['data'].keys())}")
            return jsonify({'error': 'No transcript provided', 'debug_payload_keys': list(data.keys())}), 400
        
        # Ensure transcript is a string
        transcript = str(transcript).strip()
        
        # Prepare metadata
        call_metadata = {
            'duration': duration,
            'agent_id': agent_id,
            'call_type': call_type,
            'source': 'elevenlabs'
        }
        
        # Analyze the transcript
        print(f"📊 Starting analysis for ElevenLabs call: {call_id}")
        analysis_result = analyze_call_transcript(transcript, call_metadata)
        
        # Store call data
        call_record = {
            'call_id': call_id,
            'transcript': transcript,
            'analysis': analysis_result,
            'metadata': call_metadata,
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'source': 'elevenlabs'
        }
        
        call_data_store['completed_calls'][call_id] = call_record
        update_overall_stats(analysis_result, duration)
        update_daily_stats(datetime.now().strftime('%Y-%m-%d'), analysis_result)
        
        print(f"📊 Stored ElevenLabs call. Total calls now: {len(call_data_store['completed_calls'])}")
        
        # Emit BOTH events to ensure dashboard updates
        socketio.emit('new_call_analysis', {
            'call_id': call_id,
            'analysis': analysis_result,
            'duration': duration,
            'agent_id': agent_id,
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'source': 'elevenlabs'
        })
        
        # Get fresh data for dashboard
        recent_calls = list(call_data_store['completed_calls'].values())[-10:]
        recent_calls = sorted(recent_calls, key=lambda x: x['timestamp'], reverse=True)
        stats = call_data_store['overall_stats']
        
        socketio.emit('dashboard_data_update', {
            'recent_calls': recent_calls,
            'total_calls': stats['total_calls'],
            'successful_calls': stats['successful_calls'],
            'failed_calls': stats['failed_calls'],
            'success_rate': round((stats['successful_calls'] / max(stats['total_calls'], 1)) * 100, 1),
            'positive_interactions': stats['positive_interactions'],
            'negative_interactions': stats['negative_interactions'],
            'neutral_interactions': stats['neutral_interactions'],
            'average_call_duration': round(stats['average_call_duration'], 1),
            'kpi_averages': stats['kpi_averages']
        })
        
        print(f"✅ Successfully analyzed ElevenLabs call {call_id}: {analysis_result.get('call_outcome', 'unknown')}")
        print(f"📡 Emitted WebSocket updates to dashboard")
        
        return jsonify({
            'status': 'success',
            'call_id': call_id,
            'transcript_length': len(transcript),
            'transcript_source': 'messages_array' if 'messages' in data else 'direct_field',
            'analysis_summary': {
                'outcome': analysis_result.get('call_outcome'),
                'sentiment': analysis_result.get('interaction_sentiment'),
                'overall_score': analysis_result.get('overall_score')
            }
        })
        
    except Exception as e:
        print(f"❌ Error processing ElevenLabs webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# --- Xelion Webhook Endpoint ---
@app.route('/webhook/xelion/audio', methods=['POST'])
def xelion_audio_webhook():
    """Receive audio file and/or transcript from Xelion"""
    try:
        print(f"📞 Xelion webhook received - Content-Type: {request.content_type}")
        print(f"📞 Request method: {request.method}")
        
        # Check if this is a multipart form upload (file upload)
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            print(f"📞 Form data keys: {list(request.form.keys())}")
            print(f"📞 Files: {list(request.files.keys())}")
            
            # Handle multipart form data (audio file upload)
            call_id = request.form.get('call_id', str(uuid.uuid4()))
            duration = float(request.form.get('duration', 0))
            agent_id = request.form.get('agent_id', 'unknown')
            provided_transcript = request.form.get('transcript', '')
            
            print(f"📞 Processing multipart form data for call: {call_id}")
            print(f"📞 Agent: {agent_id}, Duration: {duration}s")
            
            # Handle audio file if present
            unique_filename = None
            audio_file_path = None
            if 'audio_file' in request.files:
                file = request.files['audio_file']
                if file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    unique_filename = f"{timestamp}_{filename}"
                    audio_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(audio_file_path)
                    print(f"📞 Audio file saved: {unique_filename}")
                else:
                    print(f"❌ Invalid audio file: {file.filename}")

            # Determine transcript source
            transcript = provided_transcript
            transcript_source = "provided"
            
            # If no transcript provided but audio file exists, transcribe it
            if (not transcript or transcript.strip() == "") and audio_file_path:
                print(f"🎵 No transcript provided, transcribing audio file: {unique_filename}")
                transcript = transcribe_audio(audio_file_path)
                transcript_source = "whisper_transcribed"
                
                if not transcript:
                    print(f"❌ Transcription failed for {unique_filename}")
                    return jsonify({
                        'status': 'error',
                        'call_id': call_id,
                        'audio_file': unique_filename,
                        'error': 'Audio transcription failed'
                    }), 400

            # Process transcript if available
            analysis_result = None
            if transcript and transcript.strip():
                call_metadata = {
                    'duration': duration,
                    'agent_id': agent_id,
                    'call_type': 'voice',
                    'source': 'xelion',
                    'audio_file': unique_filename,
                    'transcript_source': transcript_source
                }
                
                print(f"📞 Analyzing transcript for call: {call_id} (source: {transcript_source})")
                print(f"📞 Transcript preview: {transcript[:200]}...")
                
                analysis_result = analyze_call_transcript(transcript, call_metadata)
                
                if analysis_result:
                    print(f"📊 Analysis completed - Outcome: {analysis_result.get('call_outcome')}, Score: {analysis_result.get('overall_score')}")
                    
                    # Store call data
                    call_record = {
                        'call_id': call_id,
                        'transcript': transcript,
                        'analysis': analysis_result,
                        'metadata': call_metadata,
                        'timestamp': datetime.now().isoformat(),
                        'duration': duration,
                        'source': 'xelion',
                        'audio_file': unique_filename,
                        'transcript_source': transcript_source
                    }
                    
                    call_data_store['completed_calls'][call_id] = call_record
                    print(f"📊 Call record stored successfully")
                    
                    update_overall_stats(analysis_result, duration)
                    print(f"📊 Overall stats updated")
                    
                    update_daily_stats(datetime.now().strftime('%Y-%m-%d'), analysis_result)
                    print(f"📊 Daily stats updated")
                    
                    print(f"📊 Stored Xelion call. Total calls now: {len(call_data_store['completed_calls'])}")
                    
                    # Emit BOTH events to ensure dashboard updates
                    try:
                        print(f"📡 Emitting new_call_analysis event...")
                        socketio.emit('new_call_analysis', {
                            'call_id': call_id,
                            'analysis': analysis_result,
                            'duration': duration,
                            'agent_id': agent_id,
                            'timestamp': datetime.now().strftime("%H:%M:%S"),
                            'has_audio': unique_filename is not None,
                            'transcript_source': transcript_source,
                            'source': 'xelion'
                        })
                        print(f"📡 new_call_analysis event emitted successfully")
                        
                        # Get fresh data for dashboard
                        recent_calls = list(call_data_store['completed_calls'].values())[-10:]
                        recent_calls = sorted(recent_calls, key=lambda x: x['timestamp'], reverse=True)
                        stats = call_data_store['overall_stats']
                        
                        print(f"📡 Emitting dashboard_data_update event...")
                        socketio.emit('dashboard_data_update', {
                            'recent_calls': recent_calls,
                            'total_calls': stats['total_calls'],
                            'successful_calls': stats['successful_calls'],
                            'failed_calls': stats['failed_calls'],
                            'success_rate': round((stats['successful_calls'] / max(stats['total_calls'], 1)) * 100, 1),
                            'positive_interactions': stats['positive_interactions'],
                            'negative_interactions': stats['negative_interactions'],
                            'neutral_interactions': stats['neutral_interactions'],
                            'average_call_duration': round(stats['average_call_duration'], 1),
                            'kpi_averages': stats['kpi_averages']
                        })
                        print(f"📡 dashboard_data_update event emitted successfully")
                        
                    except Exception as socket_error:
                        print(f"❌ WebSocket emission error: {socket_error}")
                        # Continue even if WebSocket fails
                    
                    print(f"✅ Successfully analyzed Xelion call {call_id}: {analysis_result.get('call_outcome', 'unknown')}")
                else:
                    print(f"❌ Analysis failed for call {call_id}")
            else:
                print(f"📞 No transcript available for call: {call_id}")
            
            # ALWAYS return a response regardless of analysis success
            print(f"🚀 Returning response for call {call_id}")
            
            response_data = {
                'status': 'success',
                'call_id': call_id,
                'audio_file': unique_filename,
                'transcript_provided': bool(provided_transcript and provided_transcript.strip()),
                'transcript_transcribed': transcript_source == "whisper_transcribed",
                'analysis_completed': analysis_result is not None,
                'message': f'Audio file uploaded successfully' + 
                          (f' and transcript {transcript_source}' if transcript else ' - no transcript available'),
                'analysis_summary': {
                    'outcome': analysis_result.get('call_outcome') if analysis_result else 'pending',
                    'sentiment': analysis_result.get('interaction_sentiment') if analysis_result else 'unknown',
                    'overall_score': analysis_result.get('overall_score') if analysis_result else 0
                } if analysis_result else None
            }
            
            print(f"📤 Response prepared: {response_data['status']}")
            return jsonify(response_data)
        
        # Check if this is JSON data
        elif request.content_type and 'application/json' in request.content_type:
            try:
                data = request.get_json(force=True)
                if not data:
                    return jsonify({'error': 'No JSON data received'}), 400
                    
                call_id = data.get('call_id', str(uuid.uuid4()))
                transcript = data.get('transcript', '')
                duration = data.get('duration', 0)
                agent_id = data.get('agent_id', 'unknown')
                
                print(f"📞 Processing JSON data for call: {call_id}")
                
                if transcript and transcript.strip():
                    call_metadata = {
                        'duration': duration,
                        'agent_id': agent_id,
                        'call_type': 'voice',
                        'source': 'xelion',
                        'transcript_source': 'provided'
                    }
                    
                    analysis_result = analyze_call_transcript(transcript, call_metadata)
                    
                    call_record = {
                        'call_id': call_id,
                        'transcript': transcript,
                        'analysis': analysis_result,
                        'metadata': call_metadata,
                        'timestamp': datetime.now().isoformat(),
                        'duration': duration,
                        'source': 'xelion',
                        'transcript_source': 'provided'
                    }
                    
                    call_data_store['completed_calls'][call_id] = call_record
                    update_overall_stats(analysis_result, duration)
                    update_daily_stats(datetime.now().strftime('%Y-%m-%d'), analysis_result)
                    
                    print(f"📊 Stored Xelion JSON call. Total calls now: {len(call_data_store['completed_calls'])}")
                    
                    # Emit BOTH events to ensure dashboard updates
                    socketio.emit('new_call_analysis', {
                        'call_id': call_id,
                        'analysis': analysis_result,
                        'duration': duration,
                        'agent_id': agent_id,
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'transcript_source': 'provided',
                        'source': 'xelion'
                    })
                    
                    # Get fresh data for dashboard
                    recent_calls = list(call_data_store['completed_calls'].values())[-10:]
                    recent_calls = sorted(recent_calls, key=lambda x: x['timestamp'], reverse=True)
                    stats = call_data_store['overall_stats']
                    
                    socketio.emit('dashboard_data_update', {
                        'recent_calls': recent_calls,
                        'total_calls': stats['total_calls'],
                        'successful_calls': stats['successful_calls'],
                        'failed_calls': stats['failed_calls'],
                        'success_rate': round((stats['successful_calls'] / max(stats['total_calls'], 1)) * 100, 1),
                        'positive_interactions': stats['positive_interactions'],
                        'negative_interactions': stats['negative_interactions'],
                        'neutral_interactions': stats['neutral_interactions'],
                        'average_call_duration': round(stats['average_call_duration'], 1),
                        'kpi_averages': stats['kpi_averages']
                    })
                    
                    print(f"✅ Successfully analyzed Xelion JSON call {call_id}: {analysis_result.get('call_outcome', 'unknown')}")
                    print(f"📡 Emitted WebSocket updates to dashboard")
                    
                    return jsonify({
                        'status': 'success',
                        'call_id': call_id,
                        'message': 'Transcript analyzed successfully',
                        'analysis_summary': {
                            'outcome': analysis_result.get('call_outcome'),
                            'sentiment': analysis_result.get('interaction_sentiment'),
                            'overall_score': analysis_result.get('overall_score')
                        }
                    })
                else:
                    return jsonify({'error': 'No transcript provided for analysis'}), 400
                    
            except Exception as json_error:
                print(f"❌ JSON parsing error: {json_error}")
                return jsonify({'error': f'Invalid JSON data: {str(json_error)}'}), 400
        
        else:
            return jsonify({
                'error': 'Unsupported content type',
                'received_content_type': request.content_type or 'None',
                'supported_types': ['multipart/form-data (for audio files)', 'application/json (for transcripts)'],
                'usage': {
                    'audio_upload': 'Use multipart/form-data with audio_file, call_id, duration, agent_id, transcript fields',
                    'transcript_only': 'Use application/json with call_id, transcript, duration, agent_id fields'
                }
            }), 400
        
    except Exception as e:
        print(f"❌ Error processing Xelion webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'error_type': type(e).__name__,
            'message': 'Webhook processing failed'
        }), 500

# --- Twilio Webhook Endpoint ---
@app.route('/webhook/twilio/call', methods=['POST'])
def twilio_call_webhook():
    """Handle Twilio call webhooks (incoming calls to +447488891052)"""
    try:
        # Get Twilio webhook data
        call_sid = request.form.get('CallSid')
        from_number = request.form.get('From')  # Customer's number
        to_number = request.form.get('To')      # Your 1052 number
        call_status = request.form.get('CallStatus')
        direction = request.form.get('Direction')
        
        print(f"📞 Twilio webhook: {call_status}")
        print(f"📞 Call SID: {call_sid}")
        print(f"📞 From: {from_number} → To: {to_number}")
        print(f"📞 Direction: {direction}")
        
        # Handle different call statuses
        if call_status in ['ringing', 'in-progress']:
            print(f"📞 Call {call_status}: {call_sid}")
            
            # Return TwiML to connect call to your chatbot or agent
            twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello, welcome to Waste King. Please hold while we connect you to our AI assistant.</Say>
    <Dial>
        <Number>+447866770520</Number>
    </Dial>
</Response>"""
            
            return twiml_response, 200, {'Content-Type': 'text/xml'}
            
        elif call_status == 'completed':
            print(f"📞 Call completed: {call_sid}")
            
            # Get call details for analysis
            duration = request.form.get('CallDuration', 0)
            recording_url = request.form.get('RecordingUrl', '')
            
            if recording_url:
                print(f"🎵 Recording available: {recording_url}")
                # You could download and transcribe the recording here
                
            return jsonify({'status': 'call_logged'}), 200
            
        elif call_status in ['failed', 'busy', 'no-answer']:
            print(f"❌ Call {call_status}: {call_sid}")
            return jsonify({'status': 'call_failed'}), 200
            
        else:
            print(f"📞 Unhandled call status: {call_status}")
            return jsonify({'status': 'received'}), 200
            
    except Exception as e:
        print(f"❌ Error processing Twilio webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/twilio/recording', methods=['POST'])
def twilio_recording_webhook():
    """Handle Twilio recording webhooks"""
    try:
        call_sid = request.form.get('CallSid')
        recording_sid = request.form.get('RecordingSid')
        recording_url = request.form.get('RecordingUrl')
        duration = int(request.form.get('RecordingDuration', 0))
        
        print(f"🎵 Twilio recording webhook:")
        print(f"📞 Call SID: {call_sid}")
        print(f"🎵 Recording SID: {recording_sid}")
        print(f"🎵 Recording URL: {recording_url}")
        print(f"⏱️  Duration: {duration} seconds")
        
        if recording_url and duration > 0:
            # Download and transcribe the recording
            try:
                import requests
                
                # Download the recording
                response = requests.get(recording_url + '.mp3')
                if response.status_code == 200:
                    # Save to file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"twilio_recording_{call_sid}_{timestamp}.mp3"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"💾 Recording saved: {filename}")
                    
                    # Transcribe the recording
                    transcript = transcribe_audio(file_path)
                    
                    if transcript:
                        # Analyze the call
                        call_metadata = {
                            'duration': duration,
                            'agent_id': 'twilio_system',
                            'call_type': 'voice',
                            'source': 'twilio',
                            'call_sid': call_sid,
                            'recording_sid': recording_sid,
                            'audio_file': filename
                        }
                        
                        analysis_result = analyze_call_transcript(transcript, call_metadata)
                        
                        # Store call data
                        call_record = {
                            'call_id': call_sid,
                            'transcript': transcript,
                            'analysis': analysis_result,
                            'metadata': call_metadata,
                            'timestamp': datetime.now().isoformat(),
                            'duration': duration,
                            'source': 'twilio',
                            'audio_file': filename,
                            'recording_url': recording_url
                        }
                        
                        call_data_store['completed_calls'][call_sid] = call_record
                        update_overall_stats(analysis_result, duration)
                        update_daily_stats(datetime.now().strftime('%Y-%m-%d'), analysis_result)
                        
                        print(f"✅ Twilio call analyzed: {analysis_result.get('call_outcome')}")
                        
                        # Emit dashboard updates
                        socketio.emit('new_call_analysis', {
                            'call_id': call_sid,
                            'analysis': analysis_result,
                            'duration': duration,
                            'agent_id': 'twilio_system',
                            'timestamp': datetime.now().strftime("%H:%M:%S"),
                            'source': 'twilio',
                            'has_recording': True
                        })
                        
                        # Update dashboard
                        recent_calls = list(call_data_store['completed_calls'].values())[-10:]
                        recent_calls = sorted(recent_calls, key=lambda x: x['timestamp'], reverse=True)
                        stats = call_data_store['overall_stats']
                        
                        socketio.emit('dashboard_data_update', {
                            'recent_calls': recent_calls,
                            'total_calls': stats['total_calls'],
                            'successful_calls': stats['successful_calls'],
                            'failed_calls': stats['failed_calls'],
                            'success_rate': round((stats['successful_calls'] / max(stats['total_calls'], 1)) * 100, 1),
                            'positive_interactions': stats['positive_interactions'],
                            'negative_interactions': stats['negative_interactions'],
                            'neutral_interactions': stats['neutral_interactions'],
                            'average_call_duration': round(stats['average_call_duration'], 1),
                            'kpi_averages': stats['kpi_averages']
                        })
                        
                    else:
                        print(f"❌ Failed to transcribe Twilio recording: {filename}")
                        
                else:
                    print(f"❌ Failed to download recording: {response.status_code}")
                    
            except Exception as download_error:
                print(f"❌ Error downloading/processing recording: {download_error}")
        
        return jsonify({'status': 'recording_processed'}), 200
        
    except Exception as e:
        print(f"❌ Error processing Twilio recording webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# --- API Endpoints ---
@app.route('/api/stats')
def get_stats():
    stats = call_data_store['overall_stats']
    return jsonify({
        'total_calls': stats['total_calls'],
        'successful_calls': stats['successful_calls'],
        'failed_calls': stats['failed_calls'],
        'success_rate': round((stats['successful_calls'] / max(stats['total_calls'], 1)) * 100, 1),
        'positive_interactions': stats['positive_interactions'],
        'negative_interactions': stats['negative_interactions'],
        'neutral_interactions': stats['neutral_interactions'],
        'positive_rate': round((stats['positive_interactions'] / max(stats['total_calls'], 1)) * 100, 1),
        'negative_rate': round((stats['negative_interactions'] / max(stats['total_calls'], 1)) * 100, 1),
        'average_call_duration': round(stats['average_call_duration'], 1),
        'kpi_averages': stats['kpi_averages']
    })

@app.route('/api/calls')
def get_recent_calls():
    limit = int(request.args.get('limit', 50))
    calls = list(call_data_store['completed_calls'].values())
    recent_calls = sorted(calls, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    return jsonify({
        'calls': recent_calls,
        'total_count': len(calls)
    })

@app.route('/api/calls/<call_id>')
def get_call_details(call_id):
    call = call_data_store['completed_calls'].get(call_id)
    if not call:
        return jsonify({'error': 'Call not found'}), 404
    return jsonify(call)

@app.route('/api/daily-stats')
def get_daily_stats():
    days = int(request.args.get('days', 7))
    daily_data = []
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        stats = call_data_store['daily_stats'].get(date, {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'positive_sentiment': 0,
            'negative_sentiment': 0,
            'neutral_sentiment': 0,
            'average_score': 0.0
        })
        stats['date'] = date
        daily_data.append(stats)
    
    return jsonify(daily_data[::-1])  # Reverse to get chronological order

@app.route('/api/kpi-trends')
def get_kpi_trends():
    """Get KPI trends over time"""
    # This would typically come from a time-series database
    # For now, return current averages as example
    return jsonify({
        'current_kpis': call_data_store['overall_stats']['kpi_averages'],
        'trend_data': []  # Would contain historical KPI data points
    })

# --- Flask-SocketIO Event Handlers ---
@socketio.on('connect')
def handle_dashboard_connect():
    print("🌐 Dashboard client connected via WebSocket.")
    emit('connected', {'status': 'Connected to post-call analysis system!'})
    handle_get_dashboard_data()

@socketio.on('get_dashboard_data')
def handle_get_dashboard_data():
    recent_calls = list(call_data_store['completed_calls'].values())[-10:]  # Last 10 calls
    recent_calls = sorted(recent_calls, key=lambda x: x['timestamp'], reverse=True)
    
    stats = call_data_store['overall_stats']
    
    print(f"📊 Sending dashboard data: {len(recent_calls)} calls, {stats['total_calls']} total")
    
    emit('dashboard_data_update', {
        'recent_calls': recent_calls,
        'total_calls': stats['total_calls'],
        'successful_calls': stats['successful_calls'],
        'failed_calls': stats['failed_calls'],
        'success_rate': round((stats['successful_calls'] / max(stats['total_calls'], 1)) * 100, 1),
        'positive_interactions': stats['positive_interactions'],
        'negative_interactions': stats['negative_interactions'],
        'neutral_interactions': stats['neutral_interactions'],
        'positive_rate': round((stats['positive_interactions'] / max(stats['total_calls'], 1)) * 100, 1),
        'average_call_duration': round(stats['average_call_duration'], 1),
        'kpi_averages': stats['kpi_averages']
    })

# --- Application Entry Point ---
if __name__ == '__main__':
    print("\n" + "="*60)
    print("📊 Post-Call Analysis Dashboard with Whisper Transcription")
    print("📈 Real-time Call Quality Analytics with 18 KPIs")
    print("🎵 Automatic audio transcription using OpenAI Whisper")
    print("🔗 Webhook Endpoints:")
    print("  - ElevenLabs: POST /webhook/elevenlabs/transcript")
    print("  - Xelion: POST /webhook/xelion/audio")
    print("🌐 Dashboard: http://localhost:5000")
    print("🔍 Health Check: http://localhost:5000/health")
    print("📊 API Stats: http://localhost:5000/api/stats")
    print("="*60 + "\n")

    socketio.run(app, debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
