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
    
    # Relationships
    worker_profile = db.relationship('WorkerProfile', backref='user_owner', uselist=False, cascade='all, delete-orphan', foreign_keys='WorkerProfile.user_id')
    venue_profile = db.relationship('VenueProfile', backref='user_owner', uselist=False, cascade='all, delete-orphan', foreign_keys='VenueProfile.user_id')

    def to_dict(self):
        base = {
            'id': self.id,
            'email': self.email,
            'role': self.role.value if self.role else None,
            'name': self.name,
            'phone': self.phone,
            'address': self.address,
            'bio': self.bio,
            'profile_photo': self.profile_photo,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        # Include worker_profile data for Flutter
        if self.role == UserRole.WORKER and self.worker_profile:
            base['worker_profile'] = self.worker_profile.to_dict()
            # Also add top-level fields for easier access
            base['cv_url'] = self.worker_profile.cv_document
            base['cv_summary'] = self.worker_profile.cv_summary
            base['reliability_score'] = self.worker_profile.reliability_score
            base['average_rating'] = self.worker_profile.average_rating
            base['completed_shifts'] = self.worker_profile.completed_shifts
            base['referral_code'] = self.worker_profile.referral_code
            base['referral_balance'] = self.worker_profile.referral_balance
            base['referred_by'] = self.worker_profile.referred_by
        
        # Include venue_profile data for Flutter
        if self.role == UserRole.VENUE and self.venue_profile:
            base['venue_profile'] = self.venue_profile.to_dict()
            base['parent_venue_id'] = self.venue_profile.parent_venue_id
        
        return base

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
    referral_balance = db.Column(db.Float, default=0.0)
    
    referrer_user = db.relationship('User', foreign_keys=[referred_by], backref='referred_workers')
    applications = db.relationship('Application', backref='worker', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'id_verified': self.id_verified,
            'cv_document': self.cv_document,
            'cv_summary': self.cv_summary,
            'rating': float(self.rating) if self.rating else 0.0,
            'average_rating': float(self.average_rating) if self.average_rating else 0.0,
            'total_shifts': self.total_shifts or 0,
            'completed_shifts': self.completed_shifts or 0,
            'reliability_score': float(self.reliability_score) if self.reliability_score else 100.0,
            'referral_code': self.referral_code,
            'referral_balance': float(self.referral_balance) if self.referral_balance else 0.0,
            'referred_by': self.referred_by
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
            'rating': float(self.rating) if self.rating else 0.0,
            'average_rating': float(self.average_rating) if self.average_rating else 0.0,
            'total_shifts_posted': self.total_shifts_posted or 0,
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
            'hourly_rate': float(self.hourly_rate),
            'status': self.status.value if self.status else None,
            'num_workers_needed': self.num_workers_needed or 1,
            'num_workers_hired': self.num_workers_hired or 0,
            'required_skills': self.required_skills or [],
            'is_boosted': self.is_boosted or False,
            'boosted_at': self.boosted_at.isoformat() if self.boosted_at else None,
            'fill_risk': self.fill_risk,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Application Model
class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker_profiles.id'), nullable=False)

    status = db.Column(db.Enum(ApplicationStatus), default=ApplicationStatus.APPLIED)
    cover_letter = db.Column(db.Text)

    # Rate negotiation
    offered_rate = db.Column(db.Float)
    venue_counter_rate = db.Column(db.Float)
    hired_rate = db.Column(db.Float)

    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    hired_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'worker_id': self.worker_id,
            'status': self.status.value if self.status else None,
            'cover_letter': self.cover_letter,
            'offered_rate': float(self.offered_rate) if self.offered_rate else None,
            'venue_counter_rate': float(self.venue_counter_rate) if self.venue_counter_rate else None,
            'hired_rate': float(self.hired_rate) if self.hired_rate else None,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'hired_at': self.hired_at.isoformat() if self.hired_at else None
        }

# Rating Model
class Rating(db.Model):
    __tablename__ = 'ratings'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rated_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    stars = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    tags = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    shift = db.relationship('Shift', backref='ratings')
    rater = db.relationship('User', foreign_keys=[rater_id], backref='ratings_given')
    rated_user = db.relationship('User', foreign_keys=[rated_user_id], backref='ratings_received')

    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'rater_id': self.rater_id,
            'rated_user_id': self.rated_user_id,
            'stars': float(self.stars),
            'comment': self.comment,
            'tags': self.tags or [],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Dispute Model
class Dispute(db.Model):
    __tablename__ = 'disputes'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    dispute_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    evidence_url = db.Column(db.String(255))

    status = db.Column(db.Enum(DisputeStatus), default=DisputeStatus.OPEN)
    resolution = db.Column(db.Text)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime)

    shift = db.relationship('Shift', backref='disputes')
    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='disputes_reported')
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='disputes_resolved')

    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'reporter_id': self.reporter_id,
            'dispute_type': self.dispute_type,
            'description': self.description,
            'evidence_url': self.evidence_url,
            'status': self.status.value if self.status else None,
            'resolution': self.resolution,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }

