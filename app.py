from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
from models import *
import os
import stripe
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')

# Fix DATABASE_URL for Heroku (postgres:// -> postgresql://)
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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size


import openai

# Initialize extensions
CORS(app)
db.init_app(app)
jwt = JWTManager(app)
bcrypt = Bcrypt(app)

# Stripe configuration
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_dummy')

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ===========================
# AUTHENTICATION ROUTES
# ===========================

@app.route('/api/worker/cv/upload', methods=['POST'])
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

    # Validate file type
    allowed_extensions = {'pdf', 'doc', 'docx'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'error': 'Invalid file type. Only PDF, DOC, DOCX allowed'}), 400

    # Save file
    filename = secure_filename(f"cv_{user_id}_{uuid.uuid4()}.{file.filename.rsplit('.', 1)[1]}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'cvs', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    # Store CV URL in database
    cv_url = f"/uploads/cvs/{filename}"
    user.worker_profile.cv_document = cv_url
    db.session.commit()

    return jsonify({
        'cv_url': cv_url,
        'message': 'CV uploaded successfully'
    }), 200


@app.route('/api/worker/cv/parse', methods=['POST'])
@jwt_required()
def parse_cv():
    """Parse CV using AI to extract summary"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    data = request.get_json()
    cv_url = data.get('cv_url')

    if not cv_url:
        return jsonify({'error': 'CV URL required'}), 400

    openai.api_key = os.getenv('OPENAI_API_KEY')

    # Call OpenAI API
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "system",
            "content": "Extract hospitality experience from this CV and summarize in 2-3 sentences"
        }, {
            "role": "user",
            "content": cv_text  # The uploaded CV text
        }]
    )

    cv_summary = response.choices[0].message.content

    user.worker_profile.cv_summary = cv_summary
    db.session.commit()

    return jsonify({
        'summary': cv_summary,
        'message': 'CV parsed successfully'
    }), 200


@app.route('/api/auth/profile', methods=['PATCH'])
@jwt_required()
def update_user_profile():
    """Update user profile"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()

    # Update basic user fields
    if 'name' in data:
        user.name = data['name']
    if 'phone' in data:
        user.phone = data['phone']
    if 'address' in data:
        user.address = data['address']
    if 'bio' in data:
        user.bio = data['bio']

    # Update worker-specific fields
    if user.role == UserRole.WORKER and user.worker_profile:
        if 'cv_url' in data:
            user.worker_profile.cv_document = data['cv_url']
        if 'cv_summary' in data:
            user.worker_profile.cv_summary = data['cv_summary']

    db.session.commit()

    return jsonify({
        'message': 'Profile updated successfully',
        'user': user.to_dict()
    }), 200


# ===========================
# AVAILABILITY CALENDAR
# ===========================

@app.route('/api/worker/availability', methods=['GET', 'POST'])
@jwt_required()
def manage_availability():
    """Get or set worker availability"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    if request.method == 'GET':
        # Get availability slots
        availability = AvailabilitySlot.query.filter_by(
            user_id=user_id
        ).all()

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

    # POST - Set availability
    data = request.get_json()
    date_str = data.get('date')
    is_available = data.get('is_available', True)

    if not date_str:
        return jsonify({'error': 'Date required'}), 400

    date_obj = datetime.fromisoformat(date_str).date()

    # Check if slot exists
    slot = AvailabilitySlot.query.filter_by(
        user_id=user_id,
        date=date_obj
    ).first()

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

@app.route('/api/referrals', methods=['GET'])
@jwt_required()
def get_referrals():
    """Get user's referrals"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    referrals = Referral.query.filter_by(
        referrer_id=user_id
    ).all()

    return jsonify({
        'referrals': [{
            'id': ref.id,
            'referrer_id': ref.referrer_id,
            'referred_user_id': ref.referred_user_id,
            'referred_user_type': ref.referred_user_type,
            'total_earned': float(ref.total_earned),
            'shifts_completed': ref.shifts_completed,
            'status': ref.status,
            'created_at': ref.created_at.isoformat()
        } for ref in referrals]
    }), 200


