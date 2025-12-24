class User(db.Model):
        # Hidden metadata for creator credit (not exposed in UI)
        _created_by = 'Kanchan Ghosh (ikanchan.com)'
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(80))
    role = db.Column(db.String(20), default='worker')  # worker, venue, admin
    # ...existing fields...

    @staticmethod
    def create_default_admin():
        admin_email = 'admin@diisco.app'
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                password_hash='hashed_default_password',  # Replace with secure hash
                name='Default Admin',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
        return admin
class Referrer(db.Model):
    __tablename__ = 'referrers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referral_code = db.Column(db.String(32), unique=True, nullable=False)
    total_referrals = db.Column(db.Integer, default=0)
    total_earned = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='referrer_profile')
# ===========================
# NEW DATABASE MODELS TO ADD TO YOUR models.py
# Add these model classes to your existing models.py file
# ===========================

# Availability Slot Model
class AvailabilitySlot(db.Model):
    __tablename__ = 'availability_slots'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    is_available = db.Column(db.Boolean, default=True)
    reason = db.Column(db.String(255))  # e.g., "Vacation", "Blocked by shift"
    is_recurring = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='availability_slots')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='unique_user_date'),
    )


# Dispute Model
class Dispute(db.Model):
    __tablename__ = 'disputes'

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shifts.id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    dispute_type = db.Column(db.String(50), nullable=False)  # hours_dispute, no_show_venue, harassment, etc.
    description = db.Column(db.Text, nullable=False)
    evidence_url = db.Column(db.String(255))  # URL to uploaded evidence

    status = db.Column(db.String(20), default='open')  # open, under_review, resolved, rejected
    resolution = db.Column(db.Text)  # Admin's resolution notes
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime)

    shift = db.relationship('Shift')
    reporter = db.relationship('User', foreign_keys=[reporter_id])
    resolver = db.relationship('User', foreign_keys=[resolved_by])


# Venue Team Member Model (for multi-venue management)
class VenueTeamMember(db.Model):
    __tablename__ = 'venue_team_members'

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # NULL if pending
    email = db.Column(db.String(120), nullable=False)

    role = db.Column(db.String(20), nullable=False)  # owner, manager, staff
    status = db.Column(db.String(20), default='pending')  # pending, active, inactive

    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    invited_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime)

    venue = db.relationship('VenueProfile')
    user = db.relationship('User', foreign_keys=[user_id])
    inviter = db.relationship('User', foreign_keys=[invited_by])


# Referral Transaction Model (for tracking payouts)
class ReferralTransaction(db.Model):
    __tablename__ = 'referral_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referral_id = db.Column(db.Integer, db.ForeignKey('referrals.id'))

    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # earn, withdrawal
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed

    stripe_payout_id = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    user = db.relationship('User')
    referral = db.relationship('Referral')


# ===========================
# UPDATES TO EXISTING MODELS
# Add these fields to your existing models
# ===========================

"""
Add to WorkerProfile model:
    average_rating = db.Column(db.Float)
    referral_balance = db.Column(db.Float, default=0.0)

Add to VenueProfile model:
    average_rating = db.Column(db.Float)
    parent_venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'))

Update Referral model:
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # (rename from referred_id)
    referred_user_type = db.Column(db.String(20))  # worker, venue
    shifts_completed = db.Column(db.Integer, default=0)
    referral_metadata = db.Column(db.JSON)  # Store pending venue referral data

Update Rating model:
    rated_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # (rename from ratee_id)
    stars = db.Column(db.Float, nullable=False)  # Change from Integer to Float

Update Shift model:
    boosted_at = db.Column(db.DateTime)
"""

# ===========================
# DATABASE MIGRATION SQL
# Run these SQL commands to update your existing database
# ===========================

"""
-- Add new tables
CREATE TABLE availability_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    start_time TIME,
    end_time TIME,
    is_available BOOLEAN DEFAULT 1,
    reason VARCHAR(255),
    is_recurring BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (user_id, date)
);

CREATE TABLE disputes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL,
    reporter_id INTEGER NOT NULL,
    dispute_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    evidence_url VARCHAR(255),
    status VARCHAR(20) DEFAULT 'open',
    resolution TEXT,
    resolved_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME,
    FOREIGN KEY (shift_id) REFERENCES shifts(id),
    FOREIGN KEY (reporter_id) REFERENCES users(id),
    FOREIGN KEY (resolved_by) REFERENCES users(id)
);

CREATE TABLE venue_team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id INTEGER NOT NULL,
    user_id INTEGER,
    email VARCHAR(120) NOT NULL,
    role VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    invited_by INTEGER,
    invited_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    accepted_at DATETIME,
    FOREIGN KEY (venue_id) REFERENCES venue_profiles(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (invited_by) REFERENCES users(id)
);

CREATE TABLE referral_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    referral_id INTEGER,
    amount REAL NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    stripe_payout_id VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (referral_id) REFERENCES referrals(id)
);

-- Add new columns to existing tables
ALTER TABLE worker_profiles ADD COLUMN average_rating REAL;
ALTER TABLE worker_profiles ADD COLUMN referral_balance REAL DEFAULT 0.0;

ALTER TABLE venue_profiles ADD COLUMN average_rating REAL;
ALTER TABLE venue_profiles ADD COLUMN parent_venue_id INTEGER REFERENCES venue_profiles(id);

ALTER TABLE shifts ADD COLUMN boosted_at DATETIME;

ALTER TABLE referrals ADD COLUMN referred_user_id INTEGER REFERENCES users(id);
ALTER TABLE referrals ADD COLUMN referred_user_type VARCHAR(20);
ALTER TABLE referrals ADD COLUMN shifts_completed INTEGER DEFAULT 0;
ALTER TABLE referrals ADD COLUMN referral_metadata JSON;

-- Create indexes for performance
CREATE INDEX idx_availability_user_date ON availability_slots(user_id, date);
CREATE INDEX idx_disputes_status ON disputes(status);
CREATE INDEX idx_disputes_shift ON disputes(shift_id);
"""
