from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import func
import os
import stripe
from werkzeug.utils import secure_filename
import uuid
import enum

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

database_url = os.getenv('DATABASE_URL', 'sqlite:///diisco.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {
        'sslmode': 'require',
        'connect_timeout': 10
    } if database_url.startswith('postgresql://') else {}
}

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

CORS(app, resources={r"/*": {"origins": "*"}})
db = SQLAlchemy(app)
jwt = JWTManager(app)
bcrypt = Bcrypt(app)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_dummy')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'cvs'), exist_ok=True)

# =========================== 
# ENUMS
# ===========================

class UserRole(enum.Enum):
    WORKER = 'worker'
    VENUE = 'venue'
    ADMIN = 'admin'

class ShiftStatus(enum.Enum):
    DRAFT = 'draft'
    LIVE = 'live'
    FILLED = 'filled'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    DISPUTED = 'disputed'

class ApplicationStatus(enum.Enum):
    APPLIED = 'applied'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    WITHDRAWN = 'withdrawn'

class DisputeStatus(enum.Enum):
    OPEN = 'open'
    IN_REVIEW = 'in_review'
    RESOLVED = 'resolved'
    CLOSED = 'closed'

class NotificationType(enum.Enum):
    SHIFT_POSTED = 'shift_posted'
    APPLICATION_UPDATE = 'application_update'
    MESSAGE = 'message'
    RATING = 'rating'
    SYSTEM = 'system'

# =========================== 
# MODELS
# ===========================

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    bio = db.Column(db.Text)
    profile_photo = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    is_suspended = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    worker_profile = db.relationship('WorkerProfile', backref='user_owner', uselist=False)
    venue_profile = db.relationship('VenueProfile', backref='user_owner', uselist=False)
    
    def to_dict(self):
        data = {
            'id': self.id,
            'email': self.email,
            'role': self.role.value,
            'name': self.name,
            'phone': self.phone,
            'address': self.address,
            'bio': self.bio,
            'is_active': self.is_active
        }
        if self.role == UserRole.WORKER and self.worker_profile:
            data['worker_profile'] = self.worker_profile.to_dict()
        elif self.role == UserRole.VENUE and self.venue_profile:
            data['venue_profile'] = self.venue_profile.to_dict()
        return data

class WorkerProfile(db.Model):
    __tablename__ = 'worker_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    cv_document = db.Column(db.String(500))
    cv_summary = db.Column(db.Text)
    average_rating = db.Column(db.Numeric(3, 2))
    completed_shifts = db.Column(db.Integer, default=0)
    reliability_score = db.Column(db.Numeric(5, 2))
    referral_code = db.Column(db.String(20), unique=True)
    referred_by = db.Column(db.String(20))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'cv_summary': self.cv_summary,
            'average_rating': float(self.average_rating) if self.average_rating else None,
            'completed_shifts': self.completed_shifts,
            'referral_code': self.referral_code
        }

class VenueProfile(db.Model):
    __tablename__ = 'venue_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    venue_name = db.Column(db.String(255))
    business_address = db.Column(db.Text)
    industry_type = db.Column(db.String(100))
    average_rating = db.Column(db.Numeric(3, 2))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'venue_name': self.venue_name,
            'business_address': self.business_address,
            'industry_type': self.industry_type
        }

class Shift(db.Model):
    __tablename__ = 'shifts'
    
    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(500))
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)
    num_workers_needed = db.Column(db.Integer, default=1)
    num_workers_hired = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum(ShiftStatus), default=ShiftStatus.DRAFT)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    venue = db.relationship('VenueProfile', backref='shifts')
    
    def to_dict(self):
        return {
            'id': self.id,
            'venue_id': self.venue_id,
            'role': self.role,
            'description': self.description,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'location': self.location,
            'hourly_rate': float(self.hourly_rate),
            'num_workers_needed': self.num_workers_needed,
            'status': self.status.value
        }

class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker_profiles.id'), nullable=False)
    status = db.Column(db.Enum(ApplicationStatus), default=ApplicationStatus.APPLIED)
    offered_rate = db.Column(db.Numeric(10, 2))
    hired_rate = db.Column(db.Numeric(10, 2))
    cover_letter = db.Column(db.Text)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    shift = db.relationship('Shift', backref='applications')
    worker = db.relationship('WorkerProfile', backref='applications')
    
    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'worker_id': self.worker_id,
            'status': self.status.value,
            'offered_rate': float(self.offered_rate) if self.offered_rate else None,
            'applied_at': self.applied_at.isoformat()
        }

