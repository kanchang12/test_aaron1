#!/usr/bin/env python3
"""
Standalone Twilio Call Tester with Continuous Conversation
Run this separately to test calling functionality
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Say, Gather, Hangup
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret-key'

# Configuration - Add your credentials here
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', 'your_account_sid_here')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', 'your_auth_token_here')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '+1234567890')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your_openai_api_key_here')

# Initialize clients
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Twilio client: {e}")
    twilio_client = None

try:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    openai_client = None

# Store conversation state in memory (use database in production)
conversations = {}

class ConversationManager:
    def __init__(self, call_sid):
        self.call_sid = call_sid
        self.conversation_history = []
        self.context = {
            'job_title': 'Senior Network Technician',
            'job_location': 'Chicago, IL',
            'pay_rate': '$75',
            'company': 'Field Services Nationwide'
        }
        
    def add_message(self, speaker, message):
        timestamp = datetime.now().isoformat()
        self.conversation_history.append({
            'timestamp': timestamp,
            'speaker': speaker,
            'message': message
        })
        logger.info(f"[{self.call_sid}] {speaker}: {message}")
    
    def get_conversation_context(self):
        recent_messages = self.conversation_history[-6:]  # Last 6 messages for context
        context_text = ""
        for msg in recent_messages:
            context_text += f"{msg['speaker']}: {msg['message']}\n"
        return context_text

def get_conversation_manager(call_sid):
    if call_sid not in conversations:
        conversations[call_sid] = ConversationManager(call_sid)
    return conversations[call_sid]

def generate_ai_response(user_input, conversation_manager):
    """Generate AI response using OpenAI with conversation context"""
    if not openai_client:
        return "I'm sorry, I'm having technical difficulties. A recruiter will call you back soon."
    
    try:
        context = conversation_manager.context
        conversation_history = conversation_manager.get_conversation_context()
        
        system_prompt = f"""You are Sarah, a professional AI recruiter from {context['company']}. 

Current job details:
- Position: {context['job_title']}
- Location: {context['job_location']} 
- Pay Rate: {context['pay_rate']}/hour

Conversation history:
{conversation_history}

Guidelines:
- Keep responses under 30 seconds when spoken
- Be conversational and friendly
- Focus on gauging interest and availability
- Ask relevant follow-up questions
- If they're interested, tell them a recruiter will call within 1 hour
- If not interested, thank them and end politely
- Keep responses concise and natural
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Technician just said: {user_input}"}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        if response.choices:
            ai_message = response.choices[0].message.content
            return ai_message
        else:
            return "I understand. Let me have a recruiter follow up with you soon."
            
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "I'm having some technical issues. A recruiter will call you back within the hour."

def should_end_conversation(user_input, ai_response):
    """Determine if conversation should end based on user input and AI response"""
    user_lower = user_input.lower()
    ai_lower = ai_response.lower()
    
    # End conversation triggers
    end_phrases = [
        'not interested', 'no thanks', 'not available', 'busy', 'goodbye', 
        'hang up', 'stop calling', 'remove me', 'don\'t call'
    ]
    
    continue_phrases = [
        'tell me more', 'interested', 'yes', 'sounds good', 'when', 'where', 
        'how much', 'what time', 'details'
    ]
    
    # AI indicating end
    ai_end_phrases = [
        'recruiter will call', 'thank you for your time', 'have a great day',
        'we\'ll be in touch', 'goodbye'
    ]
    
    # Check if AI is ending
    if any(phrase in ai_lower for phrase in ai_end_phrases):
        return True
    
    # Check user intent
    if any(phrase in user_lower for phrase in end_phrases):
        return True
    
    # Continue if user shows interest
    if any(phrase in user_lower for phrase in continue_phrases):
        return False
    
    # Default: continue conversation (max 6 exchanges handled elsewhere)
    return False

@app.route('/')
def index():
    """Render test interface"""
    return render_template_string(open('call.html', 'r').read())

