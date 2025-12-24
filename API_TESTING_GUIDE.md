# 🧪 API Testing Guide

## 📋 Overview

Two test scripts have been created to test all **28 new backend endpoints**:

1. **`test_api_endpoints.sh`** - Bash script (Linux/Mac/Git Bash)
2. **`test_api_endpoints.ps1`** - PowerShell script (Windows)

---

## 🚀 How to Run Tests

### **Windows (PowerShell)**

```powershell
# Navigate to project folder
cd "C:\Users\kanch\Desktop\Disco Project\code\diisco_complete_project\diisco_flutter"

# Run the PowerShell script
powershell -ExecutionPolicy Bypass -File test_api_endpoints.ps1
```

### **Linux/Mac/Git Bash**

```bash
# Navigate to project folder
cd ~/Desktop/Disco\ Project/code/diisco_complete_project/diisco_flutter

# Make script executable
chmod +x test_api_endpoints.sh

# Run the script
./test_api_endpoints.sh
```

---

## ⚙️ Prerequisites

### 1. **Backend Must Be Running**

```bash
# Start Flask backend
cd your_backend_folder
flask run
```

Backend should be running at: `http://localhost:5000`

### 2. **Database Must Be Migrated**

```bash
# Run migrations
flask db upgrade

# OR initialize fresh database
flask init-db
```

### 3. **New Routes Must Be Added**

Copy routes from `backend_new_routes.py` into your `app.py`

---

## 📊 What Gets Tested

### **1. Authentication (3 tests)**
- ✅ Worker Registration
- ✅ Venue Registration
- ✅ Worker Login

### **2. CV Upload & Parsing (3 tests)**
- ✅ Upload CV file
- ✅ Parse CV with AI
- ✅ Update profile

### **3. Availability Calendar (3 tests)**
- ✅ Set unavailable date
- ✅ Set available date
- ✅ Get availability list

### **4. Referral System (3 tests)**
- ✅ Get referrals
- ✅ Refer a venue
- ✅ Withdraw earnings (should fail - no balance)

### **5. Dispute Resolution (2 tests)**
- ✅ Create dispute with evidence
- ✅ Get disputes list

### **6. Shift Boosting (2 tests)**
- ✅ Create Stripe payment intent
- ✅ Activate shift boost

### **7. Multi-Venue Management (4 tests)**
- ✅ Get venues list
- ✅ Create venue location
- ✅ Get team members
- ✅ Invite team member

### **8. Smart Matching (2 tests)**
- ✅ Get smart matches for shift
- ✅ Invite worker to shift

### **9. Ratings (2 tests)**
- ✅ Create rating
- ✅ Get user ratings

**Total: 24 endpoint tests**

---

## 📖 Test Output Example

```
========================================
1. AUTHENTICATION TESTS
========================================

Testing: Register Worker
✓ PASS: Worker Registration
Worker Token: eyJ0eXAiOiJKV1QiLCJhbGc...

Testing: Register Venue
✓ PASS: Venue Registration
Venue Token: eyJ0eXAiOiJKV1QiLCJhbGc...

Testing: Login Worker
✓ PASS: Worker Login

========================================
2. CV UPLOAD & PARSING TESTS
========================================

Testing: Upload CV
✓ PASS: CV Upload
CV URL: /uploads/cvs/cv_1_abc123.txt

Testing: Parse CV
✓ PASS: CV Parsing

Testing: Update Profile
✓ PASS: Update Profile
```

---

## 🔍 Troubleshooting

### ❌ **All Tests Failing**

**Problem**: Backend not running

**Solution**:
```bash
# Start Flask
flask run

# Or with debug mode
flask run --debug
```

---

### ❌ **404 Errors on New Endpoints**

**Problem**: New routes not added to `app.py`

**Solution**:
1. Open `backend_new_routes.py`
2. Copy all route functions
3. Paste into your `app.py`
4. Restart Flask

---

### ❌ **Database Errors**

**Problem**: Tables don't exist

**Solution**:
```bash
# Run migrations
flask db migrate -m "Add new features"
flask db upgrade

# OR copy models and reinit
python
>>> from app import db
>>> db.create_all()
```

---

### ❌ **"Shift not found" Errors**

**Problem**: No shifts in database

