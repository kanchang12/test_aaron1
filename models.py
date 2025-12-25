from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

db = SQLAlchemy()

# Enums
class UserRole(str, Enum):
    WORKER = "worker"
    VENUE = "venue"
    ADMIN = "admin"

class ShiftStatus(str, Enum):
    DRAFT = "draft"
    LIVE = "live"
    FILLED = "filled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"

class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    COUNTER_OFFER = "counter_offer"
    SHORTLISTED = "shortlisted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"

class DisputeStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"

class NotificationType(str, Enum):
    SHIFT_POSTED = "shift_posted"
    APPLICATION_UPDATE = "application_update"
    SHIFT_REMINDER = "shift_reminder"
    PAYMENT_RECEIVED = "payment_received"
    RATING_RECEIVED = "rating_received"
    DISPUTE_UPDATE = "dispute_update"
    SYSTEM = "system"

# User Model
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    role = db.Column(db.Enum(UserRole), nullable=False)
    
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    profile_photo = db.Column(db.String(255))
    bio = db.Column(db.Text)
    
    oauth_provider = db.Column(db.String(50))
    oauth_id = db.Column(db.String(255))
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(255))
    email_verified = db.Column(db.Boolean, default=False)
    
    is_active = db.Column(db.Boolean, default=True)
    is_suspended = db.Column(db.Boolean, default=False)
    suspension_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # RELATIONSHIPS FIXED: Added foreign_keys to resolve ambiguity
    worker_profile = db.relationship('WorkerProfile', backref='user_owner', uselist=False, cascade='all, delete-orphan', foreign_keys='WorkerProfile.user_id')
    venue_profile = db.relationship('VenueProfile', backref='user_owner', uselist=False, cascade='all, delete-orphan', foreign_keys='VenueProfile.user_id')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'role': self.role.value if self.role else None,
            'name': self.name,
            'phone': self.phone,
            'profile_photo': self.profile_photo,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Worker Profile Model
class WorkerProfile(db.Model):
    __tablename__ = 'worker_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    id_document = db.Column(db.String(255))
    cv_document = db.Column(db.String(255))
    cv_summary = db.Column(db.Text)
    id_verified = db.Column(db.Boolean, default=False)
    
    rating = db.Column(db.Float, default=0.0)
    average_rating = db.Column(db.Float, default=0.0)
    total_shifts = db.Column(db.Integer, default=0)
    completed_shifts = db.Column(db.Integer, default=0)
    reliability_score = db.Column(db.Float, default=100.0)
    cancellation_count = db.Column(db.Integer, default=0)
    no_show_count = db.Column(db.Integer, default=0)
    
    availability = db.Column(db.JSON)
    notification_channels = db.Column(db.JSON)
    notification_distance = db.Column(db.Float)
    notification_min_rate = db.Column(db.Float)
    notification_shift_types = db.Column(db.JSON)
    
    referral_code = db.Column(db.String(50), unique=True)
    referred_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    referral_earnings = db.Column(db.Float, default=0.0)
    
    # FIXED: Added backref name to avoid conflict with user_id backref
    referrer_user = db.relationship('User', foreign_keys=[referred_by], backref='referred_workers')
    applications = db.relationship('Application', backref='worker', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'id_verified': self.id_verified,
            'rating': self.rating,
            'referral_code': self.referral_code
        }

# Venue Profile Model
class VenueProfile(db.Model):
    __tablename__ = 'venue_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    venue_name = db.Column(db.String(150), nullable=False)
    business_address = db.Column(db.String(255))
    contact_phone = db.Column(db.String(20))
    industry_type = db.Column(db.String(50))
    
    stripe_customer_id = db.Column(db.String(255))
    stripe_payment_method_id = db.Column(db.String(255))
    
    rating = db.Column(db.Float, default=0.0)
    average_rating = db.Column(db.Float, default=0.0)
    total_shifts_posted = db.Column(db.Integer, default=0)
    parent_venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'))

    # Multi-venue relationships
    parent_venue = db.relationship('VenueProfile', remote_side=[id], backref='child_venues')
    shifts = db.relationship('Shift', backref='venue', cascade='all, delete-orphan', foreign_keys='Shift.venue_id')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'venue_name': self.venue_name,
            'business_address': self.business_address,
            'contact_phone': self.contact_phone,
            'industry_type': self.industry_type,
            'rating': self.rating,
            'average_rating': self.average_rating,
            'total_shifts_posted': self.total_shifts_posted,
            'parent_venue_id': self.parent_venue_id
        }