# Availability Slot Model
class AvailabilitySlot(db.Model):
    __tablename__ = 'availability_slots'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    is_available = db.Column(db.Boolean, default=True)
    reason = db.Column(db.String(255))
    is_recurring = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='availability_slots')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='unique_user_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'date': self.date.isoformat() if self.date else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'is_available': self.is_available,
            'reason': self.reason,
            'is_recurring': self.is_recurring or False
        }

# Referral Model
class Referral(db.Model):
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    referred_user_type = db.Column(db.String(20))  # worker, venue
    status = db.Column(db.String(20), default='active')  # active, completed, expired
    
    shifts_completed = db.Column(db.Integer, default=0)
    total_earned = db.Column(db.Float, default=0.0)
    
    referral_metadata = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_made')
    referred_user = db.relationship('User', foreign_keys=[referred_user_id], backref='referral_received')

    def to_dict(self):
        return {
            'id': self.id,
            'referrer_id': self.referrer_id,
            'referred_user_id': self.referred_user_id,
            'referred_user_type': self.referred_user_type,
            'status': self.status,
            'shifts_completed': self.shifts_completed or 0,
            'total_earned': float(self.total_earned) if self.total_earned else 0.0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

# Referral Transaction Model
class ReferralTransaction(db.Model):
    __tablename__ = 'referral_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referral_id = db.Column(db.Integer, db.ForeignKey('referrals.id'))

    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # earn, withdrawal
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed

    payment_method = db.Column(db.String(50))
    payment_reference = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='referral_transactions')
    referral = db.relationship('Referral', backref='transactions')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'referral_id': self.referral_id,
            'amount': float(self.amount),
            'transaction_type': self.transaction_type,
            'status': self.status,
            'payment_method': self.payment_method,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }

# Venue Team Member Model
class VenueTeamMember(db.Model):
    __tablename__ = 'venue_team_members'

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    email = db.Column(db.String(120), nullable=False)

    role = db.Column(db.String(50), nullable=False)  # 'owner', 'manager', 'staff'
    permissions = db.Column(db.JSON)

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
            'email': self.email,
            'role': self.role,
            'permissions': self.permissions or [],
            'is_active': self.is_active,
            'invited_at': self.invited_at.isoformat() if self.invited_at else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None
        }

# Timesheet Model
class Timesheet(db.Model):
    __tablename__ = 'timesheets'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker_profiles.id'), nullable=False)

    check_in_time = db.Column(db.DateTime, nullable=False)
    check_out_time = db.Column(db.DateTime)

    check_in_latitude = db.Column(db.Float)
    check_in_longitude = db.Column(db.Float)
    check_out_latitude = db.Column(db.Float)
    check_out_longitude = db.Column(db.Float)

    breaks = db.Column(db.JSON)

    total_worked_minutes = db.Column(db.Integer)
    total_break_minutes = db.Column(db.Integer, default=0)

    worker_notes = db.Column(db.Text)
    venue_notes = db.Column(db.Text)

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
            'total_break_minutes': self.total_break_minutes or 0,
            'breaks': self.breaks or [],
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

    attachment_url = db.Column(db.String(255))
    attachment_type = db.Column(db.String(50))

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
            'is_read': self.is_read or False,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Notification Model
class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    notification_type = db.Column(db.Enum(NotificationType), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)

    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'))
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'))

    sent_push = db.Column(db.Boolean, default=False)
    sent_email = db.Column(db.Boolean, default=False)
    sent_sms = db.Column(db.Boolean, default=False)

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
            'type': self.notification_type.value if self.notification_type else None,  # Flutter expects 'type'
            'title': self.title,
            'message': self.message,
            'shift_id': self.shift_id,
            'application_id': self.application_id,
            'is_read': self.is_read or False,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
