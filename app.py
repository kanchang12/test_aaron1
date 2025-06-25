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

# Store conversation state
conversations = {}

def generate_ai_response(user_input, call_sid):
    if not openai_client:
        return "I'm having technical difficulties. A recruiter will call you back soon."
    
    # Get conversation history
    if call_sid not in conversations:
        conversations[call_sid] = []
    
    conversations[call_sid].append(f"User: {user_input}")
    
    # Build conversation context
    context = "\n".join(conversations[call_sid][-6:])  # Last 6 exchanges
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are Sarah from Field Services Nationwide. You're having a phone conversation about a Senior Network Technician job in Chicago paying $75/hour.

IMPORTANT: Keep the conversation going! Always end with a question or statement that invites a response.

Job details:
- Position: Senior Network Technician  
- Location: Chicago, IL
- Pay: $75/hour
- Full-time with benefits
- Requires: Network troubleshooting, router/switch configuration
- Start date: ASAP

Conversation flow:
1. If interested → Ask about their experience
2. If they have experience → Ask about availability  
3. If available → Get their email and confirm recruiter callback
4. If not interested → Thank them politely and end

Keep responses under 25 words. Always ask a follow-up question unless they're clearly not interested."""},
                {"role": "user", "content": f"Conversation so far:\n{context}\n\nUser just said: {user_input}"}
            ],
            max_tokens=80,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content if response.choices else "Tell me more about your background."
        conversations[call_sid].append(f"AI: {ai_response}")
        return ai_response
        
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Tell me about your networking experience."

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
    
    welcome = "Hello! This is Sarah from Field Services Nationwide. I'm calling about a Senior Network Technician position in Chicago that pays $75 per hour. Are you interested in hearing more about this opportunity?"
    
    response.say(welcome, voice='alice')
    
    # Gather speech input
    gather = response.gather(
        input='speech',
        timeout=12,
        speech_timeout='auto',
        action='/handle_speech?call_sid=' + call_sid,
        method='POST'
    )
    
    # Fallback if no response
    response.say("I didn't hear a response. I'll have a recruiter call you back later. Have a great day!")
    response.hangup()
    
    return str(response)

@app.route('/handle_speech', methods=['POST'])
def handle_speech():
    call_sid = request.args.get('call_sid')
    speech_result = request.values.get('SpeechResult', '').strip()
    
    logger.info(f"Speech from {call_sid}: '{speech_result}'")
    
    response = VoiceResponse()
    
    if not speech_result:
        response.say("I didn't catch that. What's your experience with networking?")
        # Keep conversation going even if no speech detected
        gather = response.gather(
            input='speech',
            timeout=10,
            speech_timeout='auto',
            action='/handle_speech?call_sid=' + call_sid,
            method='POST'
        )
        response.say("Thank you for your time!")
        response.hangup()
        return str(response)
    
    # Generate AI response with conversation context
    ai_response = generate_ai_response(speech_result, call_sid)
    response.say(ai_response, voice='alice')
    
    user_lower = speech_result.lower()
    
    # Only end conversation if explicitly not interested
    if any(phrase in user_lower for phrase in ['not interested', 'no thanks', 'stop calling', 'remove me', 'not looking']):
        response.say("No problem! Have a great day!")
        response.hangup()
    else:
        # CONTINUE CONVERSATION - this is the key!
        gather = response.gather(
            input='speech',
            timeout=15,
            speech_timeout='auto', 
            action='/handle_speech?call_sid=' + call_sid,
            method='POST'
        )
        # Fallback only after timeout
        response.say("Thanks for your time! A recruiter will call you back with next steps.")
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