**Solution**: Create a test shift first:

```bash
curl -X POST http://localhost:5000/api/shifts \
  -H "Authorization: Bearer $VENUE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "Bartender",
    "start_time": "2025-12-30T18:00:00",
    "end_time": "2025-12-30T23:00:00",
    "hourly_rate": 15.0,
    "num_workers_needed": 1
  }'
```

---

## 🎯 Manual Testing (Individual Endpoints)

### **Test CV Upload**

```bash
# Windows PowerShell
$headers = @{"Authorization" = "Bearer YOUR_TOKEN"}
Invoke-RestMethod -Uri "http://localhost:5000/api/worker/cv/upload" `
  -Method Post -Headers $headers -Form @{cv = Get-Item "test_cv.pdf"}

# Linux/Mac
curl -X POST http://localhost:5000/api/worker/cv/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "cv=@test_cv.pdf"
```

### **Test Availability**

```bash
# Windows PowerShell
$headers = @{
    "Authorization" = "Bearer YOUR_TOKEN"
    "Content-Type" = "application/json"
}
$body = @{
    date = "2025-12-25"
    is_available = $false
    reason = "Holiday"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/api/worker/availability" `
  -Method Post -Headers $headers -Body $body

# Linux/Mac
curl -X POST http://localhost:5000/api/worker/availability \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date":"2025-12-25","is_available":false,"reason":"Holiday"}'
```

### **Test Referral**

```bash
# Windows PowerShell
$headers = @{
    "Authorization" = "Bearer YOUR_TOKEN"
    "Content-Type" = "application/json"
}
$body = @{
    venue_name = "The New Pub"
    manager_name = "John Manager"
    manager_email = "john@newpub.com"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/api/referrals/venue" `
  -Method Post -Headers $headers -Body $body

# Linux/Mac
curl -X POST http://localhost:5000/api/referrals/venue \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "venue_name":"The New Pub",
    "manager_name":"John Manager",
    "manager_email":"john@newpub.com"
  }'
```

---

## 📝 Getting Your Auth Token

### **Method 1: From Test Script**

The test scripts automatically register users and save tokens. Check the console output:

```
Worker Token: eyJ0eXAiOiJKV1QiLCJhbGc...
Venue Token: eyJ0eXAiOiJKV1QiLCJhbGc...
```

### **Method 2: Manual Login**

```bash
# Login and get token
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"testworker@diisco.com","password":"password123"}'

# Response will include:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {...}
}
```

---

## 🔐 Using Tokens in Tests

Replace `YOUR_TOKEN` in the scripts with actual tokens:

```bash
# In bash script
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

# In PowerShell
$Token = "eyJ0eXAiOiJKV1QiLCJhbGc..."
```

---

## ✅ Expected Results

### **All Tests Passing**

```
✓ PASS: Worker Registration
✓ PASS: Venue Registration
✓ PASS: Worker Login
✓ PASS: CV Upload
✓ PASS: CV Parsing
✓ PASS: Update Profile
✓ PASS: Set Availability (Unavailable)
✓ PASS: Get Availability
✓ PASS: Get Referrals
✓ PASS: Refer Venue
✗ FAIL: Withdraw (should fail - no balance) ← This is expected!
✓ PASS: Create Dispute
✓ PASS: Get Disputes
... (more tests)
```

### **Some Tests May Fail If**

1. ❌ **Backend not running** → Start `flask run`
2. ❌ **Routes not added** → Copy from `backend_new_routes.py`
3. ❌ **Database not migrated** → Run `flask db upgrade`
4. ❌ **No test shift** → Create one manually
5. ❌ **Stripe/OpenAI keys missing** → Add to `.env`

---

## 📚 Next Steps

After all tests pass:

1. ✅ Test from Flutter app: `flutter run`
2. ✅ Verify each feature in the UI
3. ✅ Check database for created records
4. ✅ Monitor Flask logs for errors
5. ✅ Deploy to production when ready

---

## 🆘 Support

If tests fail, check:

1. **Flask logs** - Run with `flask run --debug`
2. **Network** - Is backend accessible at `localhost:5000`?
3. **CORS** - Is `flask-cors` installed and configured?
4. **Database** - Can you query tables directly?

---

Happy Testing! 🚀
