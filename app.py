#!/usr/bin/env python3
"""
Field Services Nationwide - AI Calling System
Main Flask Application
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
import requests # Used for calling external APIs like Gemini

import sqlalchemy 

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm # Kept for general forms, but CSRF functionality removed
from flask_migrate import Migrate
from wtforms import StringField, PasswordField, SelectField, TextAreaField, IntegerField, FloatField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging: Set to DEBUG for very detailed logs for troubleshooting, INFO for general
# For debugging AI conversation, set this to logging.DEBUG
logging.basicConfig(level=logging.INFO) # Set this to logging.DEBUG for verbose AI prompts/responses
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fsn_calling.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Explicitly confirm no CSRF: app.config['WTF_CSRF_ENABLED'] is not set or is False
# All imports and uses of CSRFProtect and generate_csrf are removed.

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


# Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '') # Automatically provided by Canvas runtime

# Initialize clients (handle cases where Twilio SID might be missing)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None
geolocator = Nominatim(user_agent="fsn_calling_system")

# ==================== DATABASE MODELS ====================
# (Your existing database models - User, Technician, WorkOrder, CallCampaign, CallLog - are here)

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
    call_status = db.Column(db.String(20), nullable=False, index=True) # e.g., 'calling', 'answered', 'failed'
    call_result = db.Column(db.String(20), index=True) # e.g., 'interested', 'not_interested', 'callback', 'unavailable'
    call_duration = db.Column(db.Integer)
    distance_miles = db.Column(db.Float)
    ai_conversation = db.Column(db.Text)
    twilio_call_sid = db.Column(db.String(100))
    called_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

# ==================== LLM INTEGRATION ====================

def call_gemini_api(prompt, model="gemini-2.0-flash"):
    """
    Calls the Gemini API to generate text based on a prompt.
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set. Cannot call Gemini API. Using fallback message.")
        return "I am sorry, I cannot generate a response right now due to an internal configuration issue."

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 200 # Limit response length for voice calls to avoid long pauses
        }
    }

    try:
        logger.info(f"Calling Gemini API with prompt: '{prompt[:100]}...'")
        response = requests.post(api_url, headers=headers, json=payload, timeout=20) # Increased timeout
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        
        json_response = response.json()
        
        if json_response and json_response.get('candidates'):
            generated_text = json_response['candidates'][0]['content']['parts'][0]['text']
            logger.info(f"Gemini API response (first 100 chars): '{generated_text[:100]}...'")
            return generated_text
        else:
            logger.warning(f"Gemini API returned no candidates or unexpected format: {json_response}")
            return "I am sorry, I couldn't generate a coherent response from the AI."
    except requests.exceptions.Timeout:
        logger.error("Gemini API call timed out.")
        return "I am sorry, the AI is taking too long to respond. Please try again."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        return f"I am sorry, there was a problem with the AI service: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error processing Gemini API response: {e}", exc_info=True)
        return "I am sorry, an unexpected internal error occurred with the AI."

# ==================== CALLING SYSTEM ====================

def get_coordinates(zip_code):
    try:
        if pd.isna(zip_code) or not isinstance(zip_code, str):
            logger.warning(f"Invalid zip code input for geocoding: '{zip_code}'. Returning None, None.")
            return None, None
        
        location = geolocator.geocode(zip_code, timeout=10)
        if location:
            logger.info(f"Geocoded zip '{zip_code}': Lat {location.latitude}, Lon {location.longitude}")
            return location.latitude, location.longitude
        logger.warning(f"Could not geocode zip code: '{zip_code}'. Returning None, None.")
        return None, None
    except Exception as e:
        logger.error(f"Error getting coordinates for '{zip_code}': {e}", exc_info=True)
        return None, None