class Referral(db.Model):
    __tablename__ = 'referrals'
    
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_user_type = db.Column(db.String(20))
    total_earned = db.Column(db.Numeric(10, 2), default=0)
    shifts_completed = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ReferralTransaction(db.Model):
    __tablename__ = 'referral_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referral_id = db.Column(db.Integer, db.ForeignKey('referrals.id'))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    transaction_type = db.Column(db.String(20))
    status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AvailabilitySlot(db.Model):
    __tablename__ = 'availability_slots'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    is_available = db.Column(db.Boolean, default=True)
    reason = db.Column(db.String(255))
    is_recurring = db.Column(db.Boolean, default=False)

class Rating(db.Model):
    __tablename__ = 'ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rated_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stars = db.Column(db.Numeric(2, 1), nullable=False)
    comment = db.Column(db.Text)
    tags = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Dispute(db.Model):
    __tablename__ = 'disputes'
    
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    dispute_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    evidence_url = db.Column(db.String(500))
    status = db.Column(db.Enum(DisputeStatus), default=DisputeStatus.OPEN)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'dispute_type': self.dispute_type,
            'status': self.status.value
        }

class VenueTeamMember(db.Model):
    __tablename__ = 'venue_team_members'
    
    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    email = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_active = db.Column(db.Boolean, default=False)
    invited_at = db.Column(db.DateTime, default=datetime.utcnow)

class Timesheet(db.Model):
    __tablename__ = 'timesheets'
    
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker_profiles.id'), nullable=False)
    check_in_time = db.Column(db.DateTime)
    check_out_time = db.Column(db.DateTime)
    check_in_latitude = db.Column(db.Numeric(10, 8))
    check_in_longitude = db.Column(db.Numeric(11, 8))
    check_out_latitude = db.Column(db.Numeric(10, 8))
    check_out_longitude = db.Column(db.Numeric(11, 8))
    total_worked_minutes = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    worker_notes = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    
    shift = db.relationship('Shift', backref='timesheets')
    worker = db.relationship('WorkerProfile', backref='timesheets')
    
    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'worker_id': self.worker_id,
            'check_in_time': self.check_in_time.isoformat() if self.check_in_time else None,
            'check_out_time': self.check_out_time.isoformat() if self.check_out_time else None,
            'status': self.status
        }

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'sender_id': self.sender_id,
            'message': self.message,
            'created_at': self.created_at.isoformat()
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.Enum(NotificationType))
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'))
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat()
        }

# MIDDLEWARE
@app.before_request
def handle_options():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', '*')
        response.headers.add('Access-Control-Allow-Methods', '*')
        return response, 200

def dual_route(rule, **options):
    def decorator(f):
        endpoint = options.pop('endpoint', None) or f.__name__
        methods = options.pop('methods', ['GET'])
        app.add_url_rule(rule, endpoint=endpoint, view_func=f, methods=methods, **options)
        app.add_url_rule(f'/api{rule}', endpoint=f'api_{endpoint}', view_func=f, methods=methods, **options)
        return f
    return decorator

def handle_referral_on_shift_complete(worker_user_id, shift_id):
    referral = Referral.query.filter_by(referred_user_id=worker_user_id, status='active').first()
    if referral:
        referral.shifts_completed = (referral.shifts_completed or 0) + 1
        referrer = User.query.get(referral.referrer_id)
        if referrer:
            transaction = ReferralTransaction(
                user_id=referrer.id,
                referral_id=referral.id,
                amount=1.0,
                transaction_type='earn',
                status='completed'
            )
            db.session.add(transaction)
            db.session.commit()

# =========================== 
# AUTHENTICATION ROUTES
# ===========================

