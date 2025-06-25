#!/usr/bin/env python3
"""
Field Services Nationwide - AI Calling System
Complete Flask Application with Integrated Call Testing
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

# Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Initialize clients
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

# Store conversation state in memory
conversations = {}

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
    campaign_id = db.Column(db.Integer, db.ForeignKey('call_campaigns.id'), nullable=True)
    technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=True)
    phone_number = db.Column(db.String(20), nullable=False)
    call_status = db.Column(db.String(20), nullable=False, index=True)
    call_result = db.Column(db.String(20), index=True)
    call_duration = db.Column(db.Integer)
    distance_miles = db.Column(db.Float)
    ai_conversation = db.Column(db.Text)
    twilio_call_sid = db.Column(db.String(100))
    called_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_test_call = db.Column(db.Boolean, default=False, nullable=False)

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

# ==================== CONVERSATION MANAGEMENT ====================

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
        recent_messages = self.conversation_history[-6:]
        context_text = ""
        for msg in recent_messages:
            context_text += f"{msg['speaker']}: {msg['message']}\n"
        return context_text

def get_conversation_manager(call_sid):
    if call_sid not in conversations:
        conversations[call_sid] = ConversationManager(call_sid)
    return conversations[call_sid]

# ==================== AI INTEGRATION ====================

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
    """Determine if conversation should end"""
    user_lower = user_input.lower()
    ai_lower = ai_response.lower()
    
    end_phrases = [
        'not interested', 'no thanks', 'not available', 'busy', 'goodbye', 
        'hang up', 'stop calling', 'remove me', 'don\'t call'
    ]
    
    ai_end_phrases = [
        'recruiter will call', 'thank you for your time', 'have a great day',
        'we\'ll be in touch', 'goodbye'
    ]
    
    if any(phrase in ai_lower for phrase in ai_end_phrases):
        return True
    
    if any(phrase in user_lower for phrase in end_phrases):
        return True
    
    return False

# ==================== HELPER FUNCTIONS ====================

def get_coordinates(address_string):
    """Geocoding with better error handling."""
    try:
        if not address_string or pd.isna(address_string):
            return None, None
        
        address_string = str(address_string).strip()
        if not address_string:
            return None, None
        
        if ", USA" not in address_string and ", US" not in address_string:
            if address_string.replace('.', '').replace('-', '').isdigit():
                address_string = f"{address_string}, USA"
            else:
                address_string = f"{address_string}, USA"
        
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
    """Find qualified technicians within radius."""
    if exclude_called_ids is None:
        exclude_called_ids = []
    
    logger.info(f"--- Starting qualification check for Work Order: {work_order.work_order_id} ---")
    
    try:
        all_techs = Technician.query.filter(Technician.is_active == True).all()
        
        if not all_techs:
            logger.warning("No active technicians found.")
            return [], []

        qualified_pool = []
        potential_technicians_data = []
        
        if not work_order.job_latitude or not work_order.job_longitude:
            logger.error(f"Work Order {work_order.work_order_id} has no valid coordinates.")
            return [], []
            
        work_order_location = (work_order.job_latitude, work_order.job_longitude)
        
        for tech in all_techs:
            is_qualified = True
            disqualification_reasons = []
            tech_distance = None

            if tech.id in exclude_called_ids:
                is_qualified = False
                disqualification_reasons.append("Already called for this campaign")
            
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

def make_ai_call(campaign, tech_data, is_test=False):
    """Make AI call to technician."""
    tech = tech_data['technician'] if not is_test else None
    phone_number = tech_data['technician'].mobile_phone if not is_test else tech_data.get('phone_number')
    
    logger.info(f"Making call to {tech.name if tech else phone_number}")
    
    try:
        call_log = CallLog(
            campaign_id=campaign.id if campaign else None,
            technician_id=tech.id if tech else None,
            phone_number=phone_number,
            call_status='initiated',
            distance_miles=tech_data.get('distance'),
            is_test_call=is_test
        )
        
        try:
            db.session.add(call_log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create call log: {e}")
            raise

        if twilio_client and TWILIO_PHONE_NUMBER:
            try:
                call = twilio_client.calls.create(
                    url=url_for('twilio_voice_webhook', _external=True, call_log_id=call_log.id),
                    to=phone_number,
                    from_=TWILIO_PHONE_NUMBER,
                    timeout=45,
                    record=False,
                    machine_detection='DetectMessageEnd',
                    machine_detection_timeout=10,
                    status_callback=url_for('twilio_voice_webhook', _external=True, call_log_id=call_log.id),
                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                    status_callback_method='POST'
                )
                
                call_log.twilio_call_sid = call.sid
                call_log.call_status = 'ringing'
                db.session.commit()
                
                logger.info(f"Twilio call initiated successfully. SID: {call.sid}")
                
            except Exception as e:
                call_log.call_status = 'failed_twilio_api'
                call_log.call_result = 'error'
                call_log.ai_conversation = f"Twilio error: {str(e)}"
                db.session.commit()
                logger.error(f"Twilio call failed: {e}")
                
                return {
                    'call_log_id': call_log.id,
                    'technician_id': tech.id if tech else None,
                    'name': tech.name if tech else 'Test Call',
                    'phone': phone_number,
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
            
            if call_log.call_result == 'interested' and campaign:
                campaign.current_responses += 1
            
            db.session.commit()
        
        return {
            'call_log_id': call_log.id,
            'technician_id': tech.id if tech else None,
            'name': tech.name if tech else 'Test Call',
            'phone': phone_number,
            'call_status': call_log.call_status,
            'call_result': call_log.call_result or 'pending',
            'distance': tech_data.get('distance'),
            'twilio_call_sid': call_log.twilio_call_sid
        }
        
    except Exception as e:
        logger.error(f"Error making call: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return {
            'technician_id': tech.id if tech else None,
            'name': tech.name if tech else 'Test Call',
            'phone': phone_number,
            'call_status': 'error',
            'call_result': 'error',
            'error': str(e)
        }

# ==================== MAIN ROUTES ====================

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
        
        called_tech_ids = [log.technician_id for log in 
                           CallLog.query.filter_by(campaign_id=campaign.id).all()]
        
        qualified_pool, all_technicians_data = find_qualified_technicians(
            work_order,
            campaign.current_radius,
            exclude_called_ids=called_tech_ids
        )

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

# ==================== CALL TESTING ROUTES ====================

@app.route('/call')
@login_required
def call_test_interface():
    """Render call testing interface"""
    return render_template('call.html')

@app.route('/make_test_call', methods=['POST'])
@login_required
def make_test_call():
    """Make a test call to specified number"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return jsonify({'error': 'Phone number required'}), 400
            
        if not twilio_client:
            return jsonify({'error': 'Twilio client not configured'}), 500
        
        # Create test call data
        test_call_data = {
            'phone_number': phone_number,
            'distance': 0
        }
        
        # Make the call
        result = make_ai_call(None, test_call_data, is_test=True)
        
        return jsonify({
            'success': True,
            'call_sid': result.get('twilio_call_sid'),
            'call_log_id': result.get('call_log_id'),
            'message': f'Test call initiated to {phone_number}'
        })
        
    except Exception as e:
        logger.error(f"Error making test call: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== TWILIO WEBHOOK ROUTES ====================

@app.route('/twilio_voice_webhook', methods=['GET', 'POST'])
def twilio_voice_webhook():
    """Handle Twilio voice webhook with continuous conversation"""
    call_log_id = request.args.get('call_log_id')
    call_sid = request.values.get('CallSid')
    call_status = request.values.get('CallStatus')
    
    logger.info(f"Voice webhook: CallSid={call_sid}, Status={call_status}, Method={request.method}")
    
    response = TwiMLResponse()
    
    try:
        if request.method == 'GET' or call_status in ['ringing', 'in-progress']:
            # Get conversation manager
            conv_manager = get_conversation_manager(call_sid)
            
            # Initial welcome message
            welcome_message = (
                "Hello! This is Sarah from Field Services Nationwide. "
                "I'm calling about a Senior Network Technician position in Chicago "
                "paying $75 per hour. Is this a good time to chat for just a minute?"
            )
            
            conv_manager.add_message("AI", welcome_message)
            
            # Update call log with initial message
            if call_log_id:
                try:
                    call_log = CallLog.query.get(call_log_id)
                    if call_log:
                        call_log.ai_conversation = f"AI: {welcome_message}"
                        call_log.call_status = 'connected'
                        db.session.commit()
                except Exception as e:
                    logger.error(f"Error updating call log: {e}")
            
            response.say(welcome_message, voice='alice', language='en-US')
            
            gather = response.gather(
                input='speech',
                timeout=10,
                speech_timeout='auto',
                action=url_for('handle_speech', call_sid=call_sid, call_log_id=call_log_id),
                method='POST'
            )
            
            response.say("I didn't hear a response. I'll have a recruiter call you back later. Have a great day!", voice='alice')
            response.hangup()
            
        else:
            # Handle status updates
            if call_log_id:
                try:
                    call_log = CallLog.query.get(call_log_id)
                    if call_log:
                        call_log.call_status = call_status
                        if call_status == 'completed':
                            call_duration = request.values.get('CallDuration')
                            if call_duration:
                                call_log.call_duration = int(call_duration)
                        db.session.commit()
                except Exception as e:
                    logger.error(f"Error updating call status: {e}")
                    db.session.rollback()
            
            return '', 200
            
    except Exception as e:
        logger.error(f"Error in voice webhook: {e}")
        response.say("Sorry, there was a technical issue. We'll call you back soon.", voice='alice')
        response.hangup()
    
    return str(response), 200

@app.route('/handle_speech', methods=['POST'])
def handle_speech():
    """Handle speech input and generate AI response"""
    call_sid = request.args.get('call_sid')
    call_log_id = request.args.get('call_log_id')
    speech_result = request.values.get('SpeechResult', '').strip()
    
    logger.info(f"Speech from {call_sid}: '{speech_result}'")
    
    response = TwiMLResponse()
    
    try:
        if not speech_result:
            response.say("I didn't catch that. Let me have a recruiter call you back. Thank you!", voice='alice')
            response.hangup()
            return str(response), 200
        
        # Get conversation manager
        conv_manager = get_conversation_manager(call_sid)
        conv_manager.add_message("Technician", speech_result)
        
        # Check conversation length
        if len(conv_manager.conversation_history) > 12:
            response.say("Thank you for your time! A recruiter will follow up with you soon. Have a great day!", voice='alice')
            response.hangup()
            return str(response), 200
        
        # Generate AI response
        ai_response = generate_ai_response(speech_result, conv_manager)
        conv_manager.add_message("AI", ai_response)
        
        # Update call log
        if call_log_id:
            try:
                call_log = CallLog.query.get(call_log_id)
                if call_log:
                    conversation_text = ""
                    for msg in conv_manager.conversation_history:
                        conversation_text += f"{msg['speaker']}: {msg['message']}\n"
                    call_log.ai_conversation = conversation_text
                    
                    # Determine call result based on conversation
                    if 'interested' in speech_result.lower() or 'yes' in speech_result.lower():
                        call_log.call_result = 'interested'
                    elif 'not interested' in speech_result.lower() or 'no' in speech_result.lower():
                        call_log.call_result = 'not_interested'
                    elif 'call back' in speech_result.lower() or 'later' in speech_result.lower():
                        call_log.call_result = 'callback'
                    
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error updating conversation: {e}")
                db.session.rollback()
        
        # Determine if conversation should end
        should_end = should_end_conversation(speech_result, ai_response)
        
        response.say(ai_response, voice='alice', language='en-US')
        
        if should_end:
            response.hangup()
        else:
            gather = response.gather(
                input='speech',
                timeout=8,
                speech_timeout='auto',
                action=url_for('handle_speech', call_sid=call_sid, call_log_id=call_log_id),
                method='POST'
            )
            response.say("Thank you for your time. A recruiter will be in touch soon!", voice='alice')
            response.hangup()
        
    except Exception as e:
        logger.error(f"Error handling speech: {e}")
        response.say("Thank you for your time. We'll follow up soon!", voice='alice')
        response.hangup()
    
    return str(response), 200

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
        
        request_data = request.get_json() or {}
        batch_size = min(request_data.get('batch_size', 5), 10)
        
        logger.info(f"Starting calling for campaign {campaign_id}, batch size: {batch_size}")
        
        called_ids = [log.technician_id for log in 
                      CallLog.query.filter_by(campaign_id=campaign.id).all()]
        
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
        
        random.shuffle(qualified_pool)
        selected_techs = qualified_pool[:batch_size]
        
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
        expansion = min(request_data.get('expansion_miles', 20), 50)
        
        campaign.current_radius += expansion
        db.session.commit()
        
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

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'twilio_configured': twilio_client is not None,
        'openai_configured': openai_client is not None,
        'active_conversations': len(conversations)
    })