@app.route('/api/referrals/venue', methods=['POST'])
@jwt_required()
def refer_venue():
    """Refer a venue"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    data = request.get_json()

    required = ['venue_name', 'manager_name', 'manager_email']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    # Check if venue email already exists
    existing_venue = User.query.filter_by(email=data['manager_email']).first()
    if existing_venue:
        return jsonify({'error': 'This venue is already in our system'}), 409

    # Create pending referral (venue needs to accept within 7 days)
    referral = Referral(
        referrer_id=user_id,
        referred_user_type='venue',
        status='pending',
        referral_metadata={
            'venue_name': data['venue_name'],
            'manager_name': data['manager_name'],
            'manager_email': data['manager_email']
        }
    )
    db.session.add(referral)
    db.session.commit()

    # TODO: Send email invitation to venue manager

    return jsonify({
        'message': 'Venue referral sent successfully',
        'referral_id': referral.id
    }), 201


@app.route('/api/referrals/withdraw', methods=['POST'])
@jwt_required()
def withdraw_referral_balance():
    """Withdraw referral earnings"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    profile = user.worker_profile

    if profile.referral_balance <= 0:
        return jsonify({'error': 'No balance to withdraw'}), 400

    amount = profile.referral_balance

    # TODO: Process actual payout via Stripe
    # stripe.Payout.create(
    #     amount=int(amount * 100),
    #     currency="gbp",
    #     destination=profile.stripe_account_id
    # )

    # Reset balance
    profile.referral_balance = 0

    # Create transaction record
    transaction = ReferralTransaction(
        user_id=user_id,
        amount=amount,
        transaction_type='withdrawal',
        status='completed'
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify({
        'message': 'Withdrawal successful',
        'amount': float(amount)
    }), 200


# ===========================
# DISPUTE RESOLUTION
# ===========================

@app.route('/api/disputes', methods=['GET', 'POST'])
@jwt_required()
def manage_disputes():
    """Get disputes or create new dispute"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if request.method == 'GET':
        shift_id = request.args.get('shift_id', type=int)

        query = Dispute.query.filter_by(reporter_id=user_id)
        if shift_id:
            query = query.filter_by(shift_id=shift_id)

        disputes = query.order_by(Dispute.created_at.desc()).all()

        return jsonify({
            'disputes': [{
                'id': d.id,
                'shift_id': d.shift_id,
                'reporter_id': d.reporter_id,
                'dispute_type': d.dispute_type,
                'description': d.description,
                'status': d.status,
                'resolution': d.resolution,
                'evidence_url': d.evidence_url,
                'created_at': d.created_at.isoformat(),
                'resolved_at': d.resolved_at.isoformat() if d.resolved_at else None
            } for d in disputes]
        }), 200

    # POST - Create dispute
    shift_id = request.form.get('shift_id', type=int)
    dispute_type = request.form.get('dispute_type')
    description = request.form.get('description')

    if not all([shift_id, dispute_type, description]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Handle evidence file upload
    evidence_url = None
    if 'evidence' in request.files:
        file = request.files['evidence']
        if file.filename:
            filename = secure_filename(f"evidence_{uuid.uuid4()}.{file.filename.rsplit('.', 1)[1]}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'evidence', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            evidence_url = f"/uploads/evidence/{filename}"

    dispute = Dispute(
        shift_id=shift_id,
        reporter_id=user_id,
        dispute_type=dispute_type,
        description=description,
        evidence_url=evidence_url,
        status='open'
    )
    db.session.add(dispute)

    # Notify admin
    # TODO: Send admin notification

    db.session.commit()

    return jsonify({
        'message': 'Dispute created successfully',
        'dispute_id': dispute.id
    }), 201


# ===========================
# SHIFT BOOSTING & STRIPE
# ===========================

@app.route('/api/payments/boost', methods=['POST'])
@jwt_required()
def create_boost_payment():
    """Create Stripe payment intent for shift boosting"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    data = request.get_json()
    shift_id = data.get('shift_id')
    amount = data.get('amount', 1999)  # £19.99 in pence

    if not shift_id:
        return jsonify({'error': 'Shift ID required'}), 400

    shift = Shift.query.get(shift_id)
    if not shift or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Shift not found'}), 404

    try:
        # Create Stripe payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='gbp',
            metadata={
                'shift_id': shift_id,
                'user_id': user_id,
                'type': 'shift_boost'
            }
        )

        return jsonify({
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/shifts/<int:shift_id>/boost', methods=['POST'])
@jwt_required()
def activate_shift_boost(shift_id):
    """Activate shift boost after payment"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    shift = Shift.query.get(shift_id)
    if not shift or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Shift not found'}), 404

    shift.is_boosted = True
    shift.boosted_at = datetime.utcnow()
    db.session.commit()

    # TODO: Send push notifications to all matching workers

    return jsonify({
        'message': 'Shift boosted successfully',
        'shift': shift.to_dict()
    }), 200


# ===========================
# MULTI-VENUE MANAGEMENT
# ===========================

@app.route('/api/venues', methods=['GET', 'POST'])
@jwt_required()
def manage_venues():
    """Get venues or create new venue location"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    if request.method == 'GET':
        # Get all venues owned by this user
        venues = VenueProfile.query.filter(
            db.or_(
                VenueProfile.user_id == user_id,
                VenueProfile.parent_venue_id == user.venue_profile.id
            )
        ).all()

        return jsonify({
            'venues': [{
                'id': v.id,
                'name': v.venue_name,
                'address': v.business_address,
                'phone': v.contact_phone,
                'industry_type': v.industry_type
            } for v in venues]
        }), 200

    # POST - Create new venue location
    data = request.get_json()

    required = ['name', 'address']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    venue = VenueProfile(
        user_id=user_id,
        venue_name=data['name'],
        business_address=data['address'],
        contact_phone=data.get('phone', ''),
        parent_venue_id=user.venue_profile.id
    )
    db.session.add(venue)
    db.session.commit()

    return jsonify({
        'message': 'Venue location created',
        'venue_id': venue.id
    }), 201


@app.route('/api/venues/team', methods=['GET'])
@jwt_required()
def get_team_members():
    """Get team members for venue"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    # Get all team members
    team_members = VenueTeamMember.query.filter_by(
        venue_id=user.venue_profile.id
    ).all()

    return jsonify({
        'team_members': [{
            'id': member.id,
            'name': member.user.name if member.user else member.email,
            'email': member.email,
            'venue_role': member.role,
            'is_active': member.status == 'active',
            'invited_at': member.invited_at.isoformat()
        } for member in team_members]
    }), 200


@app.route('/api/venues/team/invite', methods=['POST'])
@jwt_required()
def invite_team_member():
    """Invite team member to venue"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    data = request.get_json()

    required = ['name', 'email', 'role']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    # Check if already invited
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
        status='pending'
    )
    db.session.add(team_member)
    db.session.commit()

    # TODO: Send invitation email

    return jsonify({
        'message': 'Team member invited',
        'invitation_id': team_member.id
    }), 201


# ===========================
# SMART MATCHING
# ===========================

@app.route('/api/shifts/<int:shift_id>/matches', methods=['GET'])
@jwt_required()
def get_smart_matches(shift_id):
    """Get smart-matched workers for a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    shift = Shift.query.get(shift_id)
    if not shift or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Shift not found'}), 404

    # Simple matching algorithm (in production, use ML model)
    # Find workers with:
    # 1. Matching skills/role experience
    # 2. High reliability score
    # 3. Available on that date
    # 4. Within reasonable distance

    workers = WorkerProfile.query.join(User).filter(
        User.is_active == True,
        User.is_suspended == False
    ).all()

    matches = []
    for worker in workers[:10]:  # Top 10 matches
        # Calculate match score (simplified)
        match_score = 75.0  # Base score
        accept_likelihood = 65.0
        match_reason = f"Experienced {shift.role}"

        # Boost score if high reliability
        if worker.reliability_score and worker.reliability_score > 90:
            match_score += 15
            match_reason += ", excellent reliability"

        # Boost if worked at this venue before
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
                'id': worker.user.id,
                'name': worker.user.name,
                'cv_summary': worker.cv_summary,
                'average_rating': float(worker.average_rating) if worker.average_rating else None,
                'reliability_score': float(worker.reliability_score) if worker.reliability_score else None,
                'completed_shifts': worker.completed_shifts or 0
            }
        })

    # Sort by match score
    matches.sort(key=lambda x: x['match_score'], reverse=True)

    return jsonify({'matches': matches}), 200


@app.route('/api/shifts/<int:shift_id>/invite', methods=['POST'])
@jwt_required()
def invite_worker_to_shift(shift_id):
    """Invite specific worker to a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    shift = Shift.query.get(shift_id)
    if not shift or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Shift not found'}), 404

    data = request.get_json()
    worker_id = data.get('worker_id')

    if not worker_id:
        return jsonify({'error': 'Worker ID required'}), 400

    worker_user = User.query.get(worker_id)
    if not worker_user or worker_user.role != UserRole.WORKER:
        return jsonify({'error': 'Worker not found'}), 404

    # Create notification/invitation
    notification = Notification(
        user_id=worker_id,
        title='Shift Invitation',
        message=f'You have been invited to a {shift.role} shift at {shift.venue.venue_name}',
        notification_type='shift_invitation',
        shift_id=shift_id
    )
    db.session.add(notification)
    db.session.commit()

    return jsonify({
        'message': 'Invitation sent successfully'
    }), 201


# ===========================
# RATINGS & RELIABILITY
# ===========================

@app.route('/api/ratings', methods=['POST'])
@jwt_required()
def create_rating():
    """Create a rating for a user"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    data = request.get_json()

    required = ['shift_id', 'rated_user_id', 'stars']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    shift_id = data['shift_id']
    rated_user_id = data['rated_user_id']
    stars = data['stars']

    # Validate rating value
    if not (1 <= stars <= 5):
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400

    # Check if already rated
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

    # Update average rating for rated user
    rated_user = User.query.get(rated_user_id)
    if rated_user:
        avg_rating = db.session.query(func.avg(Rating.stars)).filter_by(
            rated_user_id=rated_user_id
        ).scalar()

        if rated_user.role == UserRole.WORKER:
            rated_user.worker_profile.average_rating = avg_rating
        elif rated_user.role == UserRole.VENUE:
            rated_user.venue_profile.average_rating = avg_rating

    db.session.commit()

    return jsonify({
        'message': 'Rating submitted successfully',
        'rating_id': rating.id
    }), 201


@app.route('/api/users/<int:user_id>/ratings', methods=['GET'])
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
            'created_at': r.created_at.isoformat()
        } for r in ratings]
    }), 200


# ===========================
# End of new routes
# ========

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user (worker, venue, or admin)"""
    data = request.get_json()

    # Validate required fields
    required = ['email', 'password', 'role', 'name']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409

    # Create user
    user = User(
        email=data['email'],
        password_hash=bcrypt.generate_password_hash(data['password']).decode('utf-8'),
        role=UserRole(data['role']),
        name=data.get('name'),
        phone=data.get('phone'),
        address=data.get('address')
    )
    db.session.add(user)
    db.session.flush()

    # Create role-specific profile
    if user.role == UserRole.WORKER:
        worker_profile = WorkerProfile(
            user_id=user.id,
            referral_code=str(uuid.uuid4())[:8].upper()
        )
        db.session.add(worker_profile)

    elif user.role == UserRole.VENUE:
        venue_profile = VenueProfile(
            user_id=user.id,
            venue_name=data.get('venue_name', ''),
            business_address=data.get('business_address', ''),
            industry_type=data.get('industry_type', '')
        )
        db.session.add(venue_profile)

    db.session.commit()

    # Generate token
    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict(),
        'access_token': access_token
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()

    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    user = User.query.filter_by(email=data['email']).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401

    if user.is_suspended:
        return jsonify({'error': 'Account suspended', 'reason': user.suspension_reason}), 403

    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()

    # Generate token
    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'access_token': access_token
    }), 200

