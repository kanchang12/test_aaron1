def download_audio(self, communication_oid: str) -> Optional[str]:
        """Download audio file for a communication and save it to a designated folder."""
        audio_url = f"{self.xelion_base_url}/communications/{communication_oid}/audio"
        
        file_name = f"{communication_oid}.mp3"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.close()
        file_path = temp_file.name

        try:
            response = self.session.get(audio_url, timeout=60) 
            
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                logger.info(from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import requests
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import tempfile
from openai import OpenAI
from deepgram import DeepgramClient, PrerecordedOptions
import schedule
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress HTTP request logs
logging.getLogger('geventwebsocket.handler').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*")

class LiveCallMonitor:
    def __init__(self):
        # API Configuration
        self.xelion_base_url = os.environ.get('XELION_BASE_URL', 'https://lvsl01.xelion.com/api/v1/wasteking')
        self._xelion_username = os.environ.get('XELION_USERNAME', 'abi.housego@wasteking.co.uk')
        self.xelion_password = os.environ.get('XELION_PASSWORD', 'Passw0rd#')
        self.xelion_app_key = os.environ.get('XELION_APP_KEY', 'NtYFnwKdrqbuXAd4N88txxnim2Nd6LnE')
        self.userspace = os.environ.get('XELION_USERSPACE', None)
        
        # AI API keys
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        self.deepgram_api_key = os.environ.get('DEEPGRAM_API_KEY')
        
        # Initialize clients
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        self.deepgram = DeepgramClient(self.deepgram_api_key)
        
        # Session management
        self.session = requests.Session()
        self.session_token = None
        
        # Tracking
        self.processed_calls = set()
        self.is_monitoring = False
        
        # Initialize database
        self.init_database()
        
        # Login to Xelion
        self.login(self._xelion_username)

    def init_database(self):
        """Initialize SQLite database for storing call data with 18 KPIs"""
        conn = sqlite3.connect('calls.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT UNIQUE,
                timestamp DATETIME,
                duration REAL,
                transcript TEXT,
                category TEXT,
                summary TEXT,
                sentiment TEXT,
                priority INTEGER,
                call_outcome TEXT,
                overall_score REAL,
                agent_id TEXT,
                
                -- Call Success & Resolution KPIs
                call_success_rate REAL,
                first_call_resolution REAL,
                issue_identification REAL,
                solution_effectiveness REAL,
                
                -- Customer Experience KPIs
                customer_satisfaction REAL,
                user_interaction_sentiment REAL,
                customer_effort_score REAL,
                wait_time_satisfaction REAL,
                
                -- Agent Performance KPIs
                communication_clarity REAL,
                listening_skills REAL,
                empathy_emotional_intelligence REAL,
                product_service_knowledge REAL,
                call_control_flow REAL,
                professionalism_courtesy REAL,
                
                -- Operational Efficiency KPIs
                call_handling_efficiency REAL,
                information_gathering REAL,
                follow_up_commitment REAL,
                compliance_adherence REAL,
                
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def _get_userspace_for_login(self, current_username: str) -> str:
        """Determines the userspace to use for a given username during login."""
        if self.userspace:
            return self.userspace
        return f"transcriber-{current_username.split('@')[0].replace('.', '-')}" 

    def login(self, username_to_login: str = None) -> bool:
        """
        Authenticate with Xelion using the provided username (or self._xelion_username)
        and obtain a session token.
        """
        if username_to_login is None:
            username_to_login = self._xelion_username
        
        login_url = f"{self.xelion_base_url}/me/login"
        headers = {
            "Content-Type": "application/json"
        }
        
        current_userspace = self._get_userspace_for_login(username_to_login)

        data_payload = { 
            "userName": username_to_login, 
            "password": self.xelion_password,
            "userSpace": current_userspace,     
            "appKey": self.xelion_app_key
        }
        
        json_data_string = json.dumps(data_payload)
        
        logger.info(f"🔑 ATTEMPTING LOGIN: {username_to_login}")
        
        try:
            response = self.session.post(login_url, headers=headers, data=json_data_string)
            response.raise_for_status() 
            
            login_response = response.json()
            self.session_token = login_response.get("authentication")
            self.session.headers.update({"Authorization": f"xelion {self.session_token}"})
            
            valid_until = login_response.get('validUntil', 'N/A')
            logger.info(f"✅ LOGIN SUCCESS: {username_to_login} (Valid until: {valid_until})")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ LOGIN FAILED: {username_to_login}: {e}")
            if e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response: {e.response.text}")
            return False

    def get_recent_calls(self, minutes_back: int = 10) -> List[Dict]:
        """Get recent calls using the working API method"""
        until_date = datetime.now()
        from_date = until_date - timedelta(minutes=minutes_back)
        
        logger.info(f"🔍 CHECKING FOR CALLS FROM {from_date.strftime('%H:%M:%S')} TO {until_date.strftime('%H:%M:%S')}")
        
        communications, _ = self._fetch_communications_page(
            limit=50, 
            until_date=until_date
        )
        
        logger.info(f"📞 GOT {len(communications)} COMMUNICATIONS FROM API")
        
        # Filter for new calls within time range
        new_calls = []
        for comm in communications:
            comm_obj = comm.get('object', {})
            call_id = comm_obj.get('oid')
            call_date_str = comm_obj.get('date')
            
            if not call_id:
                continue
                
            # Parse call date and check if within range
            if call_date_str:
                try:
                    call_date = datetime.strptime(call_date_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    if call_date < from_date:
                        continue  # Too old
                except:
                    pass  # If date parsing fails, include it anyway
            
            if call_id not in self.processed_calls:
                new_calls.append(comm_obj)
                logger.info(f"🆕 NEW CALL FOUND: {call_id} at {call_date_str}")
            else:
                logger.info(f"⏭️ ALREADY PROCESSED: {call_id}")
                
        logger.info(f"✅ RETURNING {len(new_calls)} NEW CALLS FOR PROCESSING")
        return new_calls

    def _fetch_communications_page(self, limit: int, until_date: datetime, before_oid: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
        """
        Fetches a single page of communications.
        Returns (list_of_communications, next_before_oid_for_paging).
        """
        params = {'limit': limit}
        if until_date:
            params['until'] = until_date.strftime('%Y-%m-%d %H:%M:%S') 
        if before_oid:
            params['before'] = before_oid

        base_urls_to_try = [
            self.xelion_base_url,  
            self.xelion_base_url.replace('/wasteking', '/master'), 
            'https://lvsl01.xelion.com/api/v1/master', 
        ]
        
        for base_url in base_urls_to_try:
            communications_url = f"{base_url}/communications"
            logger.info(f"🌐 TRYING API URL: {communications_url}")
            try:
                response = self.session.get(communications_url, params=params, timeout=30) 
                response.raise_for_status()
                
                data = response.json()
                communications = data.get('data', [])
                
                next_before_oid = None
                if 'meta' in data and 'paging' in data['meta']:
                    next_before_oid = data['meta']['paging'].get('previousId')
                
                logger.info(f"✅ SUCCESS WITH {base_url} - GOT {len(communications)} COMMUNICATIONS")
                return communications, next_before_oid
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ FAILED {base_url}: {e}")
                if e.response is not None:
                    logger.warning(f"Response: {e.response.status_code} - {e.response.text[:300]}")
                continue
        
        logger.error("💥 FAILED ALL API URLS!")
        return [], None

    def _fetch_communications_page(self, limit: int, until_date: datetime, before_oid: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
        """
        Fetches a single page of communications.
        Returns (list_of_communications, next_before_oid_for_paging).
        """
        params = {'limit': limit}
        if until_date:
            params['until'] = until_date.strftime('%Y-%m-%d %H:%M:%S') 
        if before_oid:
            params['before'] = before_oid

        base_urls_to_try = [
            self.xelion_base_url,  
            self.xelion_base_url.replace('/wasteking', '/master'), 
            'https://lvsl01.xelion.com/api/v1/master', 
        ]
        
        for base_url in base_urls_to_try:
            communications_url = f"{base_url}/communications"
            try:
                response = self.session.get(communications_url, params=params, timeout=30) 
                response.raise_for_status()
                
                data = response.json()
                communications = data.get('data', [])
                
                next_before_oid = None
                if 'meta' in data and 'paging' in data['meta']:
                    next_before_oid = data['meta']['paging'].get('previousId')
                
                return communications, next_before_oid
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to fetch communications page from {base_url}: {e}")
                if e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}, Response: {e.response.text[:300]}")
                continue
        
        logger.error("Failed to fetch any communications page from all attempted URLs.")
        return [], None

    def download_audio(self, communication_oid: str) -> Optional[str]:
        """Download audio file for a communication and save it to a designated folder."""
        audio_url = f"{self.xelion_base_url}/communications/{communication_oid}/audio"
        
        file_name = f"{communication_oid}.mp3"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.close()
        file_path = temp_file.name

        try:
            response = self.session.get(audio_url, timeout=60) 
            
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"🎵 DOWNLOADED AUDIO: {communication_oid} ({len(response.content)} bytes)")
                return file_path
            elif response.status_code == 404:
                logger.warning(f"❌ NO AUDIO AVAILABLE: {communication_oid}")
                return None
            else:
                logger.error(f"Failed to download audio for {communication_oid}: {response.status_code} - {response.text[:200]}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Audio download failed for {communication_oid}: {e}")
            return None

    def download_audio(self, call_id: str) -> Optional[str]:
        """Download audio file temporarily"""
        audio_url = f"{self.xelion_base_url}/communications/{call_id}/audio"
        
        try:
            response = self.session.get(audio_url, timeout=60)
            
            if response.status_code == 200:
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_file.write(response.content)
                temp_file.close()
                
                logger.info(f"Downloaded audio for call {call_id} ({len(response.content)} bytes)")
                return temp_file.name
            else:
                logger.warning(f"No audio available for call {call_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to download audio for {call_id}: {e}")
            return None

    def transcribe_audio(self, audio_file_path: str, call_id: str) -> Optional[str]:
        """Transcribe audio using Deepgram"""
        try:
            with open(audio_file_path, 'rb') as audio_file:
                buffer_data = audio_file.read()

            payload = {'buffer': buffer_data}
            
            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                utterances=True,
                punctuate=True,
                diarize=True
            )
            
            response = self.deepgram.listen.prerecorded.v('1').transcribe_file(payload, options)
            
            transcript = ""
            if response.results and response.results.channels:
                for utterance in response.results.channels[0].alternatives[0].paragraphs.utterances:
                    speaker = f"Speaker {utterance.speaker}"
                    transcript += f"{speaker}: {utterance.transcript}\n"
            
            logger.info(f"Successfully transcribed call {call_id}")
            return transcript.strip()
            
        except Exception as e:
            logger.error(f"Transcription failed for {call_id}: {e}")
            return None

    def analyze_call(self, transcript: str, call_id: str) -> Dict:
        """Analyze call using GPT-4.0-mini with comprehensive 18 KPI system"""
        prompt = """
        Analyze this call transcript and provide comprehensive evaluation across 18 KPIs organized in 4 categories.
        Rate each KPI from 0.0 to 10.0 (one decimal place).
        
        **CALL SUCCESS & RESOLUTION:**
        1. call_success_rate - Was the call objective achieved?
        2. first_call_resolution - Was the issue resolved without need for follow-up?
        3. issue_identification - How well was the customer's issue identified?
        4. solution_effectiveness - How effective was the solution provided?
        
        **CUSTOMER EXPERIENCE:**
        5. customer_satisfaction - Overall customer satisfaction level
        6. user_interaction_sentiment - Customer's emotional state during call
        7. customer_effort_score - How easy was it for customer to get help?
        8. wait_time_satisfaction - Customer satisfaction with response times
        
        **AGENT PERFORMANCE:**
        9. communication_clarity - How clearly did agent communicate?
        10. listening_skills - How well did agent listen and understand?
        11. empathy_emotional_intelligence - Agent's empathy and emotional awareness
        12. product_service_knowledge - Agent's knowledge of products/services
        13. call_control_flow - How well did agent manage call flow?
        14. professionalism_courtesy - Agent's professionalism and courtesy
        
        **OPERATIONAL EFFICIENCY:**
        15. call_handling_efficiency - Speed and efficiency of call handling
        16. information_gathering - Quality of information collection
        17. follow_up_commitment - Quality of follow-up commitments made
        18. compliance_adherence - Adherence to company policies/procedures
        
        Also provide:
        - category (support, sales, complaint, inquiry, booking, cancellation, other)
        - sentiment (positive, negative, neutral, mixed)
        - priority (1=low, 2=medium, 3=high, 4=urgent)
        - summary (exactly 3 lines, 30 words total - 10 words per line)
        - call_outcome (success, failure, partial_success, unknown)
        - overall_score (average of all 18 KPIs)
        
        Format as JSON with exact field names.
        
        Transcript:
        """ + transcript

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert call quality analyst. Evaluate customer service calls across all 18 KPIs with precise scoring."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Calculate overall score if not provided
            kpi_fields = [
                'call_success_rate', 'first_call_resolution', 'issue_identification', 'solution_effectiveness',
                'customer_satisfaction', 'user_interaction_sentiment', 'customer_effort_score', 'wait_time_satisfaction',
                'communication_clarity', 'listening_skills', 'empathy_emotional_intelligence', 'product_service_knowledge',
                'call_control_flow', 'professionalism_courtesy', 'call_handling_efficiency', 'information_gathering',
                'follow_up_commitment', 'compliance_adherence'
            ]
            
            if 'overall_score' not in result:
                kpi_scores = [result.get(field, 5.0) for field in kpi_fields]
                result['overall_score'] = round(sum(kpi_scores) / len(kpi_scores), 1)
            
            logger.info(f"🧠 ANALYZED CALL {call_id} WITH 18 KPIs")
            return result
            
        except Exception as e:
            logger.error(f"❌ CALL ANALYSIS FAILED: {call_id}: {e}")
            # Return default scores for all 18 KPIs
            default_result = {
                "category": "other",
                "sentiment": "neutral",
                "priority": 2,
                "summary": "Call analysis failed.\nManual review required.\nCheck transcript manually.",
                "call_outcome": "unknown",
                "overall_score": 5.0
            }
            
            # Add all 18 KPIs with default scores
            kpi_defaults = [
                'call_success_rate', 'first_call_resolution', 'issue_identification', 'solution_effectiveness',
                'customer_satisfaction', 'user_interaction_sentiment', 'customer_effort_score', 'wait_time_satisfaction',
                'communication_clarity', 'listening_skills', 'empathy_emotional_intelligence', 'product_service_knowledge',
                'call_control_flow', 'professionalism_courtesy', 'call_handling_efficiency', 'information_gathering',
                'follow_up_commitment', 'compliance_adherence'
            ]
            
            for kpi in kpi_defaults:
                default_result[kpi] = 5.0
                
            return default_result

    def process_call(self, call_data: Dict):
        """Complete call processing pipeline"""
        call_id = call_data.get('oid')
        if not call_id:
            return
            
        logger.info(f"Processing call {call_id}")
        
        # Add to processed set immediately to prevent duplicates
        self.processed_calls.add(call_id)
        
        try:
            # Download audio
            logger.info(f"🎵 DOWNLOADING AUDIO: {call_id}")
            audio_file = self.download_audio(call_id)
            if not audio_file:
                logger.warning(f"❌ NO AUDIO AVAILABLE: {call_id}")
                return
            
            # Transcribe
            logger.info(f"🎙️  TRANSCRIBING AUDIO: {call_id}")
            transcript = self.transcribe_audio(audio_file, call_id)
            
            # Clean up audio file immediately
            try:
                os.unlink(audio_file)
                logger.info(f"🗑️  AUDIO DELETED: {call_id}")
            except:
                logger.error(f"❌ FAILED TO DELETE AUDIO: {call_id}")
                
            if not transcript:
                logger.warning(f"❌ TRANSCRIPTION FAILED: {call_id}")
                return
            
            # Analyze
            logger.info(f"🧠 ANALYZING CALL: {call_id}")
            analysis = self.analyze_call(transcript, call_id)
            
            # Store in database with all 18 KPIs
            conn = sqlite3.connect('calls.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO calls 
                (call_id, timestamp, duration, transcript, category, summary, sentiment, priority, call_outcome, overall_score,
                 call_success_rate, first_call_resolution, issue_identification, solution_effectiveness,
                 customer_satisfaction, user_interaction_sentiment, customer_effort_score, wait_time_satisfaction,
                 communication_clarity, listening_skills, empathy_emotional_intelligence, product_service_knowledge,
                 call_control_flow, professionalism_courtesy, call_handling_efficiency, information_gathering,
                 follow_up_commitment, compliance_adherence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                call_id,
                call_data.get('date', datetime.now().isoformat()),
                call_data.get('duration', 0),
                transcript,
                analysis.get('category', 'other'),
                analysis.get('summary', ''),
                analysis.get('sentiment', 'neutral'),
                analysis.get('priority', 2),
                analysis.get('call_outcome', 'unknown'),
                analysis.get('overall_score', 5.0),
                
                # Call Success & Resolution
                analysis.get('call_success_rate', 5.0),
                analysis.get('first_call_resolution', 5.0),
                analysis.get('issue_identification', 5.0),
                analysis.get('solution_effectiveness', 5.0),
                
                # Customer Experience
                analysis.get('customer_satisfaction', 5.0),
                analysis.get('user_interaction_sentiment', 5.0),
                analysis.get('customer_effort_score', 5.0),
                analysis.get('wait_time_satisfaction', 5.0),
                
                # Agent Performance
                analysis.get('communication_clarity', 5.0),
                analysis.get('listening_skills', 5.0),
                analysis.get('empathy_emotional_intelligence', 5.0),
                analysis.get('product_service_knowledge', 5.0),
                analysis.get('call_control_flow', 5.0),
                analysis.get('professionalism_courtesy', 5.0),
                
                # Operational Efficiency
                analysis.get('call_handling_efficiency', 5.0),
                analysis.get('information_gathering', 5.0),
                analysis.get('follow_up_commitment', 5.0),
                analysis.get('compliance_adherence', 5.0)
            ))
            
            conn.commit()
            conn.close()
            
            # Emit real-time update with all KPIs
            call_result = {
                'call_id': call_id,
                'timestamp': call_data.get('date', datetime.now().isoformat()),
                'duration': call_data.get('duration', 0),
                'transcript': transcript,
                'category': analysis.get('category', 'other'),
                'summary': analysis.get('summary', ''),
                'sentiment': analysis.get('sentiment', 'neutral'),
                'priority': analysis.get('priority', 2),
                'call_outcome': analysis.get('call_outcome', 'unknown'),
                'overall_score': analysis.get('overall_score', 5.0),
                'kpis': {
                    # Call Success & Resolution
                    'call_success_rate': analysis.get('call_success_rate', 5.0),
                    'first_call_resolution': analysis.get('first_call_resolution', 5.0),
                    'issue_identification': analysis.get('issue_identification', 5.0),
                    'solution_effectiveness': analysis.get('solution_effectiveness', 5.0),
                    
                    # Customer Experience
                    'customer_satisfaction': analysis.get('customer_satisfaction', 5.0),
                    'user_interaction_sentiment': analysis.get('user_interaction_sentiment', 5.0),
                    'customer_effort_score': analysis.get('customer_effort_score', 5.0),
                    'wait_time_satisfaction': analysis.get('wait_time_satisfaction', 5.0),
                    
                    # Agent Performance
                    'communication_clarity': analysis.get('communication_clarity', 5.0),
                    'listening_skills': analysis.get('listening_skills', 5.0),
                    'empathy_emotional_intelligence': analysis.get('empathy_emotional_intelligence', 5.0),
                    'product_service_knowledge': analysis.get('product_service_knowledge', 5.0),
                    'call_control_flow': analysis.get('call_control_flow', 5.0),
                    'professionalism_courtesy': analysis.get('professionalism_courtesy', 5.0),
                    
                    # Operational Efficiency
                    'call_handling_efficiency': analysis.get('call_handling_efficiency', 5.0),
                    'information_gathering': analysis.get('information_gathering', 5.0),
                    'follow_up_commitment': analysis.get('follow_up_commitment', 5.0),
                    'compliance_adherence': analysis.get('compliance_adherence', 5.0)
                }
            }
            
            socketio.emit('new_call', call_result)
            logger.info(f"Successfully processed and broadcasted call {call_id}")
            
        except Exception as e:
            logger.error(f"Error processing call {call_id}: {e}")

    def start_monitoring(self):
        """Start monitoring for new calls"""
        self.is_monitoring = True
        logger.info("🎯 STARTING LIVE CALL MONITORING...")
        
        while self.is_monitoring:
            try:
                # Check if we're still logged in
                if not self.session_token:
                    logger.warning("🔑 NO SESSION TOKEN - ATTEMPTING LOGIN...")
                    if not self.login(self._xelion_username):
                        logger.error("❌ LOGIN FAILED - RETRYING IN 60s")
                        time.sleep(60)
                        continue
                
                logger.info("🔍 CHECKING FOR NEW CALLS...")
                recent_calls = self.get_recent_calls(minutes_back=10)  # Check last 10 minutes
                
                logger.info(f"📊 FOUND {len(recent_calls)} NEW CALLS")
                
                if len(recent_calls) == 0:
                    logger.info("💤 NO NEW CALLS FOUND - SLEEPING 30s")
                else:
                    logger.info(f"🚀 PROCESSING {len(recent_calls)} CALLS")
                
                for call_data in recent_calls:
                    # Process each call in a separate thread
                    thread = threading.Thread(target=self.process_call, args=(call_data,))
                    thread.daemon = True
                    thread.start()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ ERROR IN MONITORING: {e}")
                import traceback
                logger.error(f"💥 FULL ERROR: {traceback.format_exc()}")
                
                # Try to re-login on error
                logger.info("🔄 ATTEMPTING RE-LOGIN AFTER ERROR...")
                self.login(self._xelion_username)
                
                time.sleep(60)  # Wait longer on error

# Initialize monitor
monitor = LiveCallMonitor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/calls')
def get_calls():
    """Get recent calls from database with all KPIs"""
    limit = request.args.get('limit', 20, type=int)
    
    conn = sqlite3.connect('calls.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT call_id, timestamp, duration, transcript, category, summary, sentiment, priority, call_outcome, overall_score, agent_id,
               call_success_rate, first_call_resolution, issue_identification, solution_effectiveness,
               customer_satisfaction, user_interaction_sentiment, customer_effort_score, wait_time_satisfaction,
               communication_clarity, listening_skills, empathy_emotional_intelligence, product_service_knowledge,
               call_control_flow, professionalism_courtesy, call_handling_efficiency, information_gathering,
               follow_up_commitment, compliance_adherence, processed_at
        FROM calls 
        ORDER BY processed_at DESC 
        LIMIT ?
    ''', (limit,))
    
    calls = []
    for row in cursor.fetchall():
        calls.append({
            'call_id': row[0],
            'timestamp': row[1],
            'duration': row[2],
            'transcript': row[3],
            'category': row[4],
            'summary': row[5],
            'sentiment': row[6],
            'priority': row[7],
            'call_outcome': row[8],
            'overall_score': row[9],
            'agent_id': row[10],
            'processed_at': row[29],
            'kpis': {
                # Call Success & Resolution
                'call_success_rate': row[11],
                'first_call_resolution': row[12],
                'issue_identification': row[13],
                'solution_effectiveness': row[14],
                
                # Customer Experience
                'customer_satisfaction': row[15],
                'user_interaction_sentiment': row[16],
                'customer_effort_score': row[17],
                'wait_time_satisfaction': row[18],
                
                # Agent Performance
                'communication_clarity': row[19],
                'listening_skills': row[20],
                'empathy_emotional_intelligence': row[21],
                'product_service_knowledge': row[22],
                'call_control_flow': row[23],
                'professionalism_courtesy': row[24],
                
                # Operational Efficiency
                'call_handling_efficiency': row[25],
                'information_gathering': row[26],
                'follow_up_commitment': row[27],
                'compliance_adherence': row[28]
            }
        })
    
    conn.close()
    return jsonify({'calls': calls})

@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics with KPI averages"""
    conn = sqlite3.connect('calls.db')
    cursor = conn.cursor()
    
    # Get basic counts
    cursor.execute('SELECT COUNT(*) FROM calls')
    total_calls = cursor.fetchone()[0]
    
    cursor.execute('SELECT category, COUNT(*) FROM calls GROUP BY category')
    category_counts = dict(cursor.fetchall())
    
    cursor.execute('SELECT sentiment, COUNT(*) FROM calls GROUP BY sentiment')
    sentiment_counts = dict(cursor.fetchall())
    
    cursor.execute('SELECT call_outcome, COUNT(*) FROM calls GROUP BY call_outcome')
    outcome_counts = dict(cursor.fetchall())
    
    cursor.execute('SELECT AVG(duration) FROM calls WHERE duration > 0')
    avg_duration = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT AVG(priority) FROM calls')
    avg_priority = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT AVG(overall_score) FROM calls')
    avg_overall_score = cursor.fetchone()[0] or 0
    
    # Get KPI averages
    kpi_fields = [
        'call_success_rate', 'first_call_resolution', 'issue_identification', 'solution_effectiveness',
        'customer_satisfaction', 'user_interaction_sentiment', 'customer_effort_score', 'wait_time_satisfaction',
        'communication_clarity', 'listening_skills', 'empathy_emotional_intelligence', 'product_service_knowledge',
        'call_control_flow', 'professionalism_courtesy', 'call_handling_efficiency', 'information_gathering',
        'follow_up_commitment', 'compliance_adherence'
    ]
    
    kpi_averages = {}
    for kpi in kpi_fields:
        cursor.execute(f'SELECT AVG({kpi}) FROM calls WHERE {kpi} IS NOT NULL')
        kpi_averages[kpi] = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'total_calls': total_calls,
        'category_counts': category_counts,
        'sentiment_counts': sentiment_counts,
        'outcome_counts': outcome_counts,
        'avg_duration': round(avg_duration, 1),
        'avg_priority': round(avg_priority, 1),
        'avg_overall_score': round(avg_overall_score, 1),
        'kpi_averages': {k: round(v, 1) for k, v in kpi_averages.items()},
        'successful_calls': outcome_counts.get('success', 0),
        'failed_calls': outcome_counts.get('failure', 0),
        'success_rate': round((outcome_counts.get('success', 0) / max(total_calls, 1)) * 100, 1),
        'positive_interactions': sentiment_counts.get('positive', 0),
        'negative_interactions': sentiment_counts.get('negative', 0),
        'neutral_interactions': sentiment_counts.get('neutral', 0)
    })

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected to WebSocket')
    emit('status', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected from WebSocket')

def start_background_monitoring():
    """Start monitoring in background thread"""
    logger.info("🚀 STARTING BACKGROUND MONITORING THREAD...")
    monitor_thread = threading.Thread(target=monitor.start_monitoring)
    monitor_thread.daemon = True
    monitor_thread.start()
    logger.info("✅ BACKGROUND MONITORING THREAD STARTED")

if __name__ == '__main__':
    logger.info("🎯 INITIALIZING LIVE CALL MONITOR...")
    
    # Start background monitoring
    start_background_monitoring()
    
    logger.info("🌐 STARTING FLASK WEB SERVER...")
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
