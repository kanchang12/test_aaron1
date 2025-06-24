#!/usr/bin/env python3
"""
call.py - ONLY calling functions extracted from your app.py
"""

import os
import json
import logging
import requests
from twilio.rest import Client
from flask import url_for

# Get logger
logger = logging.getLogger(__name__)

# Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None

def call_openai_api(prompt, model="gpt-4o-mini"):
    """
    Calls the OpenAI API to generate text based on a prompt.
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set. Cannot call OpenAI API. Using fallback message.")
        return "I am sorry, I cannot generate a response right now due to an internal configuration issue."

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
                "content": "You are Sarah, a professional AI assistant from Field Services Nationwide. Keep responses conversational, under 30 seconds when spoken, and focused on determining job interest and availability."
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
            logger.info(f"OpenAI API response (first 100 chars): '{generated_text[:100]}...'")
            return generated_text
        else:
            logger.warning(f"OpenAI API returned no choices or unexpected format: {json_response}")
            return "I am sorry, I couldn't generate a coherent response from the AI."
    except requests.exceptions.Timeout:
        logger.error("OpenAI API call timed out.")
        return "I am sorry, the AI is taking too long to respond. Please try again."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return f"I am sorry, there was a problem with the AI service: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error processing OpenAI API response: {e}")
        return "I am sorry, an unexpected internal error occurred with the AI."

def make_ai_call(campaign, tech_data):
    """Hybrid approach - pre-generate first message, dynamic for rest."""
    from app import db, CallLog  # Import here to avoid circular imports
    
    tech = tech_data['technician']
    
    try:
        # Create call log
        call_log = CallLog(
            campaign_id=campaign.id,
            technician_id=tech.id,
            phone_number=tech.mobile_phone,
            call_status='initiated',
            distance_miles=tech_data['distance']
        )
        db.session.add(call_log)
        db.session.commit()

        # PRE-GENERATE ONLY THE FIRST MESSAGE
        work_order = campaign.work_order
        required_skills = ", ".join(work_order.required_skills) if work_order.required_skills else "IT skills"
        
        ai_prompt = (
            f"Introduce yourself as Sarah from Field Services Nationwide. "
            f"You're calling {tech.name} about a {work_order.job_category} job opportunity "
            f"in {work_order.job_city}, {work_order.job_state} paying ${work_order.pay_rate}/hour "
            f"requiring {required_skills}. Ask if they're available to chat briefly. "
            f"Keep it under 20 seconds."
        )
        
        initial_greeting = call_openai_api(ai_prompt)
        if not initial_greeting:
            initial_greeting = f"Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity. Are you available to chat?"
        
        # Store initial message and job context for later use
        job_context = {
            'technician_name': tech.name,
            'job_category': work_order.job_category,
            'job_city': work_order.job_city,
            'job_state': work_order.job_state,
            'pay_rate': work_order.pay_rate,
            'required_skills': required_skills,
            'description': work_order.description
        }
        
        call_log.ai_conversation = json.dumps({
            'initial_greeting': initial_greeting,
            'job_context': job_context,
            'conversation_history': [f"AI: {initial_greeting}"]
        })
        db.session.commit()

        # Make call with webhook for DYNAMIC conversation
        if twilio_client and TWILIO_PHONE_NUMBER:
            try:
                call = twilio_client.calls.create(
                    url=url_for('twilio_voice_webhook', _external=True, call_log_id=call_log.id),
                    to=tech.mobile_phone,
                    from_=TWILIO_PHONE_NUMBER
                )
                call_log.twilio_call_sid = call.sid
                call_log.call_status = 'ringing'
                db.session.commit()
                
                logger.info(f"Twilio call initiated. SID: {call.sid}")
                
            except Exception as e:
                call_log.call_status = 'failed_twilio_api'
                call_log.call_result = 'error'
                db.session.commit()
                logger.error(f"Twilio call failed: {e}")
                
                return {
                    'call_log_id': call_log.id,
                    'technician_id': tech.id,
                    'name': tech.name,
                    'phone': tech.mobile_phone,
                    'call_status': 'failed_twilio_api',
                    'call_result': 'error',
                    'error': str(e)
                }
        
        return {
            'call_log_id': call_log.id,
            'technician_id': tech.id,
            'name': tech.name,
            'phone': tech.mobile_phone,
            'call_status': call_log.call_status,
            'call_result': 'pending',
            'distance': tech_data['distance'],
            'twilio_call_sid': call_log.twilio_call_sid
        }
        
    except Exception as e:
        logger.error(f"Error making call to {tech.name}: {e}")
        return {'error': str(e)}