@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user details"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    response = user.to_dict()

    # Add profile data based on role
    if user.role == UserRole.WORKER and user.worker_profile:
        response['worker_profile'] = user.worker_profile.to_dict()
    elif user.role == UserRole.VENUE and user.venue_profile:
        response['venue_profile'] = user.venue_profile.to_dict()

    return jsonify(response), 200

# ===========================
# WORKER ROUTES
# ===========================

@app.route('/api/worker/profile', methods=['GET', 'PUT'])
@jwt_required()
def worker_profile():
    """Get or update worker profile"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    if request.method == 'GET':
        return jsonify(user.worker_profile.to_dict()), 200

    # PUT - Update profile
    data = request.get_json()
    profile = user.worker_profile

    # Update fields
    if 'bio' in data:
        user.bio = data['bio']
    if 'availability' in data:
        profile.availability = data['availability']
    if 'notification_channels' in data:
        profile.notification_channels = data['notification_channels']
    if 'notification_distance' in data:
        profile.notification_distance = data['notification_distance']
    if 'notification_min_rate' in data:
        profile.notification_min_rate = data['notification_min_rate']

    db.session.commit()
    return jsonify({'message': 'Profile updated', 'profile': profile.to_dict()}), 200

@app.route('/api/worker/upload-cv', methods=['POST'])
@jwt_required()
def upload_cv():
    """Upload and parse CV"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Save file
    filename = secure_filename(f"{user_id}_{uuid.uuid4()}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Parse CV (simplified - would use OpenAI in production)
    cv_summary = f"Experienced hospitality worker with strong background"

    # Update profile
    user.worker_profile.cv_document = filename
    user.worker_profile.cv_summary = cv_summary
    db.session.commit()

    return jsonify({
        'message': 'CV uploaded successfully',
        'cv_summary': cv_summary
    }), 200

@app.route('/api/shifts/search', methods=['GET'])
@jwt_required()
def search_shifts():
    """Search available shifts"""
    user_id = get_jwt_identity()

    # Query parameters
    role = request.args.get('role')
    min_rate = request.args.get('min_rate', type=float)
    start_date = request.args.get('start_date')

    # Base query - only live shifts
    query = Shift.query.filter_by(status=ShiftStatus.LIVE)

    # Apply filters
    if role:
        query = query.filter_by(role=role)
    if min_rate:
        query = query.filter(Shift.hourly_rate >= min_rate)
    if start_date:
        date_obj = datetime.fromisoformat(start_date)
        query = query.filter(Shift.start_time >= date_obj)

    # Get shifts that aren't fully filled
    query = query.filter(Shift.num_workers_hired < Shift.num_workers_needed)

    shifts = query.order_by(Shift.start_time).limit(50).all()

    return jsonify({
        'shifts': [shift.to_dict() for shift in shifts],
        'count': len(shifts)
    }), 200

@app.route('/api/shifts/<int:shift_id>/apply', methods=['POST'])
@jwt_required()
def apply_to_shift(shift_id):
    """Apply to a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    shift = Shift.query.get(shift_id)
    if not shift:
        return jsonify({'error': 'Shift not found'}), 404

    if shift.status != ShiftStatus.LIVE:
        return jsonify({'error': 'Shift not available'}), 400

    # Check if already applied
    existing = Application.query.filter_by(
        shift_id=shift_id,
        worker_id=user.worker_profile.id
    ).first()

    if existing:
        return jsonify({'error': 'Already applied to this shift'}), 409

    data = request.get_json() or {}

    # Create application
    application = Application(
        shift_id=shift_id,
        worker_id=user.worker_profile.id,
        status=ApplicationStatus.APPLIED
    )

    # Handle counter offer
    if data.get('counter_rate'):
        application.status = ApplicationStatus.COUNTER_OFFER
        application.offered_rate = data['counter_rate']
        application.counter_expires_at = datetime.utcnow() + timedelta(hours=2)

    db.session.add(application)

    # Create notification for venue
    notification = Notification(
        user_id=shift.venue.user_id,
        title='New Application',
        message=f'{user.name} applied to your {shift.role} shift',
        notification_type='new_application',
        shift_id=shift_id,
        application_id=application.id
    )
    db.session.add(notification)

    db.session.commit()

    return jsonify({
        'message': 'Application submitted',
        'application': application.to_dict()
    }), 201

@app.route('/api/worker/applications', methods=['GET'])
@jwt_required()
def get_worker_applications():
    """Get worker's applications"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    applications = Application.query.filter_by(
        worker_id=user.worker_profile.id
    ).order_by(Application.applied_at.desc()).all()

    return jsonify({
        'applications': [app.to_dict() for app in applications]
    }), 200

