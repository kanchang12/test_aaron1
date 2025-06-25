#!/usr/bin/env python3
"""
Field Services Nationwide - AI Calling System
Main Flask Application - FIXED VERSION
"""

import os
import random
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from twilio.rest import Client 
from twilio.twiml.voice_response import VoiceResponse as TwiMLResponse, Say, Gather, Hangup 

# FIXED: Use official OpenAI client instead of direct HTTP requests
from openai import OpenAI

import sqlalchemy 

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from flask_migrate import Migrate
from wtforms import StringField, PasswordField, SelectField, TextAreaField, IntegerField, FloatField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fsn_calling.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Configuration - FIXED: Proper OpenAI client initialization
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Initialize clients - FIXED: Proper error handling
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None
    if not twilio_client:
        logger.warning("Twilio client not initialized - missing credentials")
except Exception as e:
    logger.error(f"Failed to initialize Twilio client: {e}")
    twilio_client = None

try:
    openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    if not openai_client:
        logger.warning("OpenAI client not initialized - missing API key")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    openai_client = None

geolocator = Nominatim(user_agent="fsn_calling_system")

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='sub_account', nullable=False)
    company_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    
    work_orders = db.relationship('WorkOrder', backref='creator', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'

class Technician(db.Model):
    __tablename__ = 'technicians'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), index=True)
    mobile_phone = db.Column(db.String(20), nullable=False, index=True)
    home_phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    city = db.Column(db.String(50), index=True)
    state = db.Column(db.String(20), index=True)
    zip_code = db.Column(db.String(10), index=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    experience_years = db.Column(db.Integer)
    drug_screening = db.Column(db.Boolean, default=False, nullable=False)
    background_check = db.Column(db.Boolean, default=False, nullable=False)
    skills = db.Column(db.JSON)
    tools = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    call_logs = db.relationship('CallLog', backref='technician', lazy=True)

class WorkOrder(db.Model):
    __tablename__ = 'work_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    job_category = db.Column(db.String(100), nullable=False, index=True)
    required_skills = db.Column(db.JSON)
    minimum_skill_level = db.Column(db.Integer, default=5, nullable=False)
    job_city = db.Column(db.String(50), nullable=False)
    job_state = db.Column(db.String(20), nullable=False)
    job_zip = db.Column(db.String(10), nullable=False)
    job_latitude = db.Column(db.Float)
    job_longitude = db.Column(db.Float)
    pay_rate = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.DateTime)
    duration_hours = db.Column(db.Integer, default=4)
    description = db.Column(db.Text)
    requirements = db.Column(db.JSON)
    status = db.Column(db.String(20), default='active', nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    campaigns = db.relationship('CallCampaign', backref='work_order', lazy=True)

class CallCampaign(db.Model):
    __tablename__ = 'call_campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'), nullable=False)
    current_radius = db.Column(db.Integer, default=60, nullable=False)
    target_responses = db.Column(db.Integer, default=5, nullable=False)
    current_responses = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    call_logs = db.relationship('CallLog', backref='campaign', lazy=True)

class CallLog(db.Model):
    __tablename__ = 'call_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('call_campaigns.id'), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    call_status = db.Column(db.String(20), nullable=False, index=True)
    call_result = db.Column(db.String(20), index=True)
    call_duration = db.Column(db.Integer)
    distance_miles = db.Column(db.Float)
    ai_conversation = db.Column(db.Text)
    twilio_call_sid = db.Column(db.String(100))
    called_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        return None

# ==================== FORMS ====================

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    company_name = StringField('Company Name', validators=[Length(max=100)])
    phone = StringField('Phone Number', validators=[Length(max=20)])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])

class WorkOrderForm(FlaskForm):
    job_category = SelectField('Job Category', validators=[DataRequired()], choices=[
        ('', 'Select Category'),
        ('Point of Sale & Retail', 'Point of Sale & Retail'),
        ('Computer & Device Repair', 'Computer & Device Repair'),
        ('Network & Infrastructure', 'Network & Infrastructure'),
        ('Audio/Visual & Security', 'Audio/Visual & Security'),
        ('Server & Data Center', 'Server & Data Center'),
        ('Telecom & Communications', 'Telecom & Communications'),
        ('General Field Services', 'General Field Services')
    ])
    required_skills = StringField('Required Skills (comma separated)')
    minimum_skill_level = SelectField('Minimum Skill Level', validators=[DataRequired()], choices=[
        (5, '5/10 Average'),
        (6, '6/10'),
        (7, '7/10 Good'),
        (8, '8/10 Very Good'),
        (9, '9/10 Expert')
    ], coerce=int)
    job_city = StringField('Job City', validators=[DataRequired(), Length(max=50)])
    job_state = StringField('Job State', validators=[DataRequired(), Length(max=20)])
    job_zip = StringField('Job ZIP Code', validators=[DataRequired(), Length(max=10)])
    pay_rate = FloatField('Pay Rate ($/hour)', validators=[DataRequired(), NumberRange(min=10, max=200)])
    duration_hours = IntegerField('Duration (hours)', validators=[NumberRange(min=1, max=24)], default=4)
    description = TextAreaField('Job Description', validators=[Length(max=1000)])
    drug_screen = BooleanField('Drug Screening Required')
    background_check = BooleanField('Background Check Required')
    min_experience = IntegerField('Minimum Experience (years)', validators=[NumberRange(min=0, max=30)], default=0)

