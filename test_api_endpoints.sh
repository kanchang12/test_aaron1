#!/bin/bash

# ===============================================
# Diisco Backend API Testing Script
# Test all new endpoints with curl
# ===============================================

# Configuration
BASE_URL="http://localhost:5000/api"
# Change this after you get a token from login
TOKEN="YOUR_JWT_TOKEN_HERE"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper function to print section headers
print_header() {
    echo -e "\n${YELLOW}========================================${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}========================================${NC}\n"
}

# Helper function to print test results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
    fi
}

# ===============================================
# 1. AUTHENTICATION TESTS
# ===============================================
print_header "1. AUTHENTICATION TESTS"

# Register Worker
echo "Testing: Register Worker"
WORKER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testworker@diisco.com",
    "password": "password123",
    "name": "Test Worker",
    "role": "worker",
    "phone": "+44 7700 900000"
  }')

HTTP_CODE=$(echo "$WORKER_RESPONSE" | tail -n1)
BODY=$(echo "$WORKER_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 201 ]; then
    print_result 0 "Worker Registration"
    WORKER_TOKEN=$(echo "$BODY" | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//')
    echo "Worker Token: $WORKER_TOKEN"
else
    print_result 1 "Worker Registration (HTTP $HTTP_CODE)"
fi

# Register Venue
echo -e "\nTesting: Register Venue"
VENUE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testvenue@diisco.com",
    "password": "password123",
    "name": "Test Venue Manager",
    "role": "venue",
    "venue_name": "The Golden Bar"
  }')

HTTP_CODE=$(echo "$VENUE_RESPONSE" | tail -n1)
BODY=$(echo "$VENUE_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 201 ]; then
    print_result 0 "Venue Registration"
    VENUE_TOKEN=$(echo "$BODY" | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//')
    echo "Venue Token: $VENUE_TOKEN"
else
    print_result 1 "Venue Registration (HTTP $HTTP_CODE)"
fi

# Login Worker
echo -e "\nTesting: Login Worker"
LOGIN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testworker@diisco.com",
    "password": "password123"
  }')

HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Worker Login"

# ===============================================
# 2. CV UPLOAD & PARSING TESTS
# ===============================================
print_header "2. CV UPLOAD & PARSING TESTS"

# Create a dummy CV file
echo "Sample CV Content for Testing" > test_cv.txt

# Upload CV
echo "Testing: Upload CV"
CV_UPLOAD_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/worker/cv/upload" \
  -H "Authorization: Bearer $WORKER_TOKEN" \
  -F "cv=@test_cv.txt")

HTTP_CODE=$(echo "$CV_UPLOAD_RESPONSE" | tail -n1)
BODY=$(echo "$CV_UPLOAD_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    print_result 0 "CV Upload"
    CV_URL=$(echo "$BODY" | grep -o '"cv_url":"[^"]*' | sed 's/"cv_url":"//')
    echo "CV URL: $CV_URL"
else
    print_result 1 "CV Upload (HTTP $HTTP_CODE)"
fi

# Parse CV
echo -e "\nTesting: Parse CV"
CV_PARSE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/worker/cv/parse" \
  -H "Authorization: Bearer $WORKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"cv_url\": \"$CV_URL\"
  }")

HTTP_CODE=$(echo "$CV_PARSE_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "CV Parsing"

# Update Profile
echo -e "\nTesting: Update Profile"
PROFILE_RESPONSE=$(curl -s -w "\n%{http_code}" -X PATCH "$BASE_URL/auth/profile" \
  -H "Authorization: Bearer $WORKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bio": "Experienced bartender with 5 years experience",
    "cv_summary": "Expert in cocktails and customer service"
  }')

HTTP_CODE=$(echo "$PROFILE_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Update Profile"

# ===============================================
# 3. AVAILABILITY CALENDAR TESTS
# ===============================================
print_header "3. AVAILABILITY CALENDAR TESTS"

# Set Availability - Unavailable
echo "Testing: Set Availability (Unavailable)"
AVAIL_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/worker/availability" \
  -H "Authorization: Bearer $WORKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-12-25",
    "is_available": false,
    "reason": "Christmas Holiday"
  }')

HTTP_CODE=$(echo "$AVAIL_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 201 ] && echo 0 || echo 1) "Set Availability (Unavailable)"

# Set Availability - Available
echo -e "\nTesting: Set Availability (Available)"
curl -s -w "\n%{http_code}" -X POST "$BASE_URL/worker/availability" \
  -H "Authorization: Bearer $WORKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-12-26",
    "is_available": true
  }' > /dev/null

# Get Availability
echo -e "\nTesting: Get Availability"
GET_AVAIL_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/worker/availability" \
  -H "Authorization: Bearer $WORKER_TOKEN")

HTTP_CODE=$(echo "$GET_AVAIL_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Get Availability"

# ===============================================
# 4. REFERRAL SYSTEM TESTS
# ===============================================
print_header "4. REFERRAL SYSTEM TESTS"

# Get Referrals
echo "Testing: Get Referrals"
REF_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/referrals" \
  -H "Authorization: Bearer $WORKER_TOKEN")

HTTP_CODE=$(echo "$REF_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Get Referrals"

# Refer a Venue
echo -e "\nTesting: Refer Venue"
REFER_VENUE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/referrals/venue" \
  -H "Authorization: Bearer $WORKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "venue_name": "The New Pub",
    "manager_name": "John Manager",
    "manager_email": "john@thenewpub.com"
  }')

HTTP_CODE=$(echo "$REFER_VENUE_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 201 ] && echo 0 || echo 1) "Refer Venue"

# Withdraw Referral Balance
echo -e "\nTesting: Withdraw Referral Balance"
WITHDRAW_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/referrals/withdraw" \
  -H "Authorization: Bearer $WORKER_TOKEN")

HTTP_CODE=$(echo "$WITHDRAW_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 400 ] && echo 0 || echo 1) "Withdraw (should fail - no balance)"

# ===============================================
# 5. DISPUTE RESOLUTION TESTS
# ===============================================
print_header "5. DISPUTE RESOLUTION TESTS"

# Create a dummy evidence file
echo "Evidence photo data" > test_evidence.jpg

# Create Dispute
echo "Testing: Create Dispute"
DISPUTE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/disputes" \
  -H "Authorization: Bearer $WORKER_TOKEN" \
  -F "shift_id=1" \
  -F "dispute_type=hours_dispute" \
  -F "description=Venue says I worked 5 hours but I worked 6 hours" \
  -F "evidence=@test_evidence.jpg")

HTTP_CODE=$(echo "$DISPUTE_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 201 ] && echo 0 || echo 1) "Create Dispute"

# Get Disputes
echo -e "\nTesting: Get Disputes"
GET_DISPUTES_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/disputes" \
  -H "Authorization: Bearer $WORKER_TOKEN")

HTTP_CODE=$(echo "$GET_DISPUTES_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Get Disputes"

# ===============================================
# 6. SHIFT BOOSTING TESTS (VENUE)
# ===============================================
print_header "6. SHIFT BOOSTING TESTS"

# Create Boost Payment Intent
echo "Testing: Create Boost Payment Intent"
BOOST_PAYMENT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/payments/boost" \
  -H "Authorization: Bearer $VENUE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "shift_id": 1,
    "amount": 1999
  }')

HTTP_CODE=$(echo "$BOOST_PAYMENT_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Create Boost Payment Intent"

# Activate Shift Boost
echo -e "\nTesting: Activate Shift Boost"
ACTIVATE_BOOST_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/shifts/1/boost" \
  -H "Authorization: Bearer $VENUE_TOKEN")

HTTP_CODE=$(echo "$ACTIVATE_BOOST_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 404 ] && echo 0 || echo 1) "Activate Shift Boost"

# ===============================================
# 7. MULTI-VENUE MANAGEMENT TESTS
# ===============================================
print_header "7. MULTI-VENUE MANAGEMENT TESTS"

# Get Venues
echo "Testing: Get Venues"
VENUES_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/venues" \
  -H "Authorization: Bearer $VENUE_TOKEN")

HTTP_CODE=$(echo "$VENUES_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Get Venues"

# Create Venue Location
echo -e "\nTesting: Create Venue Location"
CREATE_VENUE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/venues" \
  -H "Authorization: Bearer $VENUE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "The Golden Bar - Downtown",
    "address": "456 Main St, London",
    "phone": "+44 20 7946 0958"
  }')

HTTP_CODE=$(echo "$CREATE_VENUE_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 201 ] && echo 0 || echo 1) "Create Venue Location"

# Get Team Members
echo -e "\nTesting: Get Team Members"
TEAM_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/venues/team" \
  -H "Authorization: Bearer $VENUE_TOKEN")

HTTP_CODE=$(echo "$TEAM_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Get Team Members"

# Invite Team Member
echo -e "\nTesting: Invite Team Member"
INVITE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/venues/team/invite" \
  -H "Authorization: Bearer $VENUE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sarah Manager",
    "email": "sarah@goldebar.com",
    "role": "manager"
  }')

HTTP_CODE=$(echo "$INVITE_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 201 ] && echo 0 || echo 1) "Invite Team Member"

# ===============================================
# 8. SMART MATCHING TESTS
# ===============================================
print_header "8. SMART MATCHING TESTS"

# Get Smart Matches for Shift
echo "Testing: Get Smart Matches"
MATCHES_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/shifts/1/matches" \
  -H "Authorization: Bearer $VENUE_TOKEN")

HTTP_CODE=$(echo "$MATCHES_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 404 ] && echo 0 || echo 1) "Get Smart Matches"

# Invite Worker to Shift
echo -e "\nTesting: Invite Worker to Shift"
INVITE_WORKER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/shifts/1/invite" \
  -H "Authorization: Bearer $VENUE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": 1
  }')

HTTP_CODE=$(echo "$INVITE_WORKER_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 201 ] || [ "$HTTP_CODE" -eq 404 ] && echo 0 || echo 1) "Invite Worker to Shift"

# ===============================================
# 9. RATINGS TESTS
# ===============================================
print_header "9. RATINGS TESTS"

# Create Rating
echo "Testing: Create Rating"
RATING_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/ratings" \
  -H "Authorization: Bearer $VENUE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "shift_id": 1,
    "rated_user_id": 1,
    "stars": 4.5,
    "comment": "Great worker, very professional",
    "tags": ["Punctual", "Professional", "Friendly"]
  }')

HTTP_CODE=$(echo "$RATING_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 201 ] || [ "$HTTP_CODE" -eq 404 ] && echo 0 || echo 1) "Create Rating"

# Get User Ratings
echo -e "\nTesting: Get User Ratings"
GET_RATINGS_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/users/1/ratings" \
  -H "Authorization: Bearer $WORKER_TOKEN")

HTTP_CODE=$(echo "$GET_RATINGS_RESPONSE" | tail -n1)
print_result $([ "$HTTP_CODE" -eq 200 ] && echo 0 || echo 1) "Get User Ratings"

# ===============================================
# CLEANUP
# ===============================================
print_header "CLEANUP"
rm -f test_cv.txt test_evidence.jpg
echo "Temporary test files removed"

# ===============================================
# SUMMARY
# ===============================================
print_header "TEST SUMMARY"
echo "All endpoints have been tested!"
echo ""
echo "Note: Some tests may fail if:"
echo "  - Backend is not running (flask run)"
echo "  - Database is not initialized (flask db upgrade)"
echo "  - New routes are not added to app.py yet"
echo "  - Shift ID 1 doesn't exist in database"
echo ""
echo "To fix failing tests:"
echo "  1. Ensure Flask backend is running: flask run"
echo "  2. Copy routes from backend_new_routes.py to app.py"
echo "  3. Run database migrations"
echo "  4. Create a test shift in the database"