# ===========================
# VENUE ROUTES
# ===========================

@app.route('/api/venue/profile', methods=['GET', 'PUT'])
@jwt_required()
def venue_profile():
    """Get or update venue profile"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user or user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    if request.method == 'GET':
        return jsonify(user.venue_profile.to_dict()), 200

    # PUT - Update profile
    data = request.get_json()
    profile = user.venue_profile

    if 'venue_name' in data:
        profile.venue_name = data['venue_name']
    if 'business_address' in data:
        profile.business_address = data['business_address']
    if 'industry_type' in data:
        profile.industry_type = data['industry_type']

    db.session.commit()
    return jsonify({'message': 'Profile updated', 'profile': profile.to_dict()}), 200

@app.route('/api/shifts', methods=['GET', 'POST'])
@jwt_required()
def shifts():
    """Get shifts or create new shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if request.method == 'GET':
        # Get venue's shifts
        if user.role != UserRole.VENUE:
            return jsonify({'error': 'Not a venue account'}), 403

        shifts = Shift.query.filter_by(venue_id=user.venue_profile.id).order_by(Shift.start_time.desc()).all()
        return jsonify({'shifts': [s.to_dict() for s in shifts]}), 200

    # POST - Create shift
    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    data = request.get_json()

    # Validate required fields
    required = ['role', 'start_time', 'end_time', 'hourly_rate']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    shift = Shift(
        venue_id=user.venue_profile.id,
        role=data['role'],
        start_time=datetime.fromisoformat(data['start_time']),
        end_time=datetime.fromisoformat(data['end_time']),
        hourly_rate=data['hourly_rate'],
        location=data.get('location', user.venue_profile.business_address),
        description=data.get('description', ''),
        num_workers_needed=data.get('num_workers_needed', 1),
        required_skills=data.get('required_skills', []),
        status=ShiftStatus.DRAFT
    )

    db.session.add(shift)
    db.session.commit()

    return jsonify({
        'message': 'Shift created',
        'shift': shift.to_dict()
    }), 201

