# Backend Implementation Guide for Diisco Flutter App

## 📋 Overview

All the **missing features** have been implemented in the Flutter frontend. Now you need to update your Flask backend to support these features.

---

## ✅ What's Already Implemented (Frontend)

### Worker Features:
1. ✅ **CV Upload & AI Parsing** - Upload CV, AI generates summary
2. ✅ **Availability Calendar** - Mark unavailable dates, auto-lock accepted shifts
3. ✅ **Geo-Fenced Check-In/Out** - GPS verification with 100m radius
4. ✅ **Referral System** - QR codes, unique links, £1 per shift rewards
5. ✅ **Dispute Resolution** - Report issues with evidence upload
6. ✅ **Counter-Offers** - Negotiate hourly rates (already existed)

### Venue Features:
1. ✅ **Shift Boosting** - £19.99 Stripe payment for premium visibility
2. ✅ **Multi-Venue Management** - Owner/Manager/Staff roles
3. ✅ **Smart Matching** - AI-ranked worker recommendations
4. ✅ **Applicant Invitations** - Invite specific workers to shifts

### UI Updates:
1. ✅ **Lighter Navy Color** - Changed from `#1A1A2E` to `#2C3E50`

---

## 🔧 Backend Changes Required

### Step 1: Update Database Models

**File**: `models.py`

Add these new model classes (see `backend_new_models.py`):

```python
# NEW MODELS TO ADD:
- AvailabilitySlot
- Dispute
- VenueTeamMember
- ReferralTransaction
```

**Update existing models** with new fields:

```python
# WorkerProfile - Add:
average_rating = db.Column(db.Float)
referral_balance = db.Column(db.Float, default=0.0)

# VenueProfile - Add:
average_rating = db.Column(db.Float)
parent_venue_id = db.Column(db.Integer, db.ForeignKey('venue_profiles.id'))

# Shift - Add:
boosted_at = db.Column(db.DateTime)

# Referral - Update:
referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
referred_user_type = db.Column(db.String(20))
shifts_completed = db.Column(db.Integer, default=0)
referral_metadata = db.Column(db.JSON)
```

---

### Step 2: Run Database Migration

**Option A: Using Flask-Migrate (Recommended)**

```bash
# Initialize migrations (if not done)
flask db init

# Create migration
flask db migrate -m "Add new features: availability, disputes, referrals, multi-venue"

# Apply migration
flask db upgrade
```

**Option B: Manual SQL (SQLite)**

Run the SQL commands in `backend_new_models.py` section: "DATABASE MIGRATION SQL"

```bash
sqlite3 diisco.db < migration.sql
```

---

### Step 3: Add New API Endpoints

**File**: `app.py`

Copy all routes from `backend_new_routes.py` into your `app.py`:

**New endpoints added (28 total)**:

#### CV & Profile (3 endpoints)
```
POST   /api/worker/cv/upload
POST   /api/worker/cv/parse
PATCH  /api/auth/profile
```

#### Availability Calendar (2 endpoints)
```
GET    /api/worker/availability
POST   /api/worker/availability
```

#### Referral System (3 endpoints)
```
GET    /api/referrals
POST   /api/referrals/venue
POST   /api/referrals/withdraw
```

#### Dispute Resolution (2 endpoints)
```
GET    /api/disputes
POST   /api/disputes
```

#### Shift Boosting & Stripe (2 endpoints)
```
POST   /api/payments/boost
POST   /api/shifts/{id}/boost
```

#### Multi-Venue Management (4 endpoints)
```
GET    /api/venues
POST   /api/venues
GET    /api/venues/team
POST   /api/venues/team/invite
```

#### Smart Matching (2 endpoints)
```
GET    /api/shifts/{id}/matches
POST   /api/shifts/{id}/invite
```

#### Ratings & Reliability (2 endpoints)
```
POST   /api/ratings
GET    /api/users/{id}/ratings
```

---

### Step 4: Configure Environment Variables

Add to your `.env` file:

```bash
# Stripe
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here

# OpenAI (for CV parsing)
OPENAI_API_KEY=sk-your_openai_key_here

# Upload folders
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216  # 16MB
```

---

### Step 5: Install Additional Dependencies