@app.route('/make_test_call', methods=['POST'])
def make_test_call():
    """Make a test call to specified number"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return jsonify({'error': 'Phone number required'}), 400
            
        if not twilio_client:
            return jsonify({'error': 'Twilio client not configured'}), 500
        
        # Make the call
        call = twilio_client.calls.create(
            url=f'http://{request.host}/voice_webhook',
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            timeout=45,
            record=False,
            machine_detection='DetectMessageEnd',
            machine_detection_timeout=10
        )
        
        logger.info(f"Test call initiated to {phone_number}, SID: {call.sid}")
        
        return jsonify({
            'success': True,
            'call_sid': call.sid,
            'message': f'Call initiated to {phone_number}'
        })
        
    except Exception as e:
        logger.error(f"Error making test call: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/voice_webhook', methods=['GET', 'POST'])
def voice_webhook():
    """Handle incoming voice webhook - start conversation"""
    call_sid = request.values.get('CallSid')
    call_status = request.values.get('CallStatus')
    
    logger.info(f"Voice webhook: CallSid={call_sid}, Status={call_status}, Method={request.method}")
    
    response = VoiceResponse()
    
    try:
        # Get or create conversation manager
        conv_manager = get_conversation_manager(call_sid)
        
        if request.method == 'GET' or call_status in ['ringing', 'in-progress']:
            # Initial call - start conversation
            welcome_message = (
                "Hello! This is Sarah from Field Services Nationwide. "
                "I'm calling about a Senior Network Technician position in Chicago "
                "paying $75 per hour. Is this a good time to chat for just a minute?"
            )
            
            conv_manager.add_message("AI", welcome_message)
            
            # Speak the message
            response.say(welcome_message, voice='alice', language='en-US')
            
            # Gather response with proper settings
            gather = response.gather(
                input='speech',
                timeout=10,
                speech_timeout='auto',
                action=f'/handle_speech?call_sid={call_sid}',
                method='POST',
                partial_result_callback=f'/partial_speech?call_sid={call_sid}'
            )
            
            # Fallback if no response
            response.say("I didn't hear a response. I'll have a recruiter call you back later. Have a great day!", voice='alice')
            response.hangup()
            
        else:
            # Status update - just return empty response
            return '', 200
            
    except Exception as e:
        logger.error(f"Error in voice_webhook: {e}")
        response.say("Sorry, there was a technical issue. We'll call you back soon.", voice='alice')
        response.hangup()
    
    return str(response), 200

@app.route('/partial_speech', methods=['POST'])
def partial_speech():
    """Handle partial speech results to keep call alive"""
    call_sid = request.values.get('CallSid')
    partial_result = request.values.get('PartialResult', '')
    
    logger.info(f"Partial speech from {call_sid}: '{partial_result}'")
    return '', 200

@app.route('/handle_speech', methods=['POST'])
def handle_speech():
    """Handle complete speech input and generate AI response"""
    call_sid = request.values.get('CallSid')
    speech_result = request.values.get('SpeechResult', '').strip()
    
    logger.info(f"Complete speech from {call_sid}: '{speech_result}'")
    
    response = VoiceResponse()
    
    try:
        if not speech_result:
            # No speech detected
            response.say("I didn't catch that. Let me have a recruiter call you back. Thank you!", voice='alice')
            response.hangup()
            return str(response), 200
        
        # Get conversation manager
        conv_manager = get_conversation_manager(call_sid)
        
        # Add user message to conversation
        conv_manager.add_message("Technician", speech_result)
        
        # Check if we've had too many exchanges (prevent infinite loops)
        if len(conv_manager.conversation_history) > 12:  # Max 6 exchanges
            response.say("Thank you for your time! A recruiter will follow up with you soon. Have a great day!", voice='alice')
            response.hangup()
            return str(response), 200
        
        # Generate AI response
        ai_response = generate_ai_response(speech_result, conv_manager)
        conv_manager.add_message("AI", ai_response)
        
        # Determine if conversation should end
        should_end = should_end_conversation(speech_result, ai_response)
        
        # Speak AI response
        response.say(ai_response, voice='alice', language='en-US')
        
        if should_end:
            # End conversation
            response.hangup()
        else:
            # Continue conversation
            gather = response.gather(
                input='speech',
                timeout=8,
                speech_timeout='auto',
                action=f'/handle_speech?call_sid={call_sid}',
                method='POST'
            )
            
            # Fallback if no response
            response.say("Thank you for your time. A recruiter will be in touch soon!", voice='alice')
            response.hangup()
        
    except Exception as e:
        logger.error(f"Error handling speech: {e}")
        response.say("Thank you for your time. We'll follow up soon!", voice='alice')
        response.hangup()
    
    return str(response), 200

@app.route('/get_conversation/<call_sid>')
def get_conversation(call_sid):
    """Get conversation history for a specific call"""
    if call_sid in conversations:
        conv_manager = conversations[call_sid]
        return jsonify({
            'call_sid': call_sid,
            'conversation_history': conv_manager.conversation_history,
            'context': conv_manager.context
        })
    else:
        return jsonify({'error': 'Conversation not found'}), 404

@app.route('/active_conversations')
def active_conversations():
    """Get list of active conversations"""
    active_calls = []
    for call_sid, conv_manager in conversations.items():
        active_calls.append({
            'call_sid': call_sid,
            'message_count': len(conv_manager.conversation_history),
            'last_message': conv_manager.conversation_history[-1] if conv_manager.conversation_history else None
        })
    
    return jsonify({'active_conversations': active_calls})

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'twilio_configured': twilio_client is not None,
        'openai_configured': openai_client is not None,
        'active_conversations': len(conversations)
    })

if __name__ == '__main__':
    # Configuration check
    if TWILIO_ACCOUNT_SID == 'your_account_sid_here':
        print("⚠️  WARNING: Please set your Twilio credentials in environment variables or update the code")
        print("   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
    
    if OPENAI_API_KEY == 'your_openai_api_key_here':
        print("⚠️  WARNING: Please set your OpenAI API key in environment variables or update the code")
        print("   OPENAI_API_KEY")
    
    print("🚀 Starting Twilio Call Tester...")
    print("📞 Make sure your webhook URL is accessible (use ngrok for local testing)")
    print("🌐 Access the test interface at: http://localhost:5001")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