def find_qualified_technicians(work_order, radius_miles, exclude_called_ids=None):
    if exclude_called_ids is None:
        exclude_called_ids = []
    
    logger.info(f"--- Starting qualification check for Work Order: {work_order.work_order_id} (ID: {work_order.id}) ---")
    logger.info(f"Work Order Location: Lat={work_order.job_latitude}, Lon={work_order.job_longitude}, Radius={radius_miles} miles")
    
    potential_technicians_data = [] # To store details for the dashboard
    
    all_techs = Technician.query.filter(Technician.is_active == True).all()
    
    if not all_techs:
        logger.warning("No active technicians found in the database.")
        return [], []

    qualified_pool = []
    
    work_order_location = (work_order.job_latitude, work_order.job_longitude)
    
    if not work_order.job_latitude or not work_order.job_longitude:
        logger.error(f"Work Order {work_order.work_order_id} has no valid coordinates. Cannot perform distance filtering.")
    
    for tech in all_techs:
        is_qualified = True
        disqualification_reason = []
        tech_distance = None

        logger.debug(f"Checking Technician: {tech.name} (ID: {tech.id}, Phone: {tech.mobile_phone})")
        
        if tech.id in exclude_called_ids:
            is_qualified = False
            disqualification_reason.append("Already called for this campaign")
            logger.debug(f"- {tech.name}: Skipped (Already called for this campaign)")
        
        if is_qualified:
            tech_location = (tech.latitude, tech.longitude)
            if not tech.latitude or not tech.longitude:
                is_qualified = False
                disqualification_reason.append("No valid coordinates")
                logger.debug(f"- {tech.name}: Skipped (No valid technician coordinates: Lat={tech.latitude}, Lon={tech.longitude})")
            elif not work_order.job_latitude or not work_order.job_longitude:
                is_qualified = False
                disqualification_reason.append("Work Order has no valid coordinates for distance check")
                logger.debug(f"- {tech.name}: Skipped (Work Order has no valid coordinates for distance check)")
            else:
                try:
                    tech_distance = geodesic(work_order_location, tech_location).miles
                    logger.debug(f"- {tech.name}: Distance calculated: {tech_distance:.2f} miles (Radius: {radius_miles})")
                    if tech_distance > radius_miles:
                        is_qualified = False
                        disqualification_reason.append(f"Too far ({tech_distance:.1f} miles > {radius_miles} miles)")
                        logger.debug(f"- {tech.name}: Skipped (Too far: {tech_distance:.1f} miles)")
                except Exception as e:
                    is_qualified = False
                    disqualification_reason.append(f"Error calculating distance: {e}")
                    logger.error(f"- {tech.name}: Error calculating distance: {e}", exc_info=True)

        if is_qualified:
            reqs = work_order.requirements or {}
            
            if reqs.get('drug_screen', False) and not tech.drug_screening:
                is_qualified = False
                disqualification_reason.append("Fails drug screening requirement")
                logger.debug(f"- {tech.name}: Skipped (Fails drug screening: WO Requires={reqs.get('drug_screen')}, Tech Has={tech.drug_screening})")
            
            if is_qualified and reqs.get('background_check', False) and not tech.background_check:
                is_qualified = False
                disqualification_reason.append("Fails background check requirement")
                logger.debug(f"- {tech.name}: Skipped (Fails background check: WO Requires={reqs.get('background_check')}, Tech Has={tech.background_check})")
            
            min_exp = reqs.get('min_experience', 0)
            if is_qualified and (tech.experience_years is None or tech.experience_years < min_exp):
                is_qualified = False
                disqualification_reason.append(f"Insufficient experience ({tech.experience_years or 0} yrs < {min_exp} yrs)")
                logger.debug(f"- {tech.name}: Skipped (Insufficient experience: WO Min={min_exp}, Tech Has={tech.experience_years})")

        if is_qualified and work_order.required_skills:
            tech_skills = tech.skills or {}
            meets_skills = True
            for skill in work_order.required_skills:
                skill_value = tech_skills.get(skill, '0/10')
                try:
                    if isinstance(skill_value, str) and '/' in skill_value:
                        rating = int(skill_value.split('/')[0])
                    elif isinstance(skill_value, str) and skill_value.isdigit():
                        rating = int(skill_value)
                    elif isinstance(skill_value, int):
                        rating = skill_value
                    else: 
                        rating = 0
                        
                    if rating < work_order.minimum_skill_level:
                        meets_skills = False
                        disqualification_reason.append(f"Insufficient skill level for '{skill}' ({rating}/10 < {work_order.minimum_skill_level}/10)")
                        logger.debug(f"- {tech.name}: Fails skill '{skill}' (Tech: {rating}/10, WO Min: {work_order.minimum_skill_level}/10)")
                        break 
                except (ValueError, TypeError):
                    meets_skills = False
                    disqualification_reason.append(f"Invalid skill rating for '{skill}'")
                    logger.debug(f"- {tech.name}: Fails skill '{skill}' (Invalid rating format)")
                    break 
            
            if not meets_skills:
                is_qualified = False

        tech_data_for_dashboard = {
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
            'reasons': ", ".join(disqualification_reason) if disqualification_reason else "N/A"
        }
        potential_technicians_data.append(tech_data_for_dashboard)

        if is_qualified:
            qualified_pool.append({
                'technician': tech,
                'distance': tech_distance
            })
            logger.info(f"--- QUALIFIED: {tech.name} (ID: {tech.id}), Distance: {tech_distance:.2f} miles ---")
        else:
            logger.info(f"--- DISQUALIFIED: {tech.name} (ID: {tech.id}), Reason(s): {', '.join(disqualification_reason) if disqualification_reason else 'Unknown'} ---")

    logger.info(f"--- Qualification check finished. Total qualified: {len(qualified_pool)} ---")
    return qualified_pool, potential_technicians_data


