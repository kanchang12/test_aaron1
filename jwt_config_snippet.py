# JWT configuration for 30-day session persistence
from datetime import timedelta

# Add this to your Flask app configuration (e.g., in your app.py or main backend file)
JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)

# If using Flask-JWT-Extended, set:
# app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