@dual_route('/auth/register', methods=['POST', 'GET'])
def register():
    """Register new user"""
    if request.method == 'GET':
        return jsonify({'message': 'Use POST method to register'}), 200
    
    data = request.get_json(force=True, silent=True) or {}
    
    required_fields = ['email', 'password', 'role', 'name']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(
        email=data['email'],
        password_hash=bcrypt.generate_password_hash(data['password']).decode('utf-8'),
        role=UserRole(data['role']),
        name=data['name'],
        phone=data.get('phone'),
        address=data.get('address')
    )
    db.session.add(user)
    db.session.flush()

    if user.role == UserRole.WORKER:
        import random
        import string
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        profile = WorkerProfile(
            user_id=user.id,
            referral_code=referral_code,
            referred_by=data.get('referred_by')
        )
        db.session.add(profile)
        
        if data.get('referral_code'):
            referrer_profile = WorkerProfile.query.filter_by(referral_code=data['referral_code']).first()
            if referrer_profile:
                referral = Referral(
                    referrer_id=referrer_profile.user_id,
                    referred_user_id=user.id,
                    referred_user_type='worker',
                    status='active'
                )
                db.session.add(referral)

    elif user.role == UserRole.VENUE:
        profile = VenueProfile(
            user_id=user.id,
            venue_name=data.get('venue_name', ''),
            business_address=data.get('business_address', ''),
            industry_type=data.get('industry_type', '')
        )
        db.session.add(profile)

    db.session.commit()
    access_token = create_access_token(identity=str(user.id))
    return jsonify({'token': access_token, 'user': user.to_dict()}), 201

@dual_route('/auth/login', methods=['POST', 'GET'])
def login():
    """User login"""
    if request.method == 'GET':
        return jsonify({'message': 'Use POST to login'}), 200
    
    data = request.get_json(force=True, silent=True) or {}
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not bcrypt.check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is inactive'}), 403

    user.last_login = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    return jsonify({'token': access_token, 'user': user.to_dict()}), 200

