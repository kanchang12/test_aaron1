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
from twilio.twiml.voice_response import VoiceResponse as TwiMLResponse
import requests

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm, CSRFProtect
from flask_migrate import Migrate
from wtforms import StringField, PasswordField, SelectField, TextAreaField, IntegerField, FloatField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fsn_calling.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = True

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

# Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# Initialize clients
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None
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

# ==================== CALLING SYSTEM ====================

def get_coordinates(zip_code):
    try:
        location = geolocator.geocode(zip_code)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

def find_qualified_technicians(work_order, radius_miles, exclude_called_ids=None):
    if exclude_called_ids is None:
        exclude_called_ids = []
    
    query = Technician.query.filter(Technician.is_active == True)
    
    if exclude_called_ids:
        query = query.filter(~Technician.id.in_(exclude_called_ids))
    
    all_techs = query.all()
    qualified_pool = []
    
    for tech in all_techs:
        if not tech.latitude or not tech.longitude:
            continue
            
        distance = geodesic(
            (work_order.job_latitude, work_order.job_longitude),
            (tech.latitude, tech.longitude)
        ).miles
        
        if distance > radius_miles:
            continue
        
        # Check requirements
        reqs = work_order.requirements or {}
        if reqs.get('drug_screen', False) and not tech.drug_screening:
            continue
        if reqs.get('background_check', False) and not tech.background_check:
            continue
        
        # Check skills
        if work_order.required_skills:
            tech_skills = tech.skills or {}
            meets_skills = True
            for skill in work_order.required_skills:
                skill_value = tech_skills.get(skill, '0/10')
                try:
                    rating = int(skill_value.split('/')[0]) if '/' in str(skill_value) else 0
                    if rating < work_order.minimum_skill_level:
                        meets_skills = False
                        break
                except:
                    meets_skills = False
                    break
            
            if not meets_skills:
                continue
        
        qualified_pool.append({
            'technician': tech,
            'distance': distance
        })
    
    return qualified_pool

def make_ai_call(campaign, tech_data):
    tech = tech_data['technician']
    
    # Create call log
    call_log = CallLog(
        campaign_id=campaign.id,
        technician_id=tech.id,
        phone_number=tech.mobile_phone,
        distance_miles=tech_data['distance'],
        call_status='calling'
    )
    db.session.add(call_log)
    db.session.commit()
    
    try:
        # Simulate AI conversation (replace with actual Twilio/OpenRouter)
        responses = ['interested', 'not_interested', 'callback', 'unavailable']
        weights = [0.25, 0.45, 0.20, 0.10]
        result = random.choices(responses, weights=weights)[0]
        
        call_log.call_status = 'answered'
        call_log.call_result = result
        call_log.call_duration = random.randint(90, 240)
        
        if result == 'interested':
            campaign.current_responses += 1
        
        db.session.commit()
        
        logger.info(f"Call completed: {tech.name} -> {result}")
        
        return {
            'technician_id': tech.id,
            'name': tech.name,
            'phone': tech.mobile_phone,
            'call_result': result,
            'distance': tech_data['distance']
        }
        
    except Exception as e:
        call_log.call_status = 'failed'
        db.session.commit()
        logger.error(f"Call failed for {tech.name}: {e}")
        return {
            'technician_id': tech.id,
            'name': tech.name,
            'call_result': 'failed',
            'error': str(e)
        }

# ==================== ROUTES ====================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    current_user.last_login = datetime.utcnow()
    db.session.commit()
    
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
        return redirect(url_for('campaign_dashboard', campaign_id=existing_campaign.id))
    
    campaign = CallCampaign(work_order_id=work_order.id, target_responses=5)
    db.session.add(campaign)
    db.session.commit()
    
    flash('Campaign started successfully!', 'success')
    return redirect(url_for('campaign_dashboard', campaign_id=campaign.id))