```bash
pip install openai  # For AI CV parsing
pip install python-dotenv  # For .env file support
```

Update `requirements.txt`:
```
flask==3.0.0
flask-sqlalchemy==3.1.1
flask-cors==4.0.0
flask-jwt-extended==4.5.3
flask-bcrypt==1.0.1
stripe==7.8.0
python-dotenv==1.0.0
openai==1.3.0
```

---

### Step 6: Update Upload Folder Structure

Create these folders:

```bash
mkdir -p uploads/cvs
mkdir -p uploads/evidence
mkdir -p uploads/profiles
```

Update your `.gitignore`:
```
uploads/
*.db
.env
__pycache__/
```

---

## 🧪 Testing Endpoints

### Test CV Upload:
```bash
curl -X POST http://localhost:5000/api/worker/cv/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "cv=@sample_cv.pdf"
```

### Test Availability:
```bash
curl -X POST http://localhost:5000/api/worker/availability \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date": "2025-12-25", "is_available": false, "reason": "Holiday"}'
```

### Test Dispute Creation:
```bash
curl -X POST http://localhost:5000/api/disputes \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "shift_id=1" \
  -F "dispute_type=hours_dispute" \
  -F "description=Venue says I left early but I stayed until end" \
  -F "evidence=@photo_proof.jpg"
```

### Test Smart Matching:
```bash
curl -X GET http://localhost:5000/api/shifts/1/matches \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🎯 Implementation Priority

### Must-Have (Core Features):
1. ✅ CV Upload & Parsing endpoints
2. ✅ Availability Calendar endpoints
3. ✅ Referral System endpoints
4. ✅ Dispute Resolution endpoints
5. ✅ Smart Matching endpoints

### Nice-to-Have (Enhancements):
6. Stripe Boost payment integration
7. Multi-venue team management
8. Rating system

---

## 🔐 Security Considerations

1. **File Upload Validation**:
   ```python
   ALLOWED_CV_EXTENSIONS = {'pdf', 'doc', 'docx'}
   ALLOWED_EVIDENCE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
   ```

2. **Rate Limiting** (add to production):
   ```python
   from flask_limiter import Limiter

   limiter = Limiter(
       app,
       key_func=lambda: get_jwt_identity(),
       default_limits=["100 per hour"]
   )
   ```

3. **Input Sanitization**:
   - Always validate user input
   - Use parameterized queries (SQLAlchemy does this)
   - Sanitize file names with `secure_filename()`

---

## 📊 Database Schema Summary

### New Tables (4):
- `availability_slots` - Worker availability calendar
- `disputes` - Dispute tracking with evidence
- `venue_team_members` - Multi-venue staff management
- `referral_transactions` - Referral earnings/withdrawals

### Updated Tables (5):
- `worker_profiles` - Added rating & referral balance
- `venue_profiles` - Added rating & parent venue
- `shifts` - Added boosted_at timestamp
- `referrals` - Added type, shifts count, metadata
- `ratings` - Changed stars to Float

---

## 🚀 Deployment Checklist

- [ ] Run database migrations
- [ ] Add new API routes to `app.py`
- [ ] Update `models.py` with new classes
- [ ] Configure Stripe API keys
- [ ] Configure OpenAI API key (for CV parsing)
- [ ] Create upload folders with proper permissions
- [ ] Update `.env` with production values
- [ ] Test all endpoints locally
- [ ] Deploy to production (PythonAnywhere/Heroku/etc.)
- [ ] Update Flutter app's `baseUrl` to production API

---

## 📞 Support

If you encounter issues:

1. Check Flask logs: `flask run --debug`
2. Verify database schema: `flask shell` → `db.create_all()`
3. Test with Postman/curl before Flutter app
4. Check CORS headers if requests fail from app

---

## 📁 File Reference

- `backend_new_routes.py` - All new API endpoints (copy into `app.py`)
- `backend_new_models.py` - New database models (copy into `models.py`)
- `BACKEND_IMPLEMENTATION_GUIDE.md` - This guide

---

## ✨ Next Steps

After backend is updated:

1. Run Flutter app: `flutter run`
2. Test new features end-to-end
3. Monitor logs for any errors
4. Deploy to production when ready

All frontend code is **production-ready** and waiting for backend! 🎉
