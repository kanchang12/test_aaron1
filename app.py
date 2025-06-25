#!/usr/bin/env python3
import os
import logging
from flask import Flask, request, jsonify, render_template
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

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

def generate_ai_response(user_input):
    if not openai_client:
        return "I'm having technical difficulties. A recruiter will call you back soon."
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Sarah from Field Services Nationwide. Keep responses under 30 seconds. Be conversational about job opportunities."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=100,
            temperature=0.7
        )
        return response.choices[0].message.content if response.choices else "Let me have a recruiter follow up with you."
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "A recruiter will call you back within the hour."

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
    
    welcome = "Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity. Are you interested in hearing more?"
    
    response.say(welcome, voice='alice')
    
    gather = response.gather(
        input='speech',
        timeout=10,
        action='/handle_speech?call_sid=' + call_sid,
        method='POST'
    )
    
    response.say("I didn't hear a response. Have a great day!")
    response.hangup()
    
    return str(response)

@app.route('/handle_speech', methods=['POST'])
def handle_speech():
    call_sid = request.args.get('call_sid')
    speech_result = request.values.get('SpeechResult', '').strip()
    
    logger.info(f"Speech from {call_sid}: '{speech_result}'")
    
    response = VoiceResponse()
    
    if not speech_result:
        response.say("Thank you for your time!")
        response.hangup()
        return str(response)
    
    ai_response = generate_ai_response(speech_result)
    response.say(ai_response, voice='alice')
    
    user_lower = speech_result.lower()
    
    if any(word in user_lower for word in ['yes', 'interested', 'tell me']):
        gather = response.gather(
            input='speech',
            timeout=8,
            action='/handle_speech?call_sid=' + call_sid,
            method='POST'
        )
        response.say("Thank you for your interest! A recruiter will call you soon.")
        response.hangup()
    else:
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