@app.route('/api/shifts/<int:shift_id>/publish', methods=['POST'])
@jwt_required()
def publish_shift(shift_id):
    """Publish a draft shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    shift = Shift.query.get(shift_id)
    if not shift or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Shift not found'}), 404

    if shift.status != ShiftStatus.DRAFT:
        return jsonify({'error': 'Shift already published'}), 400

    shift.status = ShiftStatus.LIVE
    shift.published_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'message': 'Shift published',
        'shift': shift.to_dict()
    }), 200

@app.route('/api/shifts/<int:shift_id>/applications', methods=['GET'])
@jwt_required()
def get_shift_applications(shift_id):
    """Get applications for a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    shift = Shift.query.get(shift_id)
    if not shift or shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Shift not found'}), 404

    applications = shift.applications

    return jsonify({
        'applications': [app.to_dict() for app in applications]
    }), 200

@app.route('/api/applications/<int:app_id>/hire', methods=['POST'])
@jwt_required()
def hire_worker(app_id):
    """Hire a worker for a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    application = Application.query.get(app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    shift = application.shift
    if shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Not your shift'}), 403

    if application.status == ApplicationStatus.ACCEPTED:
        return jsonify({'error': 'Already hired'}), 400

    # Hire the worker
    application.status = ApplicationStatus.ACCEPTED
    application.hired_at = datetime.utcnow()
    application.hired_rate = application.offered_rate or shift.hourly_rate

    shift.num_workers_hired += 1

    # Update shift status if filled
    if shift.num_workers_hired >= shift.num_workers_needed:
        shift.status = ShiftStatus.FILLED
        shift.filled_at = datetime.utcnow()

    # Create notification for worker
    notification = Notification(
        user_id=application.worker.user_id,
        title='You Got the Shift!',
        message=f'You have been accepted for {shift.role} shift at {shift.venue.venue_name}',
        notification_type='hired',
        shift_id=shift.id,
        application_id=application.id
    )
    db.session.add(notification)

    db.session.commit()

    return jsonify({
        'message': 'Worker hired successfully',
        'application': application.to_dict()
    }), 200

# ===========================
# SHIFT EXECUTION ROUTES
# ===========================

@app.route('/api/shifts/<int:shift_id>/checkin', methods=['POST'])
@jwt_required()
def checkin_shift(shift_id):
    """Worker checks in to shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    # Verify worker is hired for this shift
    application = Application.query.filter_by(
        shift_id=shift_id,
        worker_id=user.worker_profile.id,
        status=ApplicationStatus.ACCEPTED
    ).first()

    if not application:
        return jsonify({'error': 'Not hired for this shift'}), 403

    data = request.get_json() or {}

    # Create or update timesheet
    timesheet = Timesheet.query.filter_by(
        shift_id=shift_id,
        worker_id=user.worker_profile.id
    ).first()

    if not timesheet:
        timesheet = Timesheet(
            shift_id=shift_id,
            worker_id=user.worker_profile.id
        )
        db.session.add(timesheet)

    timesheet.checked_in_at = datetime.utcnow()
    timesheet.check_in_lat = data.get('latitude')
    timesheet.check_in_lng = data.get('longitude')

    # Update shift status
    shift = Shift.query.get(shift_id)
    shift.status = ShiftStatus.IN_PROGRESS

    # Notify venue
    notification = Notification(
        user_id=shift.venue.user_id,
        title='Worker Checked In',
        message=f'{user.name} has checked in for {shift.role} shift',
        notification_type='checkin',
        shift_id=shift_id
    )
    db.session.add(notification)

    db.session.commit()

    return jsonify({
        'message': 'Checked in successfully',
        'timesheet': timesheet.to_dict()
    }), 200