# ==================== OPENAI INTEGRATION - FIXED ====================

def call_openai_api(prompt, model="gpt-4o-mini"):
    """
    FIXED: Uses the official OpenAI client instead of manual HTTP requests
    """
    if not openai_client:
        logger.error("OpenAI client is not initialized. Cannot call OpenAI API.")
        return "I'm sorry, I cannot generate a response right now due to a configuration issue."

    try:
        logger.info(f"Calling OpenAI API with prompt: '{prompt[:100]}...'")
        
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are Sarah, a professional AI assistant from Field Services Nationwide. Keep responses conversational, under 30 seconds when spoken, and focused on determining job interest and availability."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        if response and response.choices:
            generated_text = response.choices[0].message.content
            logger.info(f"OpenAI API response (first 100 chars): '{generated_text[:100]}...'")
            return generated_text
        else:
            logger.warning("OpenAI API returned no choices or unexpected format")
            return "I'm sorry, I couldn't generate a coherent response."
            
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return "I'm sorry, there was a problem with the AI service. Please try again."

# ==================== HELPER FUNCTIONS ====================

def get_coordinates(address_string):
    """FIXED: Better error handling for geocoding."""
    try:
        if not address_string or pd.isna(address_string):
            return None, None
        
        # Clean the address string
        address_string = str(address_string).strip()
        if not address_string:
            return None, None
        
        # FORCE US-ONLY by adding country code
        if ", USA" not in address_string and ", US" not in address_string:
            if address_string.replace('.', '').replace('-', '').isdigit():
                # Just a zip code
                address_string = f"{address_string}, USA"
            else:
                # City/address - add USA
                address_string = f"{address_string}, USA"
        
        # Use countrycodes parameter to restrict to US only
        location = geolocator.geocode(address_string, timeout=10, country_codes=['US'])
        
        if location:
            logger.info(f"Geocoded '{address_string}': Lat {location.latitude}, Lon {location.longitude}")
            return location.latitude, location.longitude
        
        logger.warning(f"Could not geocode US location: '{address_string}'")
        return None, None
        
    except Exception as e:
        logger.error(f"Error geocoding '{address_string}': {e}")
        return None, None

