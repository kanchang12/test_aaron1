"""
Diisco Platform - Database Creation & Migration Script

This script will:
1. Create all database tables from models.py
2. Add all new columns to existing tables
3. Verify database structure
4. Create initial test data (optional)

Run this script once to set up the database.
"""

from app import app, db
from models import (
    User, UserRole, WorkerProfile, VenueProfile, Shift, ShiftStatus,
    Application, ApplicationStatus, Rating, Dispute, DisputeStatus,
    AvailabilitySlot, Referral, ReferralTransaction, VenueTeamMember,
    Timesheet, ChatMessage, Notification, NotificationType
)
from datetime import datetime, timedelta
import random
import string

def generate_referral_code(length=8):
    """Generate a random referral code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def create_all_tables():
    """Create all database tables"""
    print("🗄️  Creating all database tables...")

    with app.app_context():
        try:
            # Drop all tables (CAUTION: This will delete all data!)
            # Comment out the next line if you want to preserve existing data
            # db.drop_all()
            # print("⚠️  Dropped all existing tables")

            # Create all tables
            db.create_all()
            print("✅ All tables created successfully!")

            # Verify tables
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            print(f"\n📋 Created {len(tables)} tables:")
            for table in sorted(tables):
                print(f"   - {table}")

            return True

        except Exception as e:
            print(f"❌ Error creating tables: {str(e)}")
            return False

def verify_database_structure():
    """Verify all expected tables and columns exist"""
    print("\n🔍 Verifying database structure...")

    with app.app_context():
        try:
            inspector = db.inspect(db.engine)

            # Expected tables
            expected_tables = [
                'users', 'worker_profiles', 'venue_profiles', 'shifts',
                'applications', 'ratings', 'disputes', 'availability_slots',
                'referrals', 'referral_transactions', 'venue_team_members',
                'timesheets', 'chat_messages', 'notifications'
            ]

            tables = inspector.get_table_names()

            # Check each expected table
            all_good = True
            for table in expected_tables:
                if table in tables:
                    columns = [col['name'] for col in inspector.get_columns(table)]
                    print(f"✅ {table}: {len(columns)} columns")
                else:
                    print(f"❌ {table}: MISSING!")
                    all_good = False

            # Check critical columns in Shift table
            if 'shifts' in tables:
                shift_columns = [col['name'] for col in inspector.get_columns('shifts')]
                critical_fields = ['num_workers_needed', 'num_workers_hired', 'is_boosted', 'description']
                missing_fields = [f for f in critical_fields if f not in shift_columns]

                if missing_fields:
                    print(f"⚠️  Shift table missing fields: {missing_fields}")
                else:
                    print(f"✅ Shift table has all critical fields")

            # Check critical columns in Application table
            if 'applications' in tables:
                app_columns = [col['name'] for col in inspector.get_columns('applications')]
                critical_fields = ['offered_rate', 'hired_rate', 'applied_at']
                missing_fields = [f for f in critical_fields if f not in app_columns]

                if missing_fields:
                    print(f"⚠️  Application table missing fields: {missing_fields}")
                else:
                    print(f"✅ Application table has all critical fields")

            return all_good

        except Exception as e:
            print(f"❌ Error verifying structure: {str(e)}")
            return False

def create_test_data():
    """Create initial test data for development"""
    print("\n🧪 Creating test data...")

    with app.app_context():
        try:
            from werkzeug.security import generate_password_hash

            # Create test worker
            test_worker = User(
                email='worker@test.com',
                password_hash=generate_password_hash('password123'),
                role=UserRole.WORKER,
                name='Test Worker',
                phone='+44 7700 900000',
                address='123 Test Street, London, UK',
                email_verified=True,
                is_active=True
            )
            db.session.add(test_worker)
            db.session.flush()

            # Create worker profile
            worker_profile = WorkerProfile(
                user_id=test_worker.id,
                id_verified=True,
                rating=4.5,
                average_rating=4.5,
                total_shifts=10,
                completed_shifts=9,
                reliability_score=95.0,
                referral_code=generate_referral_code(),
                notification_channels={'push': True, 'email': True, 'sms': False},
                notification_distance=10.0,
                notification_min_rate=12.0
            )
            db.session.add(worker_profile)

            # Create test venue
            test_venue = User(
                email='venue@test.com',
                password_hash=generate_password_hash('password123'),
                role=UserRole.VENUE,
                name='Test Manager',
                phone='+44 7700 900001',
                email_verified=True,
                is_active=True
            )
            db.session.add(test_venue)
            db.session.flush()

            # Create venue profile
            venue_profile = VenueProfile(
                user_id=test_venue.id,
                venue_name='The Test Pub',
                business_address='456 Venue Road, London, UK',
                contact_phone='+44 20 7946 0958',
                industry_type='Hospitality',
                rating=4.2,
                average_rating=4.2,
                total_shifts_posted=25
            )
            db.session.add(venue_profile)
            db.session.flush()

            # Create test admin
            test_admin = User(
                email='admin@test.com',
                password_hash=generate_password_hash('admin123'),
                role=UserRole.ADMIN,
                name='Admin User',
                email_verified=True,
                is_active=True
            )
            db.session.add(test_admin)

            # Create test shift
            test_shift = Shift(
                venue_id=venue_profile.id,
                role='Bartender',
                description='Busy Friday night shift at city center pub',
                start_time=datetime.now() + timedelta(days=7, hours=18),
                end_time=datetime.now() + timedelta(days=7, hours=23),
                location='The Test Pub, London',
                hourly_rate=15.50,
                status=ShiftStatus.LIVE,
                num_workers_needed=2,
                num_workers_hired=0,
                required_skills=['bartending', 'customer_service'],
                is_boosted=False,
                fill_risk='low'
            )
            db.session.add(test_shift)

            db.session.commit()

            print("✅ Test data created successfully!")
            print("\n📝 Test Accounts:")
            print(f"   Worker: worker@test.com / password123")
            print(f"   Venue:  venue@test.com / password123")
            print(f"   Admin:  admin@test.com / admin123")

            return True

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating test data: {str(e)}")
            return False

def show_statistics():
    """Show database statistics"""
    print("\n📊 Database Statistics:")

    with app.app_context():
        try:
            print(f"   Users: {User.query.count()}")
            print(f"   Workers: {WorkerProfile.query.count()}")
            print(f"   Venues: {VenueProfile.query.count()}")
            print(f"   Shifts: {Shift.query.count()}")
            print(f"   Applications: {Application.query.count()}")
            print(f"   Ratings: {Rating.query.count()}")
            print(f"   Disputes: {Dispute.query.count()}")
            print(f"   Availability Slots: {AvailabilitySlot.query.count()}")
            print(f"   Referrals: {Referral.query.count()}")
            print(f"   Team Members: {VenueTeamMember.query.count()}")
            print(f"   Timesheets: {Timesheet.query.count()}")
            print(f"   Chat Messages: {ChatMessage.query.count()}")
            print(f"   Notifications: {Notification.query.count()}")

        except Exception as e:
            print(f"❌ Error getting statistics: {str(e)}")

def main():
    """Main migration function"""
    print("=" * 60)
    print("🚀 DIISCO PLATFORM - DATABASE SETUP")
    print("=" * 60)

    # Step 1: Create all tables
    if not create_all_tables():
        print("\n❌ Database setup failed at table creation step")
        return False

    # Step 2: Verify structure
    if not verify_database_structure():
        print("\n⚠️  Database structure has issues, but continuing...")

    # Step 3: Ask about test data
    create_test = input("\n❓ Create test data? (y/n): ").lower().strip()
    if create_test == 'y':
        create_test_data()

    # Step 4: Show statistics
    show_statistics()

    print("\n" + "=" * 60)
    print("✅ DATABASE SETUP COMPLETE!")
    print("=" * 60)
    print("\n📚 Next Steps:")
    print("   1. Configure environment variables in .env")
    print("   2. Start the Flask server: python app.py")
    print("   3. Test API endpoints with Postman or curl")
    print("   4. Build and test Flutter app")
    print("\n🔒 Security Note:")
    print("   - Change default passwords before production!")
    print("   - Add strong SECRET_KEY in .env")
    print("   - Enable 2FA for admin accounts")
    print("\n")

    return True

if __name__ == '__main__':
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