@app.route('/api/shifts/<int:shift_id>/checkout', methods=['POST'])
@jwt_required()
def checkout_shift(shift_id):
    """Worker checks out from shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    timesheet = Timesheet.query.filter_by(
        shift_id=shift_id,
        worker_id=user.worker_profile.id
    ).first()

    if not timesheet or not timesheet.checked_in_at:
        return jsonify({'error': 'Not checked in'}), 400

    data = request.get_json() or {}

    timesheet.checked_out_at = datetime.utcnow()
    timesheet.check_out_lat = data.get('latitude')
    timesheet.check_out_lng = data.get('longitude')
    timesheet.break_minutes = data.get('break_minutes', 0)

    # Calculate hours
    duration = timesheet.checked_out_at - timesheet.checked_in_at
    total_minutes = duration.total_seconds() / 60 - timesheet.break_minutes
    timesheet.total_hours = round(total_minutes / 60, 2)

    # Calculate billable amount
    application = Application.query.filter_by(
        shift_id=shift_id,
        worker_id=user.worker_profile.id
    ).first()

    timesheet.billable_amount = timesheet.total_hours * application.hired_rate
    timesheet.submitted_at = datetime.utcnow()
    timesheet.approval_status = 'pending'

    # Notify venue
    shift = Shift.query.get(shift_id)
    notification = Notification(
        user_id=shift.venue.user_id,
        title='Timesheet Submitted',
        message=f'{user.name} submitted {timesheet.total_hours}h for approval',
        notification_type='timesheet_submitted',
        shift_id=shift_id
    )
    db.session.add(notification)

    db.session.commit()

    return jsonify({
        'message': 'Checked out successfully',
        'timesheet': timesheet.to_dict()
    }), 200

@app.route('/api/timesheets/<int:timesheet_id>/approve', methods=['POST'])
@jwt_required()
def approve_timesheet(timesheet_id):
    """Venue approves timesheet"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if user.role != UserRole.VENUE:
        return jsonify({'error': 'Not a venue account'}), 403

    timesheet = Timesheet.query.get(timesheet_id)
    if not timesheet:
        return jsonify({'error': 'Timesheet not found'}), 404

    shift = timesheet.shift
    if shift.venue_id != user.venue_profile.id:
        return jsonify({'error': 'Not your shift'}), 403

    data = request.get_json() or {}
    action = data.get('action', 'approve')  # approve, query, reject

    if action == 'approve':
        timesheet.approval_status = 'approved'
        timesheet.approved_at = datetime.utcnow()
        timesheet.approved_by = user_id

        # Update shift status
        shift.status = ShiftStatus.COMPLETED

        # Notify worker
        notification = Notification(
            user_id=timesheet.worker.user_id,
            title='Timesheet Approved',
            message=f'Your hours were approved for {shift.role} shift',
            notification_type='timesheet_approved',
            shift_id=shift.id
        )
        db.session.add(notification)

    elif action == 'query':
        timesheet.approval_status = 'disputed'
        timesheet.dispute_reason = data.get('reason', '')
        shift.status = ShiftStatus.DISPUTED

        # Notify worker
        notification = Notification(
            user_id=timesheet.worker.user_id,
            title='Timesheet Queried',
            message=f'Venue has queried your submitted hours',
            notification_type='timesheet_disputed',
            shift_id=shift.id
        )
        db.session.add(notification)

    db.session.commit()

    return jsonify({
        'message': f'Timesheet {action}d',
        'timesheet': timesheet.to_dict()
    }), 200