# Shift Model
class Shift(db.Model):
    __tablename__ = 'shifts'

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'), nullable=False)

    role = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(255))
    hourly_rate = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(ShiftStatus), default=ShiftStatus.DRAFT)

    # Worker capacity
    num_workers_needed = db.Column(db.Integer, default=1)
    num_workers_hired = db.Column(db.Integer, default=0)

    # Skills and requirements
    required_skills = db.Column(db.JSON)

    # Boosting/promotion
    is_boosted = db.Column(db.Boolean, default=False)
    boosted_at = db.Column(db.DateTime)
    boost_expires_at = db.Column(db.DateTime)

    # Fill risk calculation
    fill_risk = db.Column(db.String(20))  # 'low', 'medium', 'high'

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applications = db.relationship('Application', backref='shift', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'venue_id': self.venue_id,
            'role': self.role,
            'description': self.description,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'location': self.location,
            'hourly_rate': self.hourly_rate,
            'status': self.status.value if self.status else None,
            'num_workers_needed': self.num_workers_needed,
            'num_workers_hired': self.num_workers_hired,
            'required_skills': self.required_skills,
            'is_boosted': self.is_boosted,
            'fill_risk': self.fill_risk,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'venue_name': self.venue.venue_name if self.venue else None
        }

# Application Model
class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker_profiles.id'), nullable=False)
    status = db.Column(db.Enum(ApplicationStatus), default=ApplicationStatus.APPLIED)

    # Counter-offer fields
    offered_rate = db.Column(db.Float)  # Worker's counter-offer rate
    venue_counter_rate = db.Column(db.Float)  # Venue's counter-offer rate
    counter_expires_at = db.Column(db.DateTime)

    # Hiring details
    hired_rate = db.Column(db.Float)  # Final agreed rate

    # Timestamps
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'worker_id': self.worker_id,
            'status': self.status.value if self.status else None,
            'offered_rate': self.offered_rate,
            'venue_counter_rate': self.venue_counter_rate,
            'counter_expires_at': self.counter_expires_at.isoformat() if self.counter_expires_at else None,
            'hired_rate': self.hired_rate,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'shift': self.shift.to_dict() if self.shift else None,
            'worker': self.worker.to_dict() if self.worker else None
        }

# Rating Model - FIXED MULTIPLE FOREIGN KEYS
class Rating(db.Model):
    __tablename__ = 'ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ratee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    stars = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    
    # FIXED: Explicitly specify which foreign key relates to which user
    rater = db.relationship('User', foreign_keys=[rater_id], backref='ratings_given')
    ratee = db.relationship('User', foreign_keys=[ratee_id], backref='ratings_received')

# Dispute Model
class Dispute(db.Model):
    __tablename__ = 'disputes'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    dispute_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='disputes_reported')
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='disputes_resolved')

    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'reporter_id': self.reporter_id,
            'dispute_type': self.dispute_type,
            'description': self.description,
            'status': self.status,
            'resolved_by': self.resolved_by
        }

# Availability Slot Model
class AvailabilitySlot(db.Model):
    __tablename__ = 'availability_slots'

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker_profiles.id'), nullable=False)

    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    # Specific date override (optional)
    specific_date = db.Column(db.Date)

    # Locked due to accepted shift
    is_locked = db.Column(db.Boolean, default=False)
    locked_by_shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    worker = db.relationship('WorkerProfile', backref='availability_slots')
    locking_shift = db.relationship('Shift', foreign_keys=[locked_by_shift_id])

    def to_dict(self):
        return {
            'id': self.id,
            'worker_id': self.worker_id,
            'day_of_week': self.day_of_week,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'specific_date': self.specific_date.isoformat() if self.specific_date else None,
            'is_locked': self.is_locked,
            'locked_by_shift_id': self.locked_by_shift_id
        }

