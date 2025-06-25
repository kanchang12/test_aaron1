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

# ElevenLabs voice with fast settings
VOICE_CONFIG = "g6xIsTj2HwM6VR4iXFCw-turbo_v2_5-1.1_0.5_0.8"  # Fast, clear voice

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
    if not openai_client:
        return "I'm having technical difficulties."
    
    # Get conversation history
    if call_sid not in conversations:
        conversations[call_sid] = []
    
    conversations[call_sid].append(f"User: {user_input}")
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are Sarah from Field Services. Quick phone conversation about a $75/hour network tech job in Chicago.

CRITICAL: Keep responses under 12 words max. Be fast and direct.

Flow:
- Interested? → "Great! How many years networking experience?"
- Experience given → "Perfect! Available to start soon?"  
- Available → "Awesome! What's your email?"
- Email given → "Thanks! Recruiter calls tomorrow!"
- Not interested → "No problem, bye!"

Be conversational but FAST. One quick question per response."""},
                {"role": "user", "content": user_input}
            ],
            max_tokens=25,  # Very short responses
            temperature=0.3  # More focused
        )
        
        ai_response = response.choices[0].message.content if response.choices else "Tell me your experience?"
        conversations[call_sid].append(f"AI: {ai_response}")
        return ai_response
        
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "What's your networking background?"

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
    
    welcome = "Hi! Sarah from Field Services. Network tech job, 75 per hour, Chicago. Interested?"
    
    # Use ElevenLabs voice directly through Twilio - MUCH FASTER!
    response.say(welcome, ttsProvider="ElevenLabs", voice=VOICE_CONFIG)
    
    # Gather speech input with shorter timeout for speed
    gather = response.gather(
        input='speech',
        timeout=6,
        speech_timeout='auto',
        action='/handle_speech?call_sid=' + call_sid,
        method='POST'
    )
    
    # Quick fallback
    response.say("Call you back!", ttsProvider="ElevenLabs", voice=VOICE_CONFIG)
    response.hangup()
    
    return str(response)

@app.route('/handle_speech', methods=['POST'])
def handle_speech():
    call_sid = request.args.get('call_sid')
    speech_result = request.values.get('SpeechResult', '').strip()
    
    logger.info(f"Speech from {call_sid}: '{speech_result}'")
    
    response = VoiceResponse()
    
    if not speech_result:
        quick_response = "What's your experience?"
        response.say(quick_response, ttsProvider="ElevenLabs", voice=VOICE_CONFIG)
            
        gather = response.gather(
            input='speech',
            timeout=5,
            speech_timeout='auto',
            action='/handle_speech?call_sid=' + call_sid,
            method='POST'
        )
        response.say("Thanks!", ttsProvider="ElevenLabs", voice=VOICE_CONFIG)
        response.hangup()
        return str(response)
    
    # Generate FAST AI response
    ai_response = generate_ai_response(speech_result, call_sid)
    
    # Use ElevenLabs voice through Twilio - FAST!
    response.say(ai_response, ttsProvider="ElevenLabs", voice=VOICE_CONFIG)
    
    user_lower = speech_result.lower()
    
    # Only end if explicitly not interested
    if any(phrase in user_lower for phrase in ['not interested', 'no thanks', 'stop', 'remove me', 'busy']):
        goodbye = "No problem, bye!"
        response.say(goodbye, ttsProvider="ElevenLabs", voice=VOICE_CONFIG)
        response.hangup()
    else:
        # Continue conversation with shorter timeout for speed
        gather = response.gather(
            input='speech',
            timeout=6,
            speech_timeout='auto', 
            action='/handle_speech?call_sid=' + call_sid,
            method='POST'
        )
        # Quick fallback
        response.say("Recruiter will call!", ttsProvider="ElevenLabs", voice=VOICE_CONFIG)
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