def make_ai_call(campaign, tech_data):
    tech = tech_data['technician']
    
    logger.info(f"Attempting to make AI call to technician: {tech.name} ({tech.mobile_phone}) for Campaign ID: {campaign.id}")
    
    # Create call log
    call_log = CallLog(
        campaign_id=campaign.id,
        technician_id=tech.id,
        phone_number=tech.mobile_phone,
        call_status='initiated' # Initial status: call is being initiated
    )
    # Assign distance_miles after instantiation to bypass potential constructor issue
    call_log.distance_miles = tech_data['distance'] 

    db.session.add(call_log)
    db.session.commit() # Commit to get call_log.id before potential errors or Twilio call

    # --- REAL TWILIO CALL INTEGRATION ---
    if twilio_client and TWILIO_PHONE_NUMBER:
        try:
            logger.info(f"Initiating REAL Twilio call to {tech.mobile_phone} from {TWILIO_PHONE_NUMBER}...")
            # Pass call_log_id for context in subsequent webhooks
            call = twilio_client.calls.create(
                url=url_for('twilio_voice_webhook', _external=True, 
                            call_log_id=call_log.id), 
                to=tech.mobile_phone,
                from_=TWILIO_PHONE_NUMBER
            )
            call_log.twilio_call_sid = call.sid
            call_log.call_status = 'ringing' # Call is now ringing
            db.session.commit() # Save SID and updated status
            logger.info(f"Twilio call initiated for {tech.name}. SID: {call.sid}. Status: {call.status}")

        except Exception as e:
            db.session.rollback() # Rollback if an error occurs during Twilio call initiation
            call_log.call_status = 'failed_twilio_api'
            call_log.call_result = 'error'
            call_log.ai_conversation = f"Error initiating Twilio call: {str(e)}"
            db.session.commit()
            logger.error(f"Twilio API call failed for {tech.name} ({tech.mobile_phone}): {e}", exc_info=True)
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
        logger.warning("Twilio client not initialized or phone number missing. Simulating call results for logging.")
        call_log.call_status = 'simulated'
        responses = ['interested', 'not_interested', 'callback', 'unavailable']
        weights = [0.25, 0.45, 0.20, 0.10]
        call_log.call_result = random.choices(responses, weights=weights)[0]
        call_log.call_duration = random.randint(90, 240)
        if call_log.call_result == 'interested':
            campaign.current_responses += 1
        db.session.commit()
    
    logger.info(f"Call initiation logged for {tech.name}. Current Call Status: {call_log.call_status}")
    
    return {
        'call_log_id': call_log.id,
        'technician_id': tech.id,
        'name': tech.name,
        'phone': tech.mobile_phone,
        'call_status': call_log.call_status,
        'call_result': call_log.call_result if call_log.call_result else 'pending_response', # Reflects pending AI interaction
        'distance': tech_data['distance'],
        'twilio_call_sid': call_log.twilio_call_sid
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
        logger.error(f"Error updating last login for user {current_user.username}: {e}", exc_info=True)
        db.session.rollback()

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=True)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('auth/login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
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
            job_lat, job_lon = get_coordinates(form.job_zip.data)
            
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
            logger.error(f"Error creating work order: {e}", exc_info=True)

    return render_template('work_order/create.html', form=form)

@app.route('/start_campaign/<int:work_order_id>')
@login_required
def start_campaign(work_order_id):
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
    
    flash('Campaign started successfully! Review potential technicians and initiate calls.', 'success')
    return redirect(url_for('campaign_dashboard', campaign_id=campaign.id))

@app.route('/campaign/<int:campaign_id>')
@login_required
def campaign_dashboard(campaign_id):
    campaign = CallCampaign.query.get_or_404(campaign_id)
    work_order = campaign.work_order
    
    if not current_user.is_admin() and work_order.created_by != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('index'))
    
    # Get all already called technicians for this campaign
    called_tech_ids = [log.technician_id for log in 
                       CallLog.query.filter_by(campaign_id=campaign.id).all()]
    
    # Find qualified technicians and get detailed data for dashboard
    qualified_pool, all_technicians_for_dashboard = find_qualified_technicians(
        work_order,
        campaign.current_radius,
        exclude_called_ids=called_tech_ids # Pass existing called IDs to the function
    )

    # Fetch call logs along with associated technician details using a join
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
        'potential_candidates_count': len(all_technicians_for_dashboard), # Total techs considered
        'qualified_candidates_count': len(qualified_pool) # Total qualified from current radius/criteria
    }
    
    return render_template('campaign/dashboard.html', 
                           campaign=campaign,
                           work_order=work_order,
                           call_logs=call_logs_with_tech, # This will be a list of (CallLog, Technician) tuples
                           all_technicians_data=all_technicians_for_dashboard, # New data for potential techs
                           stats=stats
                           )

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
                return redirect(url_for('list_technicians')) # Redirect to new technician list page
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
                logger.error(f"Error processing upload file: {e}", exc_info=True)
        else:
            flash('Please upload an Excel (.xlsx) file!', 'error')
    
    return render_template('technicians/upload.html')