# ==================== IMPORT FUNCTION ====================

def import_technicians_from_df(df):
    """Import technicians from DataFrame with better error handling."""
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

            existing_tech = Technician.query.filter(
                (Technician.mobile_phone == mobile_phone) |
                ((Technician.email == email) if email else False)
            ).first()

            if existing_tech:
                logger.info(f"Technician '{tech_name}' already exists. Skipping.")
                continue
            
            city = str(row.get('Address - City', '')).strip()
            state = str(row.get('Address - State/Province', '')).strip()
            zip_code = str(row.get('Address - Zip Code', '')).strip()
            
            lat, lon = None, None
            if city and state and zip_code:
                full_address = f"{city}, {state} {zip_code}, USA"
                lat, lon = get_coordinates(full_address)
            elif zip_code:
                lat, lon = get_coordinates(f"{zip_code}, USA")
            
            exp_str = str(row.get('Number of Years of Experience in the IT Industry', '')).strip()
            exp_years = 0
            if exp_str:
                try:
                    exp_years = max(0, int(float(exp_str)))
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse experience '{exp_str}' for {tech_name}")

            drug_screening = str(row.get('Able to Pass a Drug Screening?', '')).strip().lower() == 'yes'
            background_check = str(row.get('Able to Pass a Background Check?', '')).strip().lower() == 'yes'

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
            db.create_all()
            create_admin_user()
        
        port = int(os.environ.get('PORT', 5000))
        debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
        
        logger.info(f"Starting Flask app on port {port}, debug={debug_mode}")
        app.run(host='0.0.0.0', port=port, debug=debug_mode)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