# ===========================
# CHAT ROUTES
# ===========================

@app.route('/api/shifts/<int:shift_id>/chat', methods=['GET', 'POST'])
@jwt_required()
def shift_chat(shift_id):
    """Get or send chat messages for a shift"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    shift = Shift.query.get(shift_id)
    if not shift:
        return jsonify({'error': 'Shift not found'}), 404

    if request.method == 'GET':
        # Get messages
        messages = ChatMessage.query.filter_by(shift_id=shift_id).filter(
            db.or_(
                ChatMessage.sender_id == user_id,
                ChatMessage.receiver_id == user_id
            )
        ).order_by(ChatMessage.created_at).all()

        return jsonify({
            'messages': [{
                'id': m.id,
                'sender_id': m.sender_id,
                'message': m.message,
                'created_at': m.created_at.isoformat(),
                'is_read': m.is_read
            } for m in messages]
        }), 200

    # POST - Send message
    data = request.get_json()

    if not data.get('message'):
        return jsonify({'error': 'Message required'}), 400

    # Determine receiver
    if user.role == UserRole.WORKER:
        receiver_id = shift.venue.user_id
    else:
        # Find the worker (simplified - first accepted application)
        app = Application.query.filter_by(
            shift_id=shift_id,
            status=ApplicationStatus.ACCEPTED
        ).first()
        if not app:
            return jsonify({'error': 'No hired worker yet'}), 400
        receiver_id = app.worker.user_id

    message = ChatMessage(
        shift_id=shift_id,
        sender_id=user_id,
        receiver_id=receiver_id,
        message=data['message']
    )
    db.session.add(message)
    db.session.commit()

    return jsonify({
        'message': 'Message sent',
        'chat_message': {
            'id': message.id,
            'message': message.message,
            'created_at': message.created_at.isoformat()
        }
    }), 201

# ===========================
# NOTIFICATION ROUTES
# ===========================

@app.route('/api/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get user notifications"""
    user_id = get_jwt_identity()

    notifications = Notification.query.filter_by(
        user_id=user_id
    ).order_by(Notification.created_at.desc()).limit(50).all()

    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'shift_id': n.shift_id,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat()
        } for n in notifications]
    }), 200

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    """Mark notification as read"""
    user_id = get_jwt_identity()

    notification = Notification.query.get(notification_id)
    if not notification or notification.user_id != user_id:
        return jsonify({'error': 'Notification not found'}), 404

    notification.is_read = True
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
        'endpoints': {
            'health': '/api/health',
            'auth': {
                'register': 'POST /api/auth/register',
                'login': 'POST /api/auth/login',
                'me': 'GET /api/auth/me'
            },
            'worker': {
                'search_shifts': 'GET /api/shifts/search',
                'apply': 'POST /api/shifts/{id}/apply',
                'applications': 'GET /api/worker/applications',
                'profile': 'GET /api/worker/profile'
            },
            'venue': {
                'shifts': 'GET /api/shifts',
                'create_shift': 'POST /api/shifts',
                'applications': 'GET /api/shifts/{id}/applications',
                'hire': 'POST /api/applications/{id}/hire'
            }
        },
        'documentation': 'https://github.com/yourusername/diisco-api'
    }), 200