# NEW ROUTE: List all technicians
@app.route('/technicians')
@login_required
def list_technicians():
    return render_template('technicians/list.html')


# ==================== API ENDPOINTS (Additional) ====================

@app.route('/api/technicians', methods=['GET'])
@login_required
def api_get_technicians():
    """API endpoint to get a list of all active technicians."""
    all_technicians = Technician.query.filter_by(is_active=True).all()
    
    technicians_data = []
    for tech in all_technicians:
        technicians_data.append({
            'id': tech.id,
            'name': tech.name,
            'email': tech.email,
            'mobile_phone': tech.mobile_phone,
            'home_phone': tech.home_phone or 'N/A', # Provide N/A for None
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

@app.route('/api/start_calling/<int:campaign_id>', methods=['POST'])
@login_required
def api_start_calling(campaign_id):
    campaign = CallCampaign.query.get_or_404(campaign_id)
    
    if not current_user.is_admin() and campaign.work_order.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        batch_size = request.json.get('batch_size', 5) # Default to 5 calls per batch
        
        # Get already called technician IDs for this campaign
        called_ids = [log.technician_id for log in 
                      CallLog.query.filter_by(campaign_id=campaign.id).all()]
        
        # Find qualified pool based on current radius and excluding already called
        qualified_pool, _ = find_qualified_technicians(
            campaign.work_order,
            campaign.current_radius,
            exclude_called_ids=called_ids
        )
        
        if not qualified_pool:
            logger.info(f"Campaign {campaign.id}: No new qualified technicians found for calling.")
            return jsonify({
                'status': 'no_candidates',
                'pool_size': 0,
                'message': f'No new qualified technicians found within {campaign.current_radius} miles not yet called.'
            })
        
        # RANDOM SELECTION FOR FAIRNESS
        random.shuffle(qualified_pool)
        selected_techs_for_call = qualified_pool[:batch_size]
        
        if not selected_techs_for_call:
            logger.info(f"Campaign {campaign.id}: Qualified pool is empty after batch selection.")
            return jsonify({
                'status': 'no_candidates',
                'pool_size': len(qualified_pool),
                'message': 'No technicians selected for this batch (pool too small).'
            })

        # Execute calls
        results = []
        for tech_data in selected_techs_for_call:
            result = make_ai_call(campaign, tech_data)
            results.append(result)
            
        return jsonify({
            'status': 'completed',
            'pool_size': len(qualified_pool),
            'called': len(selected_techs_for_call),
            'results': results,
            'current_responses': campaign.current_responses # Update this to reflect new responses
        })
            
    except Exception as e:
        logger.error(f"API Calling failed for campaign {campaign_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/expand_radius/<int:campaign_id>', methods=['POST'])
@login_required
def api_expand_radius(campaign_id):
    campaign = CallCampaign.query.get_or_404(campaign_id)
    
    if not current_user.is_admin() and campaign.work_order.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        expansion = request.json.get('expansion_miles', 20)
        campaign.current_radius += expansion
        db.session.commit()
        
        # Re-evaluate candidates with new radius (no calls made here, just update count)
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
        logger.error(f"API radius expansion failed for campaign {campaign_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/twilio_handle_response', methods=['POST', 'GET'])
def twilio_handle_response():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    logger.info(f"Handling response for {call_sid}: '{speech_result}'")
    
    response = TwiMLResponse()
    call_log_id = request.args.get('call_log_id')
    call_log = CallLog.query.get(call_log_id) if call_log_id else None
    
    if not call_log:
        response.say("Sorry, technical issue. Goodbye.")
        response.hangup()
        return str(response)
    
    # Update conversation history
    conversation = call_log.ai_conversation or ""
    conversation += f"\nTechnician: {speech_result}"
    call_log.ai_conversation = conversation
    
    # Get AI response
    ai_prompt = (
        f"Continue this conversation as Sarah from Field Services Nationwide:\n{conversation}\n\n"
        f"Based on their response, continue talking about the job opportunity. "
        f"Only end the conversation if they clearly say 'not interested', 'goodbye', or 'yes I'm interested'. "
        f"Otherwise, keep the conversation going by asking questions about their availability, skills, or providing more job details. "
        f"Keep responses under 20 seconds."
    )
    
    ai_response = call_gemini_api(ai_prompt)
    if not ai_response:
        ai_response = "Can you tell me more about your availability for this job opportunity?"
    
    response.say(ai_response)
    
    # Update conversation
    conversation += f"\nAI: {ai_response}"
    call_log.ai_conversation = conversation
    
    # Check if AI explicitly ended conversation
    lower_response = ai_response.lower()
    should_end = any(phrase in lower_response for phrase in [
        "goodbye", "thank you for your time", "recruiter will call you", "not a good fit"
    ])
    
    if should_end:
        # Set appropriate call result
        if "recruiter will call" in lower_response:
            call_log.call_result = 'interested'
        else:
            call_log.call_result = 'not_interested'
        call_log.call_status = 'completed'
        response.hangup()
    else:
        # CONTINUE THE CONVERSATION - this is the key part!
        response.gather(
            input='speech',
            speechTimeout='auto',
            action=url_for('twilio_handle_response', _external=True, call_log_id=call_log_id),
            method='POST',
            actionOnEmptyResult=True
        )
    
    db.session.commit()
    return str(response)


# ==================== HELPER FUNCTIONS ====================

def import_technicians_from_df(df):
    imported_count = 0
    
    # Ensure all expected columns are present, even if empty, to avoid KeyError
    expected_columns = [
        'Name of Technician', 'Email', 'Mobile/Cell Phone', 'Home Phone',
        'Address - Street', 'Address - City', 'Address - State/Province', 'Address - Zip Code',
        'Number of Years of Experience in the IT Industry', 'Able to Pass a Drug Screening?',
        'Able to Pass a Background Check?', 'Tools', 
        # Skill columns - make sure these match your spreadsheet exactly
        'POS (Point of Sale Machines)', 'Laptop Repair', 'Network Troubleshooting',
        'Security Cameras', 'Cat5/6', 'Server Programming'
    ]
    # Add any missing columns to DataFrame with NaN values to prevent KeyError
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None # Add the column with None values

    for index, row in df.iterrows():
        try:
            # Strip whitespace and convert to string, handling NaN
            tech_name = str(row.get('Name of Technician', '')).strip()
            if not tech_name:
                logger.warning(f"Skipping row {index+1} due to missing or empty technician name: {row.to_dict()}")
                continue

            mobile_phone = str(row.get('Mobile/Cell Phone', '')).strip()
            if not mobile_phone:
                logger.warning(f"Skipping row {index+1} ({tech_name}) due to missing mobile phone.")
                continue

            email = str(row.get('Email', '')).strip() or None # Allow email to be None if empty

            logger.debug(f"Processing technician: {tech_name}, Mobile: {mobile_phone}, Email: {email} (Row {index+1})")

            # Check for existing technician by mobile_phone or email to prevent duplicates
            # Only check if mobile_phone or email are not None
            existing_tech_query = Technician.query.filter(
                (Technician.mobile_phone == mobile_phone)
            )
            if email:
                existing_tech_query = existing_tech_query.union(
                    Technician.query.filter(Technician.email == email)
                )
            
            existing_tech = existing_tech_query.first()

            if existing_tech:
                logger.info(f"Technician '{tech_name}' (Mobile: {mobile_phone}, Email: {email}) already exists (ID: {existing_tech.id}). Skipping import.")
                continue # Skip this row as it's a duplicate based on mobile_phone or email
            
            # Geocoding
            zip_code = str(row.get('Address - Zip Code', '')).strip()
            lat, lon = None, None
            if zip_code:
                lat, lon = get_coordinates(zip_code)
            else:
                logger.warning(f"Zip code missing for {tech_name} (Row {index+1}). Skipping geocoding.")
            
            # Safely parse experience years
            exp_str = str(row.get('Number of Years of Experience in the IT Industry', '')).strip()
            exp_years = 0 # Default value
            if exp_str:
                try:
                    exp_years = int(float(exp_str)) # Handles "7.0"
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse experience years '{exp_str}' for {tech_name} (Row {index+1}). Defaulting to 0.")

            # Safely parse boolean fields ('yes'/'no' or empty)
            drug_screening = str(row.get('Able to Pass a Drug Screening?', '')).strip().lower() == 'yes'
            background_check = str(row.get('Able to Pass a Background Check?', '')).strip().lower() == 'yes'

            # Parse skills (assuming you want to convert "7/10" to "7")
            skills = {}
            skill_columns = [
                'POS (Point of Sale Machines)', 'Laptop Repair', 'Network Troubleshooting',
                'Security Cameras', 'Cat5/6', 'Server Programming'
            ]
            for skill_col in skill_columns:
                if skill_col in row and pd.notna(row[skill_col]):
                    skill_val = str(row[skill_col]).strip()
                    # Example: if you want '7/10' to become '7', you'd parse it here
                    skills[skill_col.replace(' (Point of Sale Machines)', '')] = skill_val # Clean up key name

            # Get Home Phone, Address, and Tools
            home_phone_val = str(row.get('Home Phone', '')).strip() or None
            address_val = str(row.get('Address - Street', '')).strip() or None # Assuming 'Address - Street' for full address
            tools_val = str(row.get('Tools', '')).strip() or None # Assuming 'Tools' column for tools

            technician = Technician(
                name=tech_name,
                email=email,
                mobile_phone=mobile_phone,
                home_phone=home_phone_val,
                address=address_val,
                city=str(row.get('Address - City', '')).strip() or None,
                state=str(row.get('Address - State/Province', '')).strip() or None,
                zip_code=zip_code or None,
                latitude=lat,
                longitude=lon,
                experience_years=exp_years,
                drug_screening=drug_screening,
                background_check=background_check,
                skills=skills if skills else None, # Store as None if empty dict
                tools=tools_val,
                is_active=True
            )
            
            db.session.add(technician)
            imported_count += 1
            logger.info(f"Successfully added technician: {technician.name} (Row {index+1})")
            
            # Commit in batches to reduce transaction size but ensure persistence
            # Commit after every record for immediate feedback in logs during debugging
            if imported_count % 1 == 0: 
                db.session.commit()
                logger.info(f"Committed {imported_count} technicians so far.")
                
        except Exception as e:
            logger.error(f"Failed to import technician from row {index+1} (Name: {row.get('Name of Technician', 'N/A')}): {e}", exc_info=True)
            db.session.rollback() # Rollback current transaction if error occurs

    db.session.commit() # Final commit for any remaining records
    logger.info(f"Finished technician import. Total imported: {imported_count}")
    return imported_count

def create_admin_user():
    with app.app_context(): # Ensure admin user creation is within app context
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
        else:
            logger.info("Admin user already exists.")

# Health check
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    with app.app_context():
        # Ensure database tables are created or migrated
        # If you are using 'flask db upgrade' in Render build command, this is not strictly needed here
        # db.create_all() 
        create_admin_user() # Ensure admin user exists on app startup
    
    port = int(os.environ.get('PORT', 5000))
    # In production, debug=False is crucial. Render handles the serving.
    app.run(host='0.0.0.0', port=port, debug=False)
