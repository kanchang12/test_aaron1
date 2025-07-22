import os
import json
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import openai
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

# --- Initialize Clients ---
openai.api_key = OPENAI_API_KEY

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

# --- Enhanced KPI Analysis Function ---
def analyze_call_transcript(transcript: str, call_metadata: Dict) -> Dict:
    """
    Analyze call transcript with 18 comprehensive KPIs for call success/failure and user sentiment
    """
    try:
        prompt = f"""
        Analyze this complete call transcript for comprehensive quality metrics and determine call success/failure.
        
        Call Metadata:
        - Duration: {call_metadata.get('duration', 'unknown')} seconds
        - Agent ID: {call_metadata.get('agent_id', 'unknown')}
        - Call Type: {call_metadata.get('call_type', 'unknown')}
        - Source: {call_metadata.get('source', 'unknown')}
        
        Transcript: "{transcript}"

        Provide analysis on these 18 KPIs (rate 1-10, where 1=poor, 10=excellent):

        **Call Success & Resolution KPIs:**
        1. call_success_rate - Was the customer's primary issue/request resolved successfully?
        2. first_call_resolution - Was the issue resolved without requiring callbacks or escalation?
        3. issue_identification - How well did the agent identify and understand the customer's problem?
        4. solution_effectiveness - How effective was the solution provided to the customer?

        **Customer Experience & Sentiment KPIs:**
        5. customer_satisfaction - Overall customer happiness and satisfaction level
        6. user_interaction_sentiment - Customer's emotional journey (frustrated->satisfied, etc.)
        7. customer_effort_score - How easy was it for the customer to get their issue resolved?
        8. wait_time_satisfaction - Customer satisfaction with response times and call flow

        **Agent Performance KPIs:**
        9. communication_clarity - How clearly and understandably did the agent communicate?
        10. listening_skills - How well did the agent listen and understand customer needs?
        11. empathy_emotional_intelligence - Agent's empathy and emotional connection with customer
        12. product_service_knowledge - Agent's knowledge of products, services, and company policies
        13. call_control_flow - Agent's ability to guide and manage the conversation effectively
        14. professionalism_courtesy - Professional demeanor, politeness, and appropriate language use

        **Operational Efficiency KPIs:**
        15. call_handling_efficiency - Appropriate call length relative to issue complexity
        16. information_gathering - How effectively did the agent gather necessary customer information?
        17. follow_up_commitment - Clear next steps, commitments, and follow-up arrangements
        18. compliance_adherence - Following company scripts, policies, and regulatory requirements

        **Overall Assessment:**
        - call_outcome: "success" | "failure" | "partial_success"
        - interaction_sentiment: "positive" | "negative" | "neutral" | "mixed"
        - primary_reason: Brief specific reason for the outcome (max 50 characters)
        - customer_emotion_start: Customer's initial emotional state
        - customer_emotion_end: Customer's final emotional state
        - agent_performance_rating: Overall agent performance (1-10)

        Return ONLY valid JSON in this exact format:
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
            "primary_reason": "Billing issue resolved efficiently",
            "customer_emotion_start": "frustrated",
            "customer_emotion_end": "satisfied",
            "agent_performance_rating": 8,
            "strengths": ["clear communication", "good product knowledge", "professional manner"],
            "improvements": ["could improve follow-up process", "faster information gathering"],
            "key_moments": ["Customer initially frustrated about bill", "Agent explained charges clearly", "Customer thanked agent at end"],
            "call_tags": ["billing", "resolved", "positive_outcome"]
        }}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )

        result = json.loads(response.choices[0].message.content)
        
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

    except json.JSONDecodeError as e:
        print(f"❌ OpenAI analysis JSON decode error: {e}")
        return create_default_analysis_result(error=f"JSON Decode Error: {str(e)}")
    except Exception as e:
        print(f"❌ OpenAI analysis error: {e}")
        import traceback
        traceback.print_exc()
        return create_default_analysis_result(error=f"Analysis Error: {str(e)}")

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

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'total_calls_analyzed': call_data_store['overall_stats']['total_calls'],
        'timestamp': datetime.now().isoformat()
    })

# --- ElevenLabs Webhook Endpoint ---
@app.route('/webhook/elevenlabs/transcript', methods=['POST'])
def elevenlabs_transcript_webhook():
    """Receive post-call transcript from ElevenLabs"""
    try:
        data = request.get_json()
        
        # Extract data from ElevenLabs webhook
        call_id = data.get('conversation_id') or data.get('call_id') or str(uuid.uuid4())
        transcript = data.get('transcript') or data.get('full_transcript', '')
        agent_id = data.get('agent_id', 'unknown')
        duration = data.get('duration_seconds', 0)
        call_type = data.get('call_type', 'unknown')
        
        print(f"📞 Received ElevenLabs transcript for call: {call_id}")
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        # Prepare metadata
        call_metadata = {
            'duration': duration,
            'agent_id': agent_id,
            'call_type': call_type,
            'source': 'elevenlabs'
        }
        
        # Analyze the transcript
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
        
        # Emit real-time update to dashboard
        socketio.emit('new_call_analysis', {
            'call_id': call_id,
            'analysis': analysis_result,
            'duration': duration,
            'agent_id': agent_id,
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
        print(f"✅ Successfully analyzed call {call_id}: {analysis_result.get('call_outcome', 'unknown')}")
        
        return jsonify({
            'status': 'success',
            'call_id': call_id,
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
        # Handle file upload
        if 'audio_file' in request.files:
            file = request.files['audio_file']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                
                # Get metadata from form data
                call_id = request.form.get('call_id', str(uuid.uuid4()))
                duration = float(request.form.get('duration', 0))
                agent_id = request.form.get('agent_id', 'unknown')
                transcript = request.form.get('transcript', '')
                
                print(f"📞 Received Xelion audio for call: {call_id}")
                
                # If transcript provided, analyze it
                analysis_result = None
                if transcript:
                    call_metadata = {
                        'duration': duration,
                        'agent_id': agent_id,
                        'call_type': 'voice',
                        'source': 'xelion',
                        'audio_file': unique_filename
                    }
                    analysis_result = analyze_call_transcript(transcript, call_metadata)
                    
                    # Store call data
                    call_record = {
                        'call_id': call_id,
                        'transcript': transcript,
                        'analysis': analysis_result,
                        'metadata': call_metadata,
                        'timestamp': datetime.now().isoformat(),
                        'duration': duration,
                        'source': 'xelion',
                        'audio_file': unique_filename
                    }
                    
                    call_data_store['completed_calls'][call_id] = call_record
                    update_overall_stats(analysis_result, duration)
                    update_daily_stats(datetime.now().strftime('%Y-%m-%d'), analysis_result)
                    
                    # Emit real-time update
                    socketio.emit('new_call_analysis', {
                        'call_id': call_id,
                        'analysis': analysis_result,
                        'duration': duration,
                        'agent_id': agent_id,
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'has_audio': True
                    })
                
                return jsonify({
                    'status': 'success',
                    'call_id': call_id,
                    'audio_file': unique_filename,
                    'analysis_summary': {
                        'outcome': analysis_result.get('call_outcome') if analysis_result else 'pending',
                        'sentiment': analysis_result.get('interaction_sentiment') if analysis_result else 'unknown',
                        'overall_score': analysis_result.get('overall_score') if analysis_result else 0
                    } if analysis_result else None
                })
        
        # Handle JSON data without file
        data = request.get_json()
        if data:
            call_id = data.get('call_id', str(uuid.uuid4()))
            transcript = data.get('transcript', '')
            duration = data.get('duration', 0)
            agent_id = data.get('agent_id', 'unknown')
            
            if transcript:
                call_metadata = {
                    'duration': duration,
                    'agent_id': agent_id,
                    'call_type': 'voice',
                    'source': 'xelion'
                }
                
                analysis_result = analyze_call_transcript(transcript, call_metadata)
                
                call_record = {
                    'call_id': call_id,
                    'transcript': transcript,
                    'analysis': analysis_result,
                    'metadata': call_metadata,
                    'timestamp': datetime.now().isoformat(),
                    'duration': duration,
                    'source': 'xelion'
                }
                
                call_data_store['completed_calls'][call_id] = call_record
                update_overall_stats(analysis_result, duration)
                update_daily_stats(datetime.now().strftime('%Y-%m-%d'), analysis_result)
                
                socketio.emit('new_call_analysis', {
                    'call_id': call_id,
                    'analysis': analysis_result,
                    'duration': duration,
                    'agent_id': agent_id,
                    'timestamp': datetime.now().strftime("%H:%M:%S")
                })
                
                return jsonify({
                    'status': 'success',
                    'call_id': call_id,
                    'analysis_summary': {
                        'outcome': analysis_result.get('call_outcome'),
                        'sentiment': analysis_result.get('interaction_sentiment'),
                        'overall_score': analysis_result.get('overall_score')
                    }
                })
        
        return jsonify({'error': 'No valid data received'}), 400
        
    except Exception as e:
        print(f"❌ Error processing Xelion webhook: {e}")
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
    
    emit('dashboard_data_update', {
        'recent_calls': recent_calls,
        'total_calls': stats['total_calls'],
        'successful_calls': stats['successful_calls'],
        'failed_calls': stats['failed_calls'],
        'success_rate': round((stats['successful_calls'] / max(stats['total_calls'], 1)) * 100, 1),
        'positive_interactions': stats['positive_interactions'],
        'negative_interactions': stats['negative_interactions'],
        'positive_rate': round((stats['positive_interactions'] / max(stats['total_calls'], 1)) * 100, 1),
        'average_call_duration': round(stats['average_call_duration'], 1),
        'kpi_averages': stats['kpi_averages']
    })

# --- Application Entry Point ---
if __name__ == '__main__':
    print("\n" + "="*60)
    print("📊 Post-Call Analysis Dashboard")
    print("📈 Real-time Call Quality Analytics with 18 KPIs")
    print("🔗 Webhook Endpoints:")
    print("  - ElevenLabs: POST /webhook/elevenlabs/transcript")
    print("  - Xelion: POST /webhook/xelion/audio")
    print("🌐 Dashboard: http://localhost:5000")
    print("🔍 Health Check: http://localhost:5000/health")
    print("📊 API Stats: http://localhost:5000/api/stats")
    print("="*60 + "\n")

    socketio.run(app, debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