def find_qualified_technicians(work_order, radius_miles, exclude_called_ids=None):
    """FIXED: Better error handling and session management."""
    if exclude_called_ids is None:
        exclude_called_ids = []
    
    logger.info(f"--- Starting qualification check for Work Order: {work_order.work_order_id} ---")
    logger.info(f"Work Order Location: Lat={work_order.job_latitude}, Lon={work_order.job_longitude}, Radius={radius_miles} miles")
    
    try:
        all_techs = Technician.query.filter(Technician.is_active == True).all()
        
        if not all_techs:
            logger.warning("No active technicians found.")
            return [], []

        qualified_pool = []
        potential_technicians_data = []
        
        # FIXED: Check for valid work order coordinates first
        if not work_order.job_latitude or not work_order.job_longitude:
            logger.error(f"Work Order {work_order.work_order_id} has no valid coordinates.")
            return [], []
            
        work_order_location = (work_order.job_latitude, work_order.job_longitude)
        
        for tech in all_techs:
            is_qualified = True
            disqualification_reasons = []
            tech_distance = None

            # Check if already called
            if tech.id in exclude_called_ids:
                is_qualified = False
                disqualification_reasons.append("Already called for this campaign")
            
            # Check coordinates and distance
            if is_qualified:
                if not tech.latitude or not tech.longitude:
                    is_qualified = False
                    disqualification_reasons.append("No valid coordinates")
                else:
                    try:
                        tech_location = (tech.latitude, tech.longitude)
                        tech_distance = geodesic(work_order_location, tech_location).miles
                        
                        if tech_distance > radius_miles:
                            is_qualified = False
                            disqualification_reasons.append(f"Too far ({tech_distance:.1f} miles > {radius_miles} miles)")
                    except Exception as e:
                        is_qualified = False
                        disqualification_reasons.append(f"Error calculating distance: {e}")

            # Check requirements
            if is_qualified:
                reqs = work_order.requirements or {}
                
                if reqs.get('drug_screen', False) and not tech.drug_screening:
                    is_qualified = False
                    disqualification_reasons.append("Fails drug screening requirement")
                
                if reqs.get('background_check', False) and not tech.background_check:
                    is_qualified = False
                    disqualification_reasons.append("Fails background check requirement")
                
                min_exp = reqs.get('min_experience', 0)
                if tech.experience_years is None or tech.experience_years < min_exp:
                    is_qualified = False
                    disqualification_reasons.append(f"Insufficient experience ({tech.experience_years or 0} yrs < {min_exp} yrs)")

            # Check skills
            if is_qualified and work_order.required_skills:
                tech_skills = tech.skills or {}
                for skill in work_order.required_skills:
                    skill_value = tech_skills.get(skill, '0/10')
                    try:
                        if isinstance(skill_value, str) and '/' in skill_value:
                            rating = int(skill_value.split('/')[0])
                        elif isinstance(skill_value, (int, float)):
                            rating = int(skill_value)
                        else:
                            rating = 0
                            
                        if rating < work_order.minimum_skill_level:
                            is_qualified = False
                            disqualification_reasons.append(f"Insufficient skill level for '{skill}' ({rating}/10 < {work_order.minimum_skill_level}/10)")
                            break
                    except (ValueError, TypeError):
                        is_qualified = False
                        disqualification_reasons.append(f"Invalid skill rating for '{skill}'")
                        break

            # Store data for dashboard
            tech_data = {
                'id': tech.id,
                'name': tech.name,
                'mobile_phone': tech.mobile_phone,
                'email': tech.email,
                'address': tech.address,
                'city': tech.city,
                'state': tech.state,
                'zip_code': tech.zip_code,
                'latitude': tech.latitude,
                'longitude': tech.longitude,
                'is_qualified': is_qualified,
                'distance': tech_distance,
                'reasons': ", ".join(disqualification_reasons) if disqualification_reasons else "Qualified"
            }
            potential_technicians_data.append(tech_data)

            if is_qualified:
                qualified_pool.append({
                    'technician': tech,
                    'distance': tech_distance
                })
                logger.info(f"--- QUALIFIED: {tech.name} (ID: {tech.id}), Distance: {tech_distance:.2f} miles ---")
            else:
                logger.info(f"--- DISQUALIFIED: {tech.name} (ID: {tech.id}), Reason(s): {', '.join(disqualification_reasons)} ---")

        logger.info(f"--- Qualification check finished. Total qualified: {len(qualified_pool)} ---")
        return qualified_pool, potential_technicians_data
        
    except Exception as e:
        logger.error(f"Error in find_qualified_technicians: {e}")
        return [], []