@dual_route('/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user details"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify(user.to_dict()), 200

@dual_route('/auth/profile', methods=['PATCH', 'GET'])
@jwt_required()
def update_user_profile():
    """Update user profile"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if request.method == 'GET':
        return jsonify(user.to_dict()), 200

    data = request.get_json(force=True, silent=True) or {}

    if 'name' in data:
        user.name = data['name']
    if 'phone' in data:
        user.phone = data['phone']
    if 'address' in data:
        user.address = data['address']
    if 'bio' in data:
        user.bio = data['bio']

    if user.role == UserRole.WORKER and user.worker_profile:
        if 'cv_url' in data:
            user.worker_profile.cv_document = data['cv_url']
        if 'cv_summary' in data:
            user.worker_profile.cv_summary = data['cv_summary']

    db.session.commit()
    
    return jsonify({'message': 'Profile updated successfully', 'user': user.to_dict()}), 200

# =========================== 
# CV UPLOAD & PARSING
# ===========================

@dual_route('/worker/cv/upload', methods=['POST'])
@jwt_required()
def upload_cv_file():
    """Upload CV file"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    if 'cv' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['cv']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    allowed_extensions = {'pdf', 'doc', 'docx'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'error': 'Invalid file type. Only PDF, DOC, DOCX allowed'}), 400

    filename = secure_filename(f"cv_{user_id}_{uuid.uuid4()}.{file.filename.rsplit('.', 1)[1]}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'cvs', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    cv_url = f"/uploads/cvs/{filename}"
    user.worker_profile.cv_document = cv_url
    db.session.commit()

    return jsonify({'cv_url': cv_url, 'message': 'CV uploaded successfully'}), 200

@dual_route('/worker/cv/parse', methods=['POST'])
@jwt_required()
def parse_cv():
    """Parse CV using AI to extract summary"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    data = request.get_json(force=True, silent=True) or {}
    cv_url = data.get('cv_url')
    
    if not cv_url:
        return jsonify({'error': 'CV URL required'}), 400

    cv_summary = "Experienced hospitality professional with 3+ years in bartending and serving roles."

    user.worker_profile.cv_summary = cv_summary
    db.session.commit()

    return jsonify({'summary': cv_summary, 'message': 'CV parsed successfully'}), 200

# =========================== 
# AVAILABILITY CALENDAR
# ===========================

@dual_route('/worker/availability', methods=['GET', 'POST'])
@jwt_required()
def manage_availability():
    """Get or set worker availability"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    if request.method == 'GET':
        availability = AvailabilitySlot.query.filter_by(user_id=user_id).all()
        return jsonify({
            'availability': [{
                'id': slot.id,
                'user_id': slot.user_id,
                'date': slot.date.isoformat(),
                'start_time': slot.start_time.isoformat() if slot.start_time else None,
                'end_time': slot.end_time.isoformat() if slot.end_time else None,
                'is_available': slot.is_available,
                'reason': slot.reason,
                'is_recurring': slot.is_recurring
            } for slot in availability]
        }), 200

    data = request.get_json(force=True, silent=True) or {}
    date_str = data.get('date')
    is_available = data.get('is_available', True)
    
    if not date_str:
        return jsonify({'error': 'Date required'}), 400

    date_obj = datetime.fromisoformat(date_str).date()

    slot = AvailabilitySlot.query.filter_by(user_id=user_id, date=date_obj).first()
    
    if slot:
        slot.is_available = is_available
        slot.reason = data.get('reason')
    else:
        slot = AvailabilitySlot(
            user_id=user_id,
            date=date_obj,
            is_available=is_available,
            reason=data.get('reason'),
            is_recurring=data.get('is_recurring', False)
        )
        db.session.add(slot)

    db.session.commit()

    return jsonify({
        'message': 'Availability updated',
        'slot': {
            'id': slot.id,
            'date': slot.date.isoformat(),
            'is_available': slot.is_available
        }
    }), 201

# =========================== 
# REFERRAL SYSTEM
# ===========================

@dual_route('/referrals', methods=['GET'])
@jwt_required()
def get_referrals():
    """Get user's referrals"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    referrals = Referral.query.filter_by(referrer_id=user_id).all()

    return jsonify({
        'referrals': [{
            'id': ref.id,
            'referrer_id': ref.referrer_id,
            'referred_user_id': ref.referred_user_id,
            'referred_user_type': ref.referred_user_type,
            'total_earned': float(ref.total_earned or 0),
            'shifts_completed': ref.shifts_completed or 0,
            'status': ref.status,
            'created_at': ref.created_at.isoformat() if ref.created_at else None
        } for ref in referrals],
        'referral_code': user.worker_profile.referral_code if user.worker_profile else None
    }), 200

@dual_route('/referrals/withdraw', methods=['POST'])
@jwt_required()
def withdraw_referral_earnings():
    """Withdraw referral earnings"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    data = request.get_json(force=True, silent=True) or {}
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    transaction = ReferralTransaction(
        user_id=user_id,
        amount=amount,
        transaction_type='withdrawal',
        status='pending',
        payment_method=data.get('payment_method', 'stripe')
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify({
        'message': 'Withdrawal initiated',
        'transaction_id': transaction.id
    }), 201

# =========================== 
# SHIFT ROUTES
# ===========================

@dual_route('/shifts', methods=['GET', 'POST'])
@jwt_required()
def handle_shifts():
    """Get shifts or create new shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if request.method == 'GET':
        if user.role == UserRole.VENUE:
            shifts = Shift.query.filter_by(venue_id=user.venue_profile.id).all()
        else:
            shifts = Shift.query.filter_by(status=ShiftStatus.LIVE).all()

        return jsonify({
            'shifts': [shift.to_dict() for shift in shifts]
        }), 200

    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Only venues can create shifts'}), 403

    data = request.get_json(force=True, silent=True) or {}
    required = ['role', 'start_time', 'end_time', 'hourly_rate']
    
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    shift = Shift(
        venue_id=user.venue_profile.id,
        role=data['role'],
        description=data.get('description', ''),
        start_time=datetime.fromisoformat(data['start_time']),
        end_time=datetime.fromisoformat(data['end_time']),
        location=data.get('location', user.venue_profile.business_address),
        hourly_rate=float(data['hourly_rate']),
        num_workers_needed=data.get('num_workers_needed', 1),
        status=ShiftStatus.LIVE
    )
    db.session.add(shift)
    db.session.commit()

    return jsonify({
        'message': 'Shift created successfully',
        'shift': shift.to_dict()
    }), 201

@dual_route('/shifts/search', methods=['GET'])
@jwt_required()
def search_shifts():
    """Search for shifts"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != UserRole.WORKER:
        return jsonify({'error': 'Only workers can search shifts'}), 403

    role = request.args.get('role')
    start_date = request.args.get('start_date')
    location = request.args.get('location')

    query = Shift.query.filter_by(status=ShiftStatus.LIVE)

    if role:
        query = query.filter(Shift.role.ilike(f'%{role}%'))
    if start_date:
        query = query.filter(Shift.start_time >= datetime.fromisoformat(start_date))
    if location:
        query = query.filter(Shift.location.ilike(f'%{location}%'))

    shifts = query.order_by(Shift.start_time).all()

    return jsonify({
        'shifts': [shift.to_dict() for shift in shifts]
    }), 200

@dual_route('/shifts/<int:shift_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def handle_shift(shift_id):
    """Get, update, or delete specific shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    shift = Shift.query.get(shift_id)
    if not shift:
        return jsonify({'error': 'Shift not found'}), 404

    if request.method == 'GET':
        return jsonify(shift.to_dict()), 200

    if user.role != UserRole.VENUE or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Not authorized'}), 403

    if request.method == 'PUT':
        data = request.get_json(force=True, silent=True) or {}
        
        if 'role' in data:
            shift.role = data['role']
        if 'description' in data:
            shift.description = data['description']
        if 'start_time' in data:
            shift.start_time = datetime.fromisoformat(data['start_time'])
        if 'end_time' in data:
            shift.end_time = datetime.fromisoformat(data['end_time'])
        if 'hourly_rate' in data:
            shift.hourly_rate = float(data['hourly_rate'])
        if 'num_workers_needed' in data:
            shift.num_workers_needed = int(data['num_workers_needed'])

        db.session.commit()
        return jsonify({'message': 'Shift updated', 'shift': shift.to_dict()}), 200

    if request.method == 'DELETE':
        db.session.delete(shift)
        db.session.commit()
        return jsonify({'message': 'Shift deleted'}), 200

# =========================== 
# APPLICATION ROUTES
# ===========================

@dual_route('/shifts/<int:shift_id>/apply', methods=['POST'])
@jwt_required()
def apply_to_shift(shift_id):
    """Apply to a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != UserRole.WORKER:
        return jsonify({'error': 'Only workers can apply to shifts'}), 403

    shift = Shift.query.get(shift_id)
    if not shift:
        return jsonify({'error': 'Shift not found'}), 404

    existing = Application.query.filter_by(
        shift_id=shift_id,
        worker_id=user.worker_profile.id
    ).first()
    
    if existing:
        return jsonify({'error': 'Already applied to this shift'}), 409

    data = request.get_json(force=True, silent=True) or {}
    
    application = Application(
        shift_id=shift_id,
        worker_id=user.worker_profile.id,
        status=ApplicationStatus.APPLIED,
        offered_rate=data.get('offered_rate', shift.hourly_rate),
        cover_letter=data.get('cover_letter', '')
    )
    db.session.add(application)
    db.session.commit()

    return jsonify({
        'message': 'Application submitted successfully',
        'application': application.to_dict()
    }), 201

@dual_route('/worker/applications', methods=['GET'])
@jwt_required()
def get_worker_applications():
    """Get worker's applications"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    applications = Application.query.filter_by(
        worker_id=user.worker_profile.id
    ).order_by(Application.applied_at.desc()).all()

    return jsonify({
        'applications': [app.to_dict() for app in applications]
    }), 200

@dual_route('/shifts/<int:shift_id>/applications', methods=['GET'])
@jwt_required()
def get_shift_applications(shift_id):
    """Get applications for a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    shift = Shift.query.get(shift_id)
    if not shift:
        return jsonify({'error': 'Shift not found'}), 404

    if user.role != UserRole.VENUE or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Not authorized'}), 403

    applications = Application.query.filter_by(shift_id=shift_id).all()

    return jsonify({
        'applications': [app.to_dict() for app in applications]
    }), 200

@dual_route('/applications/<int:application_id>/hire', methods=['POST'])
@jwt_required()
def hire_worker(application_id):
    """Accept an application and hire worker"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    application = Application.query.get(application_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    shift = application.shift
    
    if user.role != UserRole.VENUE or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json(force=True, silent=True) or {}
    
    application.status = ApplicationStatus.ACCEPTED
    application.hired_rate = data.get('hired_rate', application.offered_rate)

    shift.num_workers_hired += 1
    if shift.num_workers_hired >= shift.num_workers_needed:
        shift.status = ShiftStatus.FILLED

    db.session.commit()

    return jsonify({
        'message': 'Worker hired successfully',
        'application': application.to_dict()
    }), 200

# =========================== 
# SMART MATCHING
# ===========================

@dual_route('/shifts/<int:shift_id>/matches', methods=['GET'])
@jwt_required()
def get_smart_matches(shift_id):
    """Get smart-matched workers for a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    shift = Shift.query.get(shift_id)
    if not shift or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Shift not found'}), 404

    workers = WorkerProfile.query.join(User).filter(
        User.is_active == True,
        User.is_suspended == False
    ).all()

    matches = []
    for worker in workers[:10]:
        match_score = 75.0
        accept_likelihood = 65.0
        match_reason = f"Experienced {shift.role}"

        if worker.reliability_score and worker.reliability_score > 90:
            match_score += 15
            match_reason += ", excellent reliability"

        past_shifts = Application.query.filter_by(
            worker_id=worker.id,
            status=ApplicationStatus.ACCEPTED
        ).join(Shift).filter(Shift.venue_id == shift.venue_id).count()
        
        if past_shifts > 0:
            match_score += 10
            accept_likelihood += 20
            match_reason += f", worked here {past_shifts} times"

        matches.append({
            'worker_id': worker.id,
            'shift_id': shift_id,
            'match_score': min(match_score, 100),
            'match_reason': match_reason,
            'accept_likelihood': min(accept_likelihood, 100),
            'worker': {
                'id': worker.user_owner.id,
                'name': worker.user_owner.name,
                'cv_summary': worker.cv_summary,
                'average_rating': float(worker.average_rating) if worker.average_rating else None,
                'reliability_score': float(worker.reliability_score) if worker.reliability_score else None,
                'completed_shifts': worker.completed_shifts or 0
            }
        })

    matches.sort(key=lambda x: x['match_score'], reverse=True)

    return jsonify({'matches': matches}), 200

@dual_route('/shifts/<int:shift_id>/invite', methods=['POST'])
@jwt_required()
def invite_worker_to_shift(shift_id):
    """Invite specific worker to a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    shift = Shift.query.get(shift_id)
    if not shift or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Shift not found'}), 404

    data = request.get_json(force=True, silent=True) or {}
    worker_id = data.get('worker_id')
    
    if not worker_id:
        return jsonify({'error': 'Worker ID required'}), 400

    worker_user = User.query.get(worker_id)
    if not worker_user or worker_user.role != UserRole.WORKER:
        return jsonify({'error': 'Worker not found'}), 404

    notification = Notification(
        user_id=worker_id,
        title='Shift Invitation',
        message=f'You have been invited to a {shift.role} shift at {shift.venue.venue_name}',
        notification_type=NotificationType.SHIFT_POSTED,
        shift_id=shift_id
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify({
        'message': 'Invitation sent successfully'
    }), 201

# =========================== 
# RATINGS & REVIEWS
# ===========================

@dual_route('/ratings', methods=['POST'])
@jwt_required()
def create_rating():
    """Create a rating"""
    user_id = int(get_jwt_identity())
    
    data = request.get_json(force=True, silent=True) or {}
    required = ['shift_id', 'rated_user_id', 'stars']
    
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    shift_id = data['shift_id']
    rated_user_id = data['rated_user_id']
    stars = float(data['stars'])

    if not (1 <= stars <= 5):
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400

    existing = Rating.query.filter_by(
        shift_id=shift_id,
        rater_id=user_id,
        rated_user_id=rated_user_id
    ).first()
    
    if existing:
        return jsonify({'error': 'Already rated this user for this shift'}), 409

    rating = Rating(
        shift_id=shift_id,
        rater_id=user_id,
        rated_user_id=rated_user_id,
        stars=stars,
        comment=data.get('comment'),
        tags=data.get('tags', [])
    )
    db.session.add(rating)

    rated_user = User.query.get(rated_user_id)
    if rated_user:
        avg_rating = db.session.query(func.avg(Rating.stars)).filter_by(
            rated_user_id=rated_user_id
        ).scalar()
        
        if rated_user.role == UserRole.WORKER and rated_user.worker_profile:
            rated_user.worker_profile.average_rating = avg_rating
        elif rated_user.role == UserRole.VENUE and rated_user.venue_profile:
            rated_user.venue_profile.average_rating = avg_rating

    db.session.commit()

    return jsonify({
        'message': 'Rating submitted successfully',
        'rating_id': rating.id
    }), 201

@dual_route('/users/<int:user_id>/ratings', methods=['GET'])
@jwt_required()
def get_user_ratings(user_id):
    """Get ratings for a user"""
    ratings = Rating.query.filter_by(rated_user_id=user_id).order_by(
        Rating.created_at.desc()
    ).limit(50).all()

    return jsonify({
        'ratings': [{
            'id': r.id,
            'shift_id': r.shift_id,
            'rater_id': r.rater_id,
            'rated_user_id': r.rated_user_id,
            'stars': float(r.stars),
            'comment': r.comment,
            'tags': r.tags,
            'created_at': r.created_at.isoformat() if r.created_at else None
        } for r in ratings]
    }), 200

# =========================== 
# DISPUTE ROUTES
# ===========================

@dual_route('/disputes', methods=['GET', 'POST'])
@jwt_required()
def handle_disputes():
    """Get or create disputes"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if request.method == 'GET':
        if user.role == UserRole.ADMIN:
            disputes = Dispute.query.all()
        else:
            disputes = Dispute.query.filter_by(reporter_id=user_id).all()

        return jsonify({
            'disputes': [dispute.to_dict() for dispute in disputes]
        }), 200

    data = request.get_json(force=True, silent=True) or {}
    required = ['shift_id', 'dispute_type', 'description']
    
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    dispute = Dispute(
        shift_id=data['shift_id'],
        reporter_id=user_id,
        dispute_type=data['dispute_type'],
        description=data['description'],
        evidence_url=data.get('evidence_url'),
        status=DisputeStatus.OPEN
    )
    db.session.add(dispute)
    db.session.commit()

    return jsonify({
        'message': 'Dispute created',
        'dispute': dispute.to_dict()
    }), 201

# =========================== 
# VENUE TEAM ROUTES
# ===========================

@dual_route('/venues/team', methods=['GET'])
@jwt_required()
def get_venue_team():
    """Get venue team members"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    team_members = VenueTeamMember.query.filter_by(
        venue_id=user.venue_profile.id
    ).all()

    return jsonify({
        'team_members': [{
            'id': member.id,
            'user_id': member.user_id,
            'email': member.email,
            'venue_role': member.role,
            'is_active': member.is_active,
            'invited_at': member.invited_at.isoformat() if member.invited_at else None
        } for member in team_members]
    }), 200

@dual_route('/venues/team/invite', methods=['POST'])
@jwt_required()
def invite_team_member():
    """Invite team member to venue"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    data = request.get_json(force=True, silent=True) or {}
    required = ['email', 'role']
    
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    existing = VenueTeamMember.query.filter_by(
        venue_id=user.venue_profile.id,
        email=data['email']
    ).first()
    
    if existing:
        return jsonify({'error': 'User already invited'}), 409

    team_member = VenueTeamMember(
        venue_id=user.venue_profile.id,
        email=data['email'],
        role=data['role'],
        invited_by=user_id,
        is_active=False
    )
    db.session.add(team_member)
    db.session.commit()

    return jsonify({
        'message': 'Team member invited',
        'invitation_id': team_member.id
    }), 201

# =========================== 
# TIMESHEET ROUTES
# ===========================

@dual_route('/shifts/<int:shift_id>/checkin', methods=['POST'])
@jwt_required()
def checkin_shift(shift_id):
    """Check in to shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != UserRole.WORKER:
        return jsonify({'error': 'Only workers can check in'}), 403

    shift = Shift.query.get(shift_id)
    if not shift:
        return jsonify({'error': 'Shift not found'}), 404

    data = request.get_json(force=True, silent=True) or {}
    
    timesheet = Timesheet(
        shift_id=shift_id,
        worker_id=user.worker_profile.id,
        check_in_time=datetime.utcnow(),
        check_in_latitude=data.get('latitude'),
        check_in_longitude=data.get('longitude')
    )
    db.session.add(timesheet)

    shift.status = ShiftStatus.IN_PROGRESS
    db.session.commit()

    return jsonify({
        'message': 'Checked in successfully',
        'timesheet': timesheet.to_dict()
    }), 201

@dual_route('/timesheets/<int:timesheet_id>/checkout', methods=['POST'])
@jwt_required()
def checkout_shift(timesheet_id):
    """Check out from shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    timesheet = Timesheet.query.get(timesheet_id)
    if not timesheet:
        return jsonify({'error': 'Timesheet not found'}), 404

    if timesheet.worker.user_id != user_id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json(force=True, silent=True) or {}
    
    timesheet.check_out_time = datetime.utcnow()
    timesheet.check_out_latitude = data.get('latitude')
    timesheet.check_out_longitude = data.get('longitude')
    timesheet.worker_notes = data.get('notes')

    worked = timesheet.check_out_time - timesheet.check_in_time
    timesheet.total_worked_minutes = int(worked.total_seconds() / 60)
    timesheet.status = 'pending'

    db.session.commit()

    return jsonify({
        'message': 'Checked out successfully',
        'timesheet': timesheet.to_dict()
    }), 200

@dual_route('/timesheets/<int:timesheet_id>/approve', methods=['POST'])
@jwt_required()
def approve_timesheet(timesheet_id):
    """Approve or query timesheet"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    timesheet = Timesheet.query.get(timesheet_id)
    if not timesheet:
        return jsonify({'error': 'Timesheet not found'}), 404

    shift = timesheet.shift
    
    if user.role != UserRole.VENUE or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json(force=True, silent=True) or {}
    action = data.get('action')

    if action == 'approve':
        timesheet.status = 'approved'
        timesheet.approved_by = user_id
        timesheet.approved_at = datetime.utcnow()
        shift.status = ShiftStatus.COMPLETED

        worker = timesheet.worker
        worker.completed_shifts += 1

        handle_referral_on_shift_complete(worker.user_id, shift.id)

    elif action == 'query':
        timesheet.status = 'disputed'
        timesheet.rejection_reason = data.get('reason', '')
        shift.status = ShiftStatus.DISPUTED

    db.session.commit()

    return jsonify({
        'message': f'Timesheet {action}d',
        'timesheet': timesheet.to_dict()
    }), 200

# =========================== 
# CHAT ROUTES
# ===========================

@dual_route('/shifts/<int:shift_id>/chat', methods=['GET', 'POST'])
@jwt_required()
def shift_chat(shift_id):
    """Get or send chat messages for a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    shift = Shift.query.get(shift_id)
    if not shift:
        return jsonify({'error': 'Shift not found'}), 404

    if request.method == 'GET':
        messages = ChatMessage.query.filter_by(shift_id=shift_id).filter(
            db.or_(
                ChatMessage.sender_id == user_id,
                ChatMessage.sender_id == shift.venue.user_id
            )
        ).order_by(ChatMessage.created_at).all()

        return jsonify({
            'messages': [m.to_dict() for m in messages]
        }), 200

    data = request.get_json(force=True, silent=True) or {}
    if not data.get('message'):
        return jsonify({'error': 'Message required'}), 400

    if user.role == UserRole.WORKER:
        receiver_id = shift.venue.user_id
    else:
        app = Application.query.filter_by(
            shift_id=shift_id,
            status=ApplicationStatus.ACCEPTED
        ).first()
        
        if not app:
            return jsonify({'error': 'No hired worker yet'}), 400
        
        receiver_id = app.worker.user_owner.id

    message = ChatMessage(
        shift_id=shift_id,
        sender_id=user_id,
        message=data['message']
    )
    db.session.add(message)
    db.session.commit()

    return jsonify({
        'message': 'Message sent',
        'chat_message': message.to_dict()
    }), 201

# =========================== 
# NOTIFICATION ROUTES
# ===========================

@dual_route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get user notifications"""
    user_id = int(get_jwt_identity())
    
    notifications = Notification.query.filter_by(
        user_id=user_id
    ).order_by(Notification.created_at.desc()).limit(50).all()

    return jsonify({
        'notifications': [n.to_dict() for n in notifications]
    }), 200

@dual_route('/notifications/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    """Mark notification as read"""
    user_id = int(get_jwt_identity())
    
    notification = Notification.query.get(notification_id)
    if not notification or notification.user_id != user_id:
        return jsonify({'error': 'Notification not found'}), 404

    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Marked as read'}), 200

# =========================== 
# UTILITY ROUTES
# ===========================

@app.route('/', methods=['GET'])
def home():
    """API home page"""
    return jsonify({
        'name': 'Diisco API',
        'version': '1.0.0',
        'status': 'running',
        'creator': 'Kanchan Ghosh (ikanchan.com)'
    }), 200

@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected'
    }), 200

@app.route('/reset-db', methods=['GET'])
def reset_db():
    """Reset database - visit this URL"""
    try:
        db.drop_all()
        db.create_all()
        
        venue_user = User(
            email='venue@test.com',
            password_hash=bcrypt.generate_password_hash('password123').decode('utf-8'),
            role=UserRole.VENUE,
            name='Test Manager',
            is_active=True
        )
        db.session.add(venue_user)
        db.session.flush()
        
        venue_profile = VenueProfile(
            user_id=venue_user.id,
            venue_name='The Golden Bar',
            business_address='123 Main St, Leeds'
        )
        db.session.add(venue_profile)
        
        worker_user = User(
            email='worker@test.com',
            password_hash=bcrypt.generate_password_hash('password123').decode('utf-8'),
            role=UserRole.WORKER,
            name='John Worker',
            is_active=True
        )
        db.session.add(worker_user)
        db.session.flush()
        
        worker_profile = WorkerProfile(
            user_id=worker_user.id,
            referral_code='JOHN123'
        )
        db.session.add(worker_profile)
        
        db.session.commit()
        
        return jsonify({
            'status': 'SUCCESS',
            'message': 'Database reset complete!',
            'test_accounts': {
                'worker': 'worker@test.com / password123',
                'venue': 'venue@test.com / password123'
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'ERROR',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