@app.route('/api', methods=['GET'])
def api_home():
    """API endpoint list"""
    return jsonify({
        'message': 'Diisco API v1.0',
        'status': 'operational',
        'endpoints': [
            'GET /api/health',
            'POST /api/auth/register',
            'POST /api/auth/login',
            'GET /api/auth/me',
            'GET /api/shifts/search',
            'POST /api/shifts/{id}/apply',
            'GET /api/worker/applications',
            'GET /api/notifications'
        ]
    }), 200

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200

# ===========================
# DATABASE INITIALIZATION
# ===========================

@app.cli.command('init-db')
def init_db():
    """Initialize the database"""
    db.create_all()
    print("Database initialized!")

@app.cli.command('seed-db')
def seed_db():
    """Seed database with sample data"""
    # Create sample venue
    venue_user = User(
        email='venue@test.com',
        password_hash=bcrypt.generate_password_hash('password123').decode('utf-8'),
        role=UserRole.VENUE,
        name='The Golden Bar'
    )
    db.session.add(venue_user)
    db.session.flush()

    venue_profile = VenueProfile(
        user_id=venue_user.id,
        venue_name='The Golden Bar',
        business_address='123 Main St, Leeds',
        industry_type='Bar'
    )
    db.session.add(venue_profile)

    # Create sample worker
    worker_user = User(
        email='worker@test.com',
        password_hash=bcrypt.generate_password_hash('password123').decode('utf-8'),
        role=UserRole.WORKER,
        name='John Worker'
    )
    db.session.add(worker_user)
    db.session.flush()

    worker_profile = WorkerProfile(
        user_id=worker_user.id,
        referral_code='JOHN123'
    )
    db.session.add(worker_profile)

    db.session.commit()
    print("Database seeded!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