def make_ai_call(campaign, tech_data):
    """FIXED: Better error handling and session management."""
    tech = tech_data['technician']
    
    logger.info(f"Making call to {tech.name} ({tech.mobile_phone})")
    
    try:
        # Create call log with better error handling
        call_log = CallLog(
            campaign_id=campaign.id,
            technician_id=tech.id,
            phone_number=tech.mobile_phone,
            call_status='initiated',
            distance_miles=tech_data['distance']
        )
        
        try:
            db.session.add(call_log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create call log: {e}")
            raise

        # Make Twilio call
        if twilio_client and TWILIO_PHONE_NUMBER:
            try:
                call = twilio_client.calls.create(
                    url=url_for('twilio_voice_webhook', _external=True, call_log_id=call_log.id),
                    to=tech.mobile_phone,
                    from_=TWILIO_PHONE_NUMBER,
                    timeout=30,  # FIXED: Add timeout
                    record=False  # FIXED: Disable recording for privacy
                )
                call_log.twilio_call_sid = call.sid
                call_log.call_status = 'ringing'
                db.session.commit()
                
                logger.info(f"Twilio call initiated. SID: {call.sid}")
                
            except Exception as e:
                call_log.call_status = 'failed_twilio_api'
                call_log.call_result = 'error'
                call_log.ai_conversation = f"Twilio error: {str(e)}"
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
        else:
            # Simulate call for testing
            call_log.call_status = 'simulated'
            responses = ['interested', 'not_interested', 'callback', 'unavailable']
            weights = [0.25, 0.45, 0.20, 0.10]
            call_log.call_result = random.choices(responses, weights=weights)[0]
            call_log.call_duration = random.randint(90, 240)
            
            if call_log.call_result == 'interested':
                campaign.current_responses += 1
            
            db.session.commit()
        
        return {
            'call_log_id': call_log.id,
            'technician_id': tech.id,
            'name': tech.name,
            'phone': tech.mobile_phone,
            'call_status': call_log.call_status,
            'call_result': call_log.call_result or 'pending',
            'distance': tech_data['distance'],
            'twilio_call_sid': call_log.twilio_call_sid
        }
        
    except Exception as e:
        logger.error(f"Error making call to {tech.name}: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return {
            'technician_id': tech.id,
            'name': tech.name,
            'phone': tech.mobile_phone,
            'call_status': 'error',
            'call_result': 'error',
            'error': str(e)
        }

# ==================== ROUTES ====================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    try:
        current_user.last_login = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        logger.error(f"Error updating last login: {e}")
        db.session.rollback()

    try:
        if current_user.is_admin():
            recent_orders = WorkOrder.query.order_by(WorkOrder.created_at.desc()).limit(5).all()
            campaign_query = CallCampaign.query.filter_by(status='active')
        else:
            recent_orders = WorkOrder.query.filter_by(created_by=current_user.id).order_by(WorkOrder.created_at.desc()).limit(5).all()
            work_order_ids = [wo.id for wo in WorkOrder.query.filter_by(created_by=current_user.id).all()]
            campaign_query = CallCampaign.query.filter_by(status='active').filter(CallCampaign.work_order_id.in_(work_order_ids))
        
        active_campaigns = campaign_query.all()
        
        stats = {
            'total_technicians': Technician.query.filter_by(is_active=True).count(),
            'total_work_orders': len(recent_orders),
            'active_campaigns': len(active_campaigns),
            'total_calls': CallLog.query.count()
        }
        
        return render_template('dashboard.html', 
                               recent_orders=recent_orders,
                               active_campaigns=active_campaigns,
                               stats=stats)
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        flash('Error loading dashboard. Please try again.', 'error')
        return render_template('dashboard.html', recent_orders=[], active_campaigns=[], stats={})

@app.route('/twilio_voice_webhook', methods=['GET', 'POST'])
def twilio_voice_webhook():
    """FIXED: Better error handling for Twilio webhooks."""
    call_log_id = request.args.get('call_log_id')
    
    try:
        if request.method == 'GET':
            # Call answered - provide TwiML with OpenAI
            logger.info(f"Call answered - providing TwiML for call_log_id: {call_log_id}")
            response = TwiMLResponse()
            
            # Get context for AI
            if call_log_id:
                try:
                    call_log = CallLog.query.get(call_log_id)
                    if call_log:
                        technician = Technician.query.get(call_log.technician_id)
                        campaign = CallCampaign.query.get(call_log.campaign_id)
                        work_order = campaign.work_order if campaign else None
                        
                        # Build AI prompt with context
                        initial_prompt = (
                            "Introduce yourself as Sarah from Field Services Nationwide. "
                            "You're calling about a job opportunity. Keep it brief and ask if they're available to chat. "
                        )
                        
                        if technician and work_order:
                            required_skills = ", ".join(work_order.required_skills) if work_order.required_skills else "IT skills"
                            initial_prompt += (
                                f"The technician's name is {technician.name}. "
                                f"The job is {work_order.job_category} in {work_order.job_city}, {work_order.job_state} "
                                f"paying ${work_order.pay_rate}/hour requiring {required_skills}. "
                            )
                        
                        ai_response = call_openai_api(initial_prompt)
                        if not ai_response:
                            ai_response = "Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity. Are you available to chat?"
                        
                        call_log.ai_conversation = f"AI: {ai_response}"
                        db.session.commit()
                        
                        response.say(ai_response, voice='alice')
                    else:
                        response.say("Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity.", voice='alice')
                except Exception as e:
                    logger.error(f"Error getting call context: {e}")
                    response.say("Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity.", voice='alice')
            else:
                response.say("Hello! This is Sarah from Field Services Nationwide. I'm calling about a job opportunity. Are you available to chat?", voice='alice')
            
            # FIXED: Better gather configuration
            response.gather(
                input='speech',
                speech_timeout='auto',
                timeout=10,
                action=url_for('twilio_handle_response', _external=True, call_log_id=call_log_id),
                method='POST'
            )
            return str(response)
        
        else:  # POST - status updates
            call_sid = request.form.get('CallSid')
            call_status = request.form.get('CallStatus')
            logger.info(f"Status update: CallSid={call_sid}, Status={call_status}")
            
            # Update call log status
            if call_log_id and call_status in ['answered', 'completed', 'busy', 'no-answer', 'failed']:
                try:
                    call_log = CallLog.query.get(call_log_id)
                    if call_log:
                        call_log.call_status = call_status
                        db.session.commit()
                except Exception as e:
                    logger.error(f"Error updating call status: {e}")
                    db.session.rollback()
            
            return '', 200
            
    except Exception as e:
        logger.error(f"Error in twilio_voice_webhook: {e}")
        error_response = TwiMLResponse()
        error_response.say("Sorry, there was a technical issue. Please try again later.", voice='alice')
        error_response.hangup()
        return str(error_response)

@app.route('/twilio_handle_response', methods=['POST'])
def twilio_handle_response():
    """FIXED: Better conversation handling."""
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '').strip()
    call_log_id = request.args.get('call_log_id')
    
    logger.info(f"Speech from {call_sid}: '{speech_result}'")
    
    response = TwiMLResponse()
    
    try:
        # Update conversation
        if call_log_id:
            call_log = CallLog.query.get(call_log_id)
            if call_log:
                conversation = call_log.ai_conversation or ""
                conversation += f"\nTechnician: {speech_result}"
                
                # Get job context
                campaign = call_log.campaign
                work_order = campaign.work_order if campaign else None
                job_info = ""
                if work_order:
                    job_info = f"Job: {work_order.job_category} in {work_order.job_city}, ${work_order.pay_rate}/hour"
                
                # Generate AI response using OpenAI
                ai_prompt = (
                    f"Continue this conversation as Sarah from Field Services Nationwide:\n{conversation}\n\n"
                    f"Job details: {job_info}\n\n"
                    f"Based on their response, continue talking about the job opportunity. "
                    f"Keep responses under 20 seconds. If they seem interested, tell them a recruiter will call back. "
                    f"If not interested, politely end the call. "
                    f"If they need more info, provide job details briefly."
                )
                
                ai_response = call_openai_api(ai_prompt)
                if not ai_response:
                    ai_response = "Thank you for your time. A recruiter will contact you soon if you're interested."
                
                response.say(ai_response, voice='alice')
                
                # Update conversation
                conversation += f"\nAI: {ai_response}"
                call_log.ai_conversation = conversation
                
                # Check if conversation should end
                lower_response = ai_response.lower()
                lower_speech = speech_result.lower()
                should_end = any(phrase in lower_response for phrase in [
                    "goodbye", "thank you for your time", "recruiter will call", "not interested"
                ]) or any(phrase in lower_speech for phrase in [
                    "not interested", "no thanks", "goodbye", "hang up"
                ])
                
                if should_end:
                    if "recruiter will call" in lower_response or "interested" in lower_speech:
                        call_log.call_result = 'interested'
                        # Update campaign responses
                        try:
                            campaign.current_responses += 1
                            db.session.commit()
                        except:
                            db.session.rollback()
                    else:
                        call_log.call_result = 'not_interested'
                    
                    call_log.call_status = 'completed'
                    db.session.commit()
                    response.hangup()
                else:
                    # Continue conversation
                    response.gather(
                        input='speech',
                        speech_timeout='auto',
                        timeout=10,
                        action=url_for('twilio_handle_response', _external=True, call_log_id=call_log_id),
                        method='POST'
                    )
                    db.session.commit()
        
    except Exception as e:
        logger.error(f"Error in handle_response: {e}")
        response.say("Thank you for your time. Have a great day!", voice='alice')
        response.hangup()
        try:
            db.session.rollback()
        except:
            pass
    
    return str(response)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(username=form.username.data).first()
            
            if user and user.check_password(form.password.data) and user.is_active:
                login_user(user, remember=True)
                flash('Login successful!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('Invalid username or password!', 'error')
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Login failed. Please try again.', 'error')
    
    return render_template('auth/login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            if User.query.filter_by(username=form.username.data).first():
                flash('Username already exists!', 'error')
                return render_template('auth/register.html', form=form)
            
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already registered!', 'error')
                return render_template('auth/register.html', form=form)
            
            user = User(
                username=form.username.data,
                email=form.email.data,
                company_name=form.company_name.data,
                phone=form.phone.data,
                role='sub_account'
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('auth/register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/create_work_order', methods=['GET', 'POST'])
@login_required
def create_work_order():
    form = WorkOrderForm()
    
    if form.validate_on_submit():
        try:
            # Use full address for better geocoding
            full_address = f"{form.job_city.data}, {form.job_state.data} {form.job_zip.data}, USA"
            job_lat, job_lon = get_coordinates(full_address)
            
            required_skills = []
            if form.required_skills.data:
                required_skills = [skill.strip() for skill in form.required_skills.data.split(',') if skill.strip()]
            
            work_order = WorkOrder(
                work_order_id=f"WO-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
                job_category=form.job_category.data,
                required_skills=required_skills,
                minimum_skill_level=form.minimum_skill_level.data,
                job_city=form.job_city.data,
                job_state=form.job_state.data,
                job_zip=form.job_zip.data,
                job_latitude=job_lat,
                job_longitude=job_lon,
                pay_rate=form.pay_rate.data,
                duration_hours=form.duration_hours.data,
                description=form.description.data,
                requirements={
                    'drug_screen': form.drug_screen.data,
                    'background_check': form.background_check.data,
                    'min_experience': form.min_experience.data
                },
                created_by=current_user.id
            )
            
            db.session.add(work_order)
            db.session.commit()
            
            flash('Work order created successfully!', 'success')
            return redirect(url_for('start_campaign', work_order_id=work_order.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating work order: {str(e)}', 'error')
            logger.error(f"Error creating work order: {e}")

    return render_template('work_order/create.html', form=form)

@app.route('/start_campaign/<int:work_order_id>')
@login_required
def start_campaign(work_order_id):
    try:
        work_order = WorkOrder.query.get_or_404(work_order_id)
        
        if not current_user.is_admin() and work_order.created_by != current_user.id:
            flash('Access denied!', 'error')
            return redirect(url_for('index'))
        
        existing_campaign = CallCampaign.query.filter_by(work_order_id=work_order.id, status='active').first()
        if existing_campaign:
            flash(f'Campaign for Work Order {work_order.work_order_id} is already active!', 'info')
            return redirect(url_for('campaign_dashboard', campaign_id=existing_campaign.id))
        
        campaign = CallCampaign(work_order_id=work_order.id, target_responses=5)
        db.session.add(campaign)
        db.session.commit()
        
        flash('Campaign started successfully!', 'success')
        return redirect(url_for('campaign_dashboard', campaign_id=campaign.id))
    except Exception as e:
        logger.error(f"Error starting campaign: {e}")
        flash('Error starting campaign. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/campaign/<int:campaign_id>')
@login_required
def campaign_dashboard(campaign_id):
    try:
        campaign = CallCampaign.query.get_or_404(campaign_id)
        work_order = campaign.work_order
        
        if not current_user.is_admin() and work_order.created_by != current_user.id:
            flash('Access denied!', 'error')
            return redirect(url_for('index'))
        
        # Get called technician IDs
        called_tech_ids = [log.technician_id for log in 
                           CallLog.query.filter_by(campaign_id=campaign.id).all()]
        
        # Find qualified technicians
        qualified_pool, all_technicians_data = find_qualified_technicians(
            work_order,
            campaign.current_radius,
            exclude_called_ids=called_tech_ids
        )

        # Get call logs with technician details
        call_logs_with_tech = db.session.query(CallLog, Technician).\
                    join(Technician).\
                    filter(CallLog.campaign_id == campaign.id).\
                    order_by(CallLog.called_at.desc()).all()
        
        stats = {
            'total_calls': len(call_logs_with_tech),
            'interested': len([log for log, _ in call_logs_with_tech if log.call_result == 'interested']),
            'not_interested': len([log for log, _ in call_logs_with_tech if log.call_result == 'not_interested']),
            'callbacks': len([log for log, _ in call_logs_with_tech if log.call_result == 'callback']),
            'current_radius': campaign.current_radius,
            'success_rate': (len([log for log, _ in call_logs_with_tech if log.call_result == 'interested']) / len(call_logs_with_tech) * 100) if call_logs_with_tech else 0,
            'potential_candidates_count': len(all_technicians_data),
            'qualified_candidates_count': len(qualified_pool)
        }
        
        return render_template('campaign/dashboard.html', 
                               campaign=campaign,
                               work_order=work_order,
                               call_logs=call_logs_with_tech,
                               all_technicians_data=all_technicians_data,
                               stats=stats)
        
    except Exception as e:
        logger.error(f"Error in campaign dashboard: {e}")
        flash('Error loading campaign dashboard', 'error')
        return redirect(url_for('index'))

@app.route('/upload_technicians', methods=['GET', 'POST'])
@login_required
def upload_technicians():
    if not current_user.is_admin():
        flash('Access denied! Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected!', 'error')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect(request.url)
            
        if file and file.filename.endswith('.xlsx'):
            try:
                df = pd.read_excel(file)
                imported_count = import_technicians_from_df(df)
                flash(f'Successfully imported {imported_count} technicians!', 'success')
                return redirect(url_for('list_technicians'))
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
                logger.error(f"Error processing upload file: {e}")
        else:
            flash('Please upload an Excel (.xlsx) file!', 'error')
    
    return render_template('technicians/upload.html')

@app.route('/technicians')
@login_required
def list_technicians():
    return render_template('technicians/list.html')

# ==================== API ENDPOINTS ====================

@app.route('/api/technicians', methods=['GET'])
@login_required
def api_get_technicians():
    """API endpoint to get all active technicians."""
    try:
        all_technicians = Technician.query.filter_by(is_active=True).all()
        
        technicians_data = []
        for tech in all_technicians:
            technicians_data.append({
                'id': tech.id,
                'name': tech.name,
                'email': tech.email,
                'mobile_phone': tech.mobile_phone,
                'home_phone': tech.home_phone or 'N/A',
                'address': tech.address or 'N/A',
                'city': tech.city,
                'state': tech.state,
                'zip_code': tech.zip_code,
                'latitude': tech.latitude,
                'longitude': tech.longitude,
                'experience_years': tech.experience_years,
                'drug_screening': tech.drug_screening,
                'background_check': tech.background_check,
                'skills': tech.skills or {},
                'tools': tech.tools or 'N/A',
                'is_active': tech.is_active,
                'created_at': tech.created_at.isoformat(),
                'updated_at': tech.updated_at.isoformat() if tech.updated_at else None
            })
        return jsonify({'technicians': technicians_data})
    
    except Exception as e:
        logger.error(f"Error in api_get_technicians: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/start_calling/<int:campaign_id>', methods=['POST'])
@login_required
def api_start_calling(campaign_id):
    try:
        campaign = CallCampaign.query.get_or_404(campaign_id)
        
        if not current_user.is_admin() and campaign.work_order.created_by != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get request data safely
        request_data = request.get_json() or {}
        batch_size = min(request_data.get('batch_size', 5), 10)  # FIXED: Limit batch size
        
        logger.info(f"Starting calling for campaign {campaign_id}, batch size: {batch_size}")
        
        # Get already called technician IDs
        called_ids = [log.technician_id for log in 
                      CallLog.query.filter_by(campaign_id=campaign.id).all()]
        
        # Find qualified technicians
        qualified_pool, _ = find_qualified_technicians(
            campaign.work_order,
            campaign.current_radius,
            exclude_called_ids=called_ids
        )
        
        if not qualified_pool:
            return jsonify({
                'status': 'no_candidates',
                'pool_size': 0,
                'message': f'No qualified technicians found within {campaign.current_radius} miles.'
            })
        
        # Select technicians for this batch
        random.shuffle(qualified_pool)
        selected_techs = qualified_pool[:batch_size]
        
        # Make calls
        results = []
        successful_calls = 0
        
        for tech_data in selected_techs:
            try:
                result = make_ai_call(campaign, tech_data)
                results.append(result)
                if result.get('call_status') not in ['failed_twilio_api', 'error']:
                    successful_calls += 1
            except Exception as e:
                logger.error(f"Failed to call {tech_data['technician'].name}: {e}")
                results.append({
                    'technician_id': tech_data['technician'].id,
                    'name': tech_data['technician'].name,
                    'phone': tech_data['technician'].mobile_phone,
                    'call_status': 'error',
                    'error': str(e)
                })
        
        return jsonify({
            'status': 'completed',
            'pool_size': len(qualified_pool),
            'called': len(selected_techs),
            'successful_calls': successful_calls,
            'results': results,
            'current_responses': campaign.current_responses
        })
        
    except Exception as e:
        logger.error(f"API calling failed for campaign {campaign_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/expand_radius/<int:campaign_id>', methods=['POST'])
@login_required
def api_expand_radius(campaign_id):
    try:
        campaign = CallCampaign.query.get_or_404(campaign_id)
        
        if not current_user.is_admin() and campaign.work_order.created_by != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        request_data = request.get_json() or {}
        expansion = min(request_data.get('expansion_miles', 20), 50)  # FIXED: Limit expansion
        
        campaign.current_radius += expansion
        db.session.commit()
        
        # Re-evaluate candidates with new radius
        called_ids = [log.technician_id for log in 
                      CallLog.query.filter_by(campaign_id=campaign.id).all()]
        
        qualified_pool, _ = find_qualified_technicians(
            campaign.work_order,
            campaign.current_radius,
            exclude_called_ids=called_ids
        )
        
        return jsonify({
            'status': 'radius_expanded',
            'new_radius': campaign.current_radius,
            'new_candidates': len(qualified_pool),
            'message': f'Radius expanded to {campaign.current_radius} miles'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"API radius expansion failed: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== IMPORT FUNCTION ====================

def import_technicians_from_df(df):
    """FIXED: Better error handling and session management for import."""
    imported_count = 0
    
    expected_columns = [
        'Name of Technician', 'Email', 'Mobile/Cell Phone', 'Home Phone',
        'Address - Street', 'Address - City', 'Address - State/Province', 'Address - Zip Code',
        'Number of Years of Experience in the IT Industry', 'Able to Pass a Drug Screening?',
        'Able to Pass a Background Check?', 'Tools', 
        'POS (Point of Sale Machines)', 'Laptop Repair', 'Network Troubleshooting',
        'Security Cameras', 'Cat5/6', 'Server Programming'
    ]
    
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    for index, row in df.iterrows():
        try:
            tech_name = str(row.get('Name of Technician', '')).strip()
            if not tech_name:
                continue

            mobile_phone = str(row.get('Mobile/Cell Phone', '')).strip()
            if not mobile_phone:
                continue

            email = str(row.get('Email', '')).strip() or None

            # Check for existing technician
            existing_tech = Technician.query.filter(
                (Technician.mobile_phone == mobile_phone) |
                ((Technician.email == email) if email else False)
            ).first()

            if existing_tech:
                logger.info(f"Technician '{tech_name}' already exists. Skipping.")
                continue
            
            # Better geocoding with full address
            city = str(row.get('Address - City', '')).strip()
            state = str(row.get('Address - State/Province', '')).strip()
            zip_code = str(row.get('Address - Zip Code', '')).strip()
            
            lat, lon = None, None
            if city and state and zip_code:
                full_address = f"{city}, {state} {zip_code}, USA"
                lat, lon = get_coordinates(full_address)
            elif zip_code:
                lat, lon = get_coordinates(f"{zip_code}, USA")
            
            # Parse experience years
            exp_str = str(row.get('Number of Years of Experience in the IT Industry', '')).strip()
            exp_years = 0
            if exp_str:
                try:
                    exp_years = max(0, int(float(exp_str)))  # FIXED: Ensure non-negative
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse experience '{exp_str}' for {tech_name}")

            # Parse boolean fields
            drug_screening = str(row.get('Able to Pass a Drug Screening?', '')).strip().lower() == 'yes'
            background_check = str(row.get('Able to Pass a Background Check?', '')).strip().lower() == 'yes'

            # Parse skills
            skills = {}
            skill_columns = [
                'POS (Point of Sale Machines)', 'Laptop Repair', 'Network Troubleshooting',
                'Security Cameras', 'Cat5/6', 'Server Programming'
            ]
            for skill_col in skill_columns:
                if skill_col in row and pd.notna(row[skill_col]):
                    skill_val = str(row[skill_col]).strip()
                    clean_key = skill_col.replace(' (Point of Sale Machines)', '').replace('/', '_')
                    skills[clean_key] = skill_val

            technician = Technician(
                name=tech_name,
                email=email,
                mobile_phone=mobile_phone,
                home_phone=str(row.get('Home Phone', '')).strip() or None,
                address=str(row.get('Address - Street', '')).strip() or None,
                city=city or None,
                state=state or None,
                zip_code=zip_code or None,
                latitude=lat,
                longitude=lon,
                experience_years=exp_years,
                drug_screening=drug_screening,
                background_check=background_check,
                skills=skills if skills else None,
                tools=str(row.get('Tools', '')).strip() or None,
                is_active=True
            )
            
            db.session.add(technician)
            imported_count += 1
            logger.info(f"Added technician: {technician.name}")
            
            # FIXED: Commit more frequently and handle errors
            if imported_count % 5 == 0:
                try:
                    db.session.commit()
                    logger.info(f"Committed {imported_count} technicians")
                except Exception as e:
                    logger.error(f"Error committing batch: {e}")
                    db.session.rollback()
                    raise
                
        except Exception as e:
            logger.error(f"Failed to import technician from row {index+1}: {e}")
            db.session.rollback()

    # Final commit
    try:
        db.session.commit()
        logger.info(f"Finished import. Total: {imported_count}")
    except Exception as e:
        logger.error(f"Error in final commit: {e}")
        db.session.rollback()
    
    return imported_count

def create_admin_user():
    """Create admin user if it doesn't exist."""
    try:
        with app.app_context():
            if not User.query.filter_by(username='admin').first():
                admin = User(
                    username='admin',
                    email='admin@fieldservicesnationwide.com',
                    role='admin',
                    company_name='Field Services Nationwide'
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                logger.info("Created admin user: username='admin', password='admin123'")
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'twilio_configured': twilio_client is not None,
        'openai_configured': openai_client is not None
    })

# FIXED: Better error handling for app context
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    try:
        with app.app_context():
            # FIXED: Create tables if they don't exist
            db.create_all()
            create_admin_user()
        
        port = int(os.environ.get('PORT', 5000))
        debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
        
        logger.info(f"Starting Flask app on port {port}, debug={debug_mode}")
        app.run(host='0.0.0.0', port=port, debug=debug_mode)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
