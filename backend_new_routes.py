def handle_referral_on_shift_complete(worker_user_id, shift_id):
    """Accumulate referral reward when referred user completes a shift."""
    # Find referral for this worker
    referral = Referral.query.filter_by(referred_user_id=worker_user_id, status='active').first()
    if referral:
        # Increment shifts_completed
        referral.shifts_completed = (referral.shifts_completed or 0) + 1
        # Add £1 to referrer's balance
        referrer = User.query.get(referral.referrer_id)
        if referrer and referrer.worker_profile:
            referrer.worker_profile.referral_balance = (referrer.worker_profile.referral_balance or 0) + 1.0
            # Create transaction record
            transaction = ReferralTransaction(
                user_id=referrer.id,
                referral_id=referral.id,
                amount=1.0,
                transaction_type='earn',
                status='completed'
            )
            db.session.add(transaction)
        db.session.commit()

    # After marking shift as completed, call referral handler
    handle_referral_on_shift_complete(worker_user_id, shift_id)
# ===========================
# NEW ROUTES TO ADD TO YOUR EXISTING app.py
# Copy these routes into your Flask application
# ===========================

# Add these imports at the top of your app.py:
# import openai  # For CV parsing
# from sqlalchemy import func

# ===========================
# CV UPLOAD & PARSING
# ===========================

@app.route('/api/worker/cv/upload', methods=['POST'])
@jwt_required()
def upload_cv_file():
    """Upload CV file"""
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user or user.role != UserRole.WORKER:
        return jsonify({'error': 'Not a worker account'}), 403

    data = request.get_json()
    cv_url = data.get('cv_url')

    if not cv_url:
        return jsonify({'error': 'CV URL required'}), 400

    # Simple AI parsing (in production, use OpenAI GPT-4 or similar)
    # For now, generate a sample summary
    cv_summary = f"Experienced hospitality professional with 3+ years in bartending and serving roles. Skilled in customer service, cocktail preparation, and high-volume environments."

    # TODO: Implement actual CV parsing with OpenAI
    # openai.api_key = os.getenv('OPENAI_API_KEY')
    # response = openai.ChatCompletion.create(
    #     model="gpt-4",
    #     messages=[{
    #         "role": "system",
    #         "content": "Extract hospitality experience from CV and summarize in one sentence"
    #     }]
    # )
    # cv_summary = response.choices[0].message.content

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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
    user_id = get_jwt_identity()
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
# ===========================