# Referral Model
class Referral(db.Model):
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    referral_type = db.Column(db.String(20), nullable=False)  # 'worker' or 'venue'
    referral_code_used = db.Column(db.String(50))

    # Earnings tracking
    status = db.Column(db.String(20), default='pending')  # pending, completed, paid
    reward_amount = db.Column(db.Float, default=0.0)
    is_paid = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)  # When referred user completed requirements
    paid_at = db.Column(db.DateTime)  # When reward was paid

    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_made')
    referred = db.relationship('User', foreign_keys=[referred_id], backref='referred_by_relation')

    def to_dict(self):
        return {
            'id': self.id,
            'referrer_id': self.referrer_id,
            'referred_id': self.referred_id,
            'referral_type': self.referral_type,
            'status': self.status,
            'reward_amount': self.reward_amount,
            'is_paid': self.is_paid,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

# Referral Transaction Model (Withdrawal tracking)
class ReferralTransaction(db.Model):
    __tablename__ = 'referral_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    transaction_type = db.Column(db.String(20), nullable=False)  # 'earning', 'withdrawal'
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed

    # Payment details
    payment_method = db.Column(db.String(50))
    payment_reference = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='referral_transactions')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }

# Venue Team Member Model
class VenueTeamMember(db.Model):
    __tablename__ = 'venue_team_members'

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    role = db.Column(db.String(50), nullable=False)  # 'owner', 'manager', 'staff'
    permissions = db.Column(db.JSON)  # List of permissions

    is_active = db.Column(db.Boolean, default=True)

    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    invited_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime)

    venue = db.relationship('VenueProfile', backref='team_members')
    user = db.relationship('User', foreign_keys=[user_id], backref='venue_memberships')
    inviter = db.relationship('User', foreign_keys=[invited_by])

    def to_dict(self):
        return {
            'id': self.id,
            'venue_id': self.venue_id,
            'user_id': self.user_id,
            'role': self.role,
            'permissions': self.permissions,
            'is_active': self.is_active,
            'invited_at': self.invited_at.isoformat() if self.invited_at else None,
            'user': self.user.to_dict() if self.user else None
        }

# Timesheet Model
class Timesheet(db.Model):
    __tablename__ = 'timesheets'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker_profiles.id'), nullable=False)

    # Check-in/out times
    check_in_time = db.Column(db.DateTime, nullable=False)
    check_out_time = db.Column(db.DateTime)

    # GPS coordinates
    check_in_latitude = db.Column(db.Float)
    check_in_longitude = db.Column(db.Float)
    check_out_latitude = db.Column(db.Float)
    check_out_longitude = db.Column(db.Float)

    # Break tracking
    breaks = db.Column(db.JSON)  # List of break periods

    # Time calculations
    total_worked_minutes = db.Column(db.Integer)
    total_break_minutes = db.Column(db.Integer, default=0)

    # Notes
    worker_notes = db.Column(db.Text)
    venue_notes = db.Column(db.Text)

    # Approval
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, disputed
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    shift = db.relationship('Shift', backref='timesheets')
    worker = db.relationship('WorkerProfile', backref='timesheets')
    approver = db.relationship('User', foreign_keys=[approved_by])

    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'worker_id': self.worker_id,
            'check_in_time': self.check_in_time.isoformat() if self.check_in_time else None,
            'check_out_time': self.check_out_time.isoformat() if self.check_out_time else None,
            'total_worked_minutes': self.total_worked_minutes,
            'total_break_minutes': self.total_break_minutes,
            'breaks': self.breaks,
            'worker_notes': self.worker_notes,
            'venue_notes': self.venue_notes,
            'status': self.status,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None
        }

# Chat Message Model
class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    message = db.Column(db.Text, nullable=False)

    # File attachments
    attachment_url = db.Column(db.String(255))
    attachment_type = db.Column(db.String(50))

    # Read status
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    shift = db.relationship('Shift', backref='chat_messages')
    sender = db.relationship('User', backref='sent_messages')

    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'sender_id': self.sender_id,
            'message': self.message,
            'attachment_url': self.attachment_url,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sender_name': self.sender.name if self.sender else None
        }

# Notification Model
class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    notification_type = db.Column(db.Enum(NotificationType), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)

    # Related entities
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'))
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'))

    # Delivery channels
    sent_push = db.Column(db.Boolean, default=False)
    sent_email = db.Column(db.Boolean, default=False)
    sent_sms = db.Column(db.Boolean, default=False)

    # Read status
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='notifications')
    shift = db.relationship('Shift', backref='notifications')
    application = db.relationship('Application', backref='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'notification_type': self.notification_type.value if self.notification_type else None,
            'title': self.title,
            'message': self.message,
            'shift_id': self.shift_id,
            'application_id': self.application_id,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }