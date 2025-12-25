# Diisco Backend API

Flask-based REST API for the Diisco hospitality gig platform.

## Features

- User authentication (Workers, Venues, Admins)
- Shift management (create, publish, apply, hire)
- Real-time notifications
- Chat messaging
- Timesheet & payment processing
- Geolocation check-in/out
- Referral system
- Rating & feedback

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### 3. Initialize Database

```bash
flask init-db
flask seed-db  # Optional: Add sample data
```

### 4. Run Server

```bash
# Development
python app.py

# Production
gunicorn app:app
```

The server will run on `http://localhost:5000`

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user

### Worker Endpoints
- `GET/PUT /api/worker/profile` - Worker profile
- `POST /api/worker/upload-cv` - Upload CV
- `GET /api/shifts/search` - Search available shifts
- `POST /api/shifts/<id>/apply` - Apply to shift
- `GET /api/worker/applications` - Get applications
- `POST /api/shifts/<id>/checkin` - Check in to shift
- `POST /api/shifts/<id>/checkout` - Check out from shift

### Venue Endpoints
- `GET/PUT /api/venue/profile` - Venue profile
- `GET/POST /api/shifts` - List/create shifts
- `POST /api/shifts/<id>/publish` - Publish shift
- `GET /api/shifts/<id>/applications` - Get applications
- `POST /api/applications/<id>/hire` - Hire worker
- `POST /api/timesheets/<id>/approve` - Approve timesheet

### Common Endpoints
- `GET/POST /api/shifts/<id>/chat` - Chat messages
- `GET /api/notifications` - Get notifications
- `POST /api/notifications/<id>/read` - Mark as read

## Authentication

All protected endpoints require JWT token in header:
```
Authorization: Bearer <token>
```

Get token from `/api/auth/login` or `/api/auth/register`

## Database Schema

- **Users** - Base user accounts
- **WorkerProfiles** - Worker-specific data
- **VenueProfiles** - Venue-specific data
- **Shifts** - Job postings
- **Applications** - Worker applications
- **Timesheets** - Check-in/out records
- **Ratings** - Feedback
- **ChatMessages** - Communications
- **Notifications** - Alerts
- **Referrals** - Referral tracking

## Deployment

### Deploy to Cloud Run / Heroku / Railway

1. Add database URL to environment (PostgreSQL recommended for production)
2. Set all environment variables
3. Run migrations: `flask init-db`
4. Deploy with gunicorn

## Next Steps

1. Implement Stripe payment processing
2. Add OpenAI CV parsing
3. Implement Twilio SMS notifications
4. Add Google Maps geolocation
5. Build admin panel
6. Add analytics endpoints
