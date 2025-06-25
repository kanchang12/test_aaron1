#!/usr/bin/env python3
import os
import logging
from flask import Flask, request, jsonify, render_template
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# ElevenLabs voice - EXACT voice you want, natural settings
VOICE_CONFIG = "g6xIsTj2HwM6VR4iXFCw-turbo_v2_5-0.9_0.7_0.9"  # Natural speed, stable, similar

# Initialize clients
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("✅ Twilio initialized")
except:
    twilio_client = None
    logger.error("❌ Twilio failed")

try:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ OpenAI initialized")
except:
    openai_client = None
    logger.error("❌ OpenAI failed")

# Store conversation state
conversations = {}

def generate_ai_response(user_input, call_sid):
    # Pre-built fast responses - no API delay!
    responses = {
        'interested': "Great! How many years experience do you have?",
        'yes': "Awesome! What's your networking background?", 
        'experience': "Perfect! Are you available to start soon?",
        'available': "Excellent! What's your email address?",
        'email': "Thanks! Recruiter calls you tomorrow morning!",
        'default': "Tell me about your experience?"
    }
    
    user_lower = user_input.lower()
    
    if any(word in user_lower for word in ['interested', 'yes', 'sure', 'tell me']):
        return responses['interested']
    elif any(word in user_lower for word in ['year', 'experience', 'network', 'tech']):
        return responses['available']
    elif any(word in user_lower for word in ['available', 'start', 'soon', 'ready']):
        return responses['email']
    elif '@' in user_lower or 'email' in user_lower:
        return responses['email']
    else:
        return responses['default']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/make_call', methods=['POST'])
def make_call():
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return jsonify({'error': 'Phone number required'}), 400
            
        if not twilio_client:
            return jsonify({'error': 'Twilio not configured'}), 500
        
        call = twilio_client.calls.create(
            url=request.url_root + 'voice_webhook',
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            timeout=30
        )
        
        logger.info(f"Call initiated to {phone_number}, SID: {call.sid}")
        
        return jsonify({
            'success': True,
            'call_sid': call.sid,
            'message': f'Call initiated to {phone_number}'
        })
        
    except Exception as e:
        logger.error(f"Call failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/voice_webhook', methods=['GET', 'POST'])
def voice_webhook():
    call_sid = request.values.get('CallSid')
    logger.info(f"Voice webhook for {call_sid}")
    
    response = VoiceResponse()
    
    welcome = "Hi! This is Sarah from Field Services. I have a network technician job in Chicago paying seventy five dollars per hour. Are you interested?"
    
    # Use JUST your voice ID - let ElevenLabs use default natural settings
    response.say(welcome, ttsProvider="ElevenLabs", voice="g6xIsTj2HwM6VR4iXFCw")
    
    # Minimal timeout for instant response
    gather = response.gather(
        input='speech',
        timeout=4,
        speech_timeout=2,
        action='/handle_speech?call_sid=' + call_sid,
        method='POST'
    )
    
    response.say("I'll call back later!", ttsProvider="ElevenLabs", voice="g6xIsTj2HwM6VR4iXFCw")
    response.hangup()
    
    return str(response)

@app.route('/handle_speech', methods=['POST'])
def handle_speech():
    call_sid = request.args.get('call_sid')
    speech_result = request.values.get('SpeechResult', '').strip()
    
    logger.info(f"Speech from {call_sid}: '{speech_result}'")
    
    response = VoiceResponse()
    
    # INSTANT response - no delays!
    ai_response = generate_ai_response(speech_result, call_sid)
    
    # Use your exact voice ID with no modifications
    response.say(ai_response, ttsProvider="ElevenLabs", voice="g6xIsTj2HwM6VR4iXFCw")
    
    user_lower = speech_result.lower()
    
    # Only end if explicitly not interested
    if any(phrase in user_lower for phrase in ['not interested', 'no thanks', 'stop', 'remove', 'busy']):
        response.say("No problem! Have a great day!", ttsProvider="ElevenLabs", voice="g6xIsTj2HwM6VR4iXFCw")
        response.hangup()
    else:
        # Continue with minimal timeout
        gather = response.gather(
            input='speech',
            timeout=4,
            speech_timeout=2,
            action='/handle_speech?call_sid=' + call_sid,
            method='POST'
        )
        response.say("Thanks for your time!", ttsProvider="ElevenLabs", voice="g6xIsTj2HwM6VR4iXFCw")
        response.hangup()
    
    return str(response)

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'twilio_configured': twilio_client is not None,
        'openai_configured': openai_client is not None
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