@app.route('/campaign/<int:campaign_id>')
@login_required
def campaign_dashboard(campaign_id):
    campaign = CallCampaign.query.get_or_404(campaign_id)
    work_order = campaign.work_order
    
    if not current_user.is_admin() and work_order.created_by != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('index'))
    
    call_logs = CallLog.query.filter_by(campaign_id=campaign.id).order_by(CallLog.called_at.desc()).all()
    
    stats = {
        'total_calls': len(call_logs),
        'interested': len([log for log in call_logs if log.call_result == 'interested']),
        'not_interested': len([log for log in call_logs if log.call_result == 'not_interested']),
        'callbacks': len([log for log in call_logs if log.call_result == 'callback']),
        'current_radius': campaign.current_radius,
        'success_rate': (len([log for log in call_logs if log.call_result == 'interested']) / len(call_logs) * 100) if call_logs else 0
    }
    
    return render_template('campaign/dashboard.html', 
                         campaign=campaign,
                         work_order=work_order,
                         call_logs=call_logs,
                         stats=stats)

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
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
        else:
            flash('Please upload an Excel (.xlsx) file!', 'error')
    
    return render_template('technicians/upload.html')

# ==================== API ENDPOINTS ====================

@app.route('/api/start_calling/<int:campaign_id>', methods=['POST'])
@login_required
def api_start_calling(campaign_id):
    campaign = CallCampaign.query.get_or_404(campaign_id)
    
    if not current_user.is_admin() and campaign.work_order.created_by != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        batch_size = request.json.get('batch_size', 10)
        
        # Get already called technician IDs
        called_ids = [log.technician_id for log in 
                     CallLog.query.filter_by(campaign_id=campaign.id).all()]
        
        # Find qualified pool
        qualified_pool = find_qualified_technicians(
            campaign.work_order,
            campaign.current_radius,
            exclude_called_ids=called_ids
        )
        
        if not qualified_pool:
            return jsonify({
                'status': 'no_candidates',
                'pool_size': 0,
                'message': f'No qualified technicians found within {campaign.current_radius} miles'
            })
        
        # RANDOM SELECTION FOR FAIRNESS
        random.shuffle(qualified_pool)
        selected_techs = qualified_pool[:batch_size]
        
        # Execute calls
        results = []
        for tech_data in selected_techs:
            result = make_ai_call(campaign, tech_data)
            results.append(result)
        
        return jsonify({
            'status': 'completed',
            'pool_size': len(qualified_pool),
            'called': len(selected_techs),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Calling failed: {e}")
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
        
        # Execute calling round with new radius
        called_ids = [log.technician_id for log in 
                     CallLog.query.filter_by(campaign_id=campaign.id).all()]
        
        qualified_pool = find_qualified_technicians(
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
        return jsonify({'error': str(e)}), 500

# ==================== HELPER FUNCTIONS ====================

def import_technicians_from_df(df):
    imported_count = 0
    
    for _, row in df.iterrows():
        try:
            if pd.isna(row.get('Name of Technician')):
                continue
            
            zip_code = str(row.get('Address - Zip Code', '')).strip()
            lat, lon = get_coordinates(zip_code) if zip_code else (None, None)
            
            exp_str = str(row.get('Number of Years of Experience in the IT Industry', '0'))
            exp_years = int(''.join(filter(str.isdigit, exp_str))) if exp_str else 0
            
            skills = {}
            skill_columns = [
                'POS (Point of Sale Machines)', 'Laptop Repair', 'Network Troubleshooting',
                'Security Cameras', 'Cat5/6', 'Server Programming'
            ]
            
            for skill in skill_columns:
                if skill in row and pd.notna(row[skill]):
                    skills[skill] = str(row[skill]).strip()
            
            technician = Technician(
                name=str(row.get('Name of Technician', '')).strip(),
                email=str(row.get('Email', '')).strip() or None,
                mobile_phone=str(row.get('Mobile/Cell Phone', '')).strip(),
                city=str(row.get('Address - City', '')).strip() or None,
                state=str(row.get('Address - State/Province', '')).strip() or None,
                zip_code=zip_code or None,
                latitude=lat,
                longitude=lon,
                experience_years=exp_years,
                drug_screening=str(row.get('Able to Pass a Drug Screening?', '')).lower() == 'yes',
                background_check=str(row.get('Able to Pass a Background Check?', '')).lower() == 'yes',
                skills=skills
            )
            
            db.session.add(technician)
            imported_count += 1
            
            if imported_count % 100 == 0:
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error importing technician: {e}")
            continue
    
    db.session.commit()
    return imported_count

def create_admin_user():
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

# Health check
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    with app.app_context():

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
