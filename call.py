#!/usr/bin/env python3
"""
AI Calling System - Backend Only
Works with your existing HTML templates
"""

import os
import random
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None

# Store call data in memory
call_sessions = {}

# ==================== OPENAI INTEGRATION ====================

def call_openai_api(prompt, model="gpt-4o-mini"):
    """Call OpenAI API to generate AI response."""
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set.")
        return "Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity."

    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are Sarah, a professional recruiter from Field Services Nationwide. Keep responses under 30 seconds when spoken. Be friendly and professional."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "max_tokens": 150,
        "temperature": 0.7
    }

    try:
        logger.info(f"Calling OpenAI API with prompt: '{prompt[:100]}...'")
        response = requests.post(api_url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        
        json_response = response.json()
        if json_response and json_response.get('choices'):
            generated_text = json_response['choices'][0]['message']['content']
            logger.info(f"OpenAI response: '{generated_text[:100]}...'")
            return generated_text
        else:
            logger.warning(f"OpenAI API returned unexpected format: {json_response}")
            return "Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity."
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return "Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity."

# ==================== CALLING FUNCTIONS ====================

def make_ai_call(phone_number, job_info):
    """Make AI call - generates AI response first, then makes call with TwiML."""
    
    logger.info(f"Making call to {phone_number}")
    
    try:
        # STEP 1: Generate AI response FIRST
        ai_prompt = (
            f"Introduce yourself as Sarah from Field Services Nationwide. "
            f"You're calling about a {job_info.get('category', 'IT')} job opportunity "
            f"in {job_info.get('city', 'Colorado Springs')}, {job_info.get('state', 'Colorado')} "
            f"paying ${job_info.get('pay_rate', 35)}/hour "
            f"requiring {job_info.get('skills', 'IT skills')}. "
            f"Ask if they're available to chat briefly. Keep it under 30 seconds."
        )
        
        ai_greeting = call_openai_api(ai_prompt)
        print(f"AI Generated Greeting: {ai_greeting}")
        
        # STEP 2: Create TwiML with AI response
        twiml_response = f"""
        <Response>
            <Say voice="alice">{ai_greeting}</Say>
            <Gather input="speech" speechTimeout="auto" actionOnEmptyResult="true" 
                    action="{request.url_root}handle_response" method="POST">
                <Say voice="alice">Please let me know if you're interested.</Say>
            </Gather>
            <Say voice="alice">Thank you for your time. A recruiter will contact you soon.</Say>
        </Response>
        """
        
        print(f"Generated TwiML: {twiml_response}")
        
        # Generate unique call ID
        call_id = f"call_{random.randint(1000, 9999)}"
        
        # Store call session data
        call_sessions[call_id] = {
            'phone': phone_number,
            'job_info': job_info,
            'greeting': ai_greeting,
            'conversation': [f"AI: {ai_greeting}"],
            'status': 'initiated'
        }

        # STEP 3: Make call with complete TwiML
        if twilio_client and TWILIO_PHONE_NUMBER:
            call = twilio_client.calls.create(
                twiml=twiml_response,
                to=phone_number,
                from_=TWILIO_PHONE_NUMBER,
            )
            
            call_sessions[call_id]['twilio_sid'] = call.sid
            call_sessions[call_id]['status'] = 'calling'
            
            print(f"Call initiated successfully!")
            print(f"Call SID: {call.sid}")
            print(f"To: {call.to}")
            print(f"From: {call.from_}")
            
            logger.info(f"Twilio call initiated. SID: {call.sid}")
            
            return {
                'success': True,
                'call_id': call_id,
                'twilio_sid': call.sid,
                'phone': phone_number,
                'status': 'calling',
                'greeting': ai_greeting
            }
        else:
            # Simulate call for testing without Twilio
            call_sessions[call_id]['status'] = 'simulated'
            
            print("SIMULATED CALL - Twilio not configured")
            return {
                'success': True,
                'call_id': call_id,
                'phone': phone_number,
                'status': 'simulated',
                'greeting': ai_greeting
            }
            
    except Exception as e:
        logger.error(f"Error making call: {e}")
        return {
            'success': False,
            'error': str(e),
            'phone': phone_number
        }

# ==================== API ROUTES ====================

@app.route('/make_call', methods=['POST'])
def api_make_call():
    """API endpoint to initiate AI call."""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        job_info = data.get('job_info', {})
        
        if not phone_number:
            return jsonify({'success': False, 'error': 'Phone number required'}), 400
        
        result = make_ai_call(phone_number, job_info)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in api_make_call: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/call_logs', methods=['GET'])
def get_call_logs():
    """Get all call session data."""
    return jsonify(call_sessions)

@app.route('/handle_response', methods=['POST'])
def handle_response():
    """Handle user speech response."""
    try:
        speech_result = request.form.get('SpeechResult', '')
        call_sid = request.form.get('CallSid')
        
        logger.info(f"User response: '{speech_result}' from call: {call_sid}")
        
        # Find call session by Twilio SID
        call_id = None
        for cid, session in call_sessions.items():
            if session.get('twilio_sid') == call_sid:
                call_id = cid
                break
        
        if call_id:
            # Update conversation history
            call_sessions[call_id]['conversation'].append(f"User: {speech_result}")
            
            # Simple response logic
            response = VoiceResponse()
            
            if any(word in speech_result.lower() for word in ['yes', 'interested', 'available']):
                call_sessions[call_id]['status'] = 'interested'
                response.say("Excellent! A recruiter will contact you within 24 hours to discuss the details. Thank you!")
            elif any(word in speech_result.lower() for word in ['no', 'not interested', 'busy']):
                call_sessions[call_id]['status'] = 'not_interested'
                response.say("No problem at all. Thank you for your time and have a great day!")
            else:
                call_sessions[call_id]['status'] = 'callback'
                response.say("Thank you for the response. Someone will follow up with you soon. Have a great day!")
            
            response.hangup()
            return str(response)
        
        # Fallback response
        response = VoiceResponse()
        response.say("Thank you for your time. Have a great day!")
        response.hangup()
        return str(response)
        
    except Exception as e:
        logger.error(f"Error in handle_response: {e}")
        response = VoiceResponse()
        response.say("Thank you for your time. Have a great day!")
        response.hangup()
        return str(response)

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'twilio_configured': bool(twilio_client),
        'openai_configured': bool(OPENAI_API_KEY)
    })

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    print("🚀 Starting AI Calling System...")
    print(f"Twilio configured: {bool(twilio_client)}")
    print(f"OpenAI configured: {bool(OPENAI_API_KEY)}")
    
    if not twilio_client:
        print("⚠️  Twilio not configured - calls will be simulated")
    if not OPENAI_API_KEY:
        print("⚠️  OpenAI not configured - using fallback messages")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
