# ===============================================
# Diisco Backend API Testing Script (PowerShell)
# Test all new endpoints with Invoke-RestMethod
# ===============================================

# Configuration
$BaseUrl = "http://localhost:5000/api"
$WorkerToken = ""
$VenueToken = ""

# Helper function to print headers
function Print-Header {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Yellow
    Write-Host $Message -ForegroundColor Yellow
    Write-Host "========================================`n" -ForegroundColor Yellow
}

# Helper function to print results
function Print-Result {
    param([bool]$Success, [string]$Message)
    if ($Success) {
        Write-Host "✓ PASS: $Message" -ForegroundColor Green
    } else {
        Write-Host "✗ FAIL: $Message" -ForegroundColor Red
    }
}

# ===============================================
# 1. AUTHENTICATION TESTS
# ===============================================
Print-Header "1. AUTHENTICATION TESTS"

# Register Worker
Write-Host "Testing: Register Worker"
try {
    $workerBody = @{
        email = "testworker@diisco.com"
        password = "password123"
        name = "Test Worker"
        role = "worker"
        phone = "+44 7700 900000"
    } | ConvertTo-Json

    $workerResponse = Invoke-RestMethod -Uri "$BaseUrl/auth/register" -Method Post -Body $workerBody -ContentType "application/json"
    $WorkerToken = $workerResponse.access_token
    Print-Result $true "Worker Registration"
    Write-Host "Worker Token: $WorkerToken"
} catch {
    Print-Result $false "Worker Registration - $_"
}

# Register Venue
Write-Host "`nTesting: Register Venue"
try {
    $venueBody = @{
        email = "testvenue@diisco.com"
        password = "password123"
        name = "Test Venue Manager"
        role = "venue"
        venue_name = "The Golden Bar"
    } | ConvertTo-Json

    $venueResponse = Invoke-RestMethod -Uri "$BaseUrl/auth/register" -Method Post -Body $venueBody -ContentType "application/json"
    $VenueToken = $venueResponse.access_token
    Print-Result $true "Venue Registration"
    Write-Host "Venue Token: $VenueToken"
} catch {
    Print-Result $false "Venue Registration - $_"
}

# Login Worker
Write-Host "`nTesting: Login Worker"
try {
    $loginBody = @{
        email = "testworker@diisco.com"
        password = "password123"
    } | ConvertTo-Json

    $loginResponse = Invoke-RestMethod -Uri "$BaseUrl/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
    Print-Result $true "Worker Login"
} catch {
    Print-Result $false "Worker Login - $_"
}

# ===============================================
# 2. CV UPLOAD & PARSING TESTS
# ===============================================
Print-Header "2. CV UPLOAD & PARSING TESTS"

# Create dummy CV file
"Sample CV Content for Testing" | Out-File -FilePath "test_cv.txt"

# Upload CV
Write-Host "Testing: Upload CV"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
    }

    $filePath = Resolve-Path "test_cv.txt"
    $form = @{
        cv = Get-Item -Path $filePath
    }

    $cvResponse = Invoke-RestMethod -Uri "$BaseUrl/worker/cv/upload" -Method Post -Headers $headers -Form $form
    $cvUrl = $cvResponse.cv_url
    Print-Result $true "CV Upload"
    Write-Host "CV URL: $cvUrl"
} catch {
    Print-Result $false "CV Upload - $_"
}

# Parse CV
Write-Host "`nTesting: Parse CV"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
        "Content-Type" = "application/json"
    }

    $parseBody = @{
        cv_url = $cvUrl
    } | ConvertTo-Json

    $parseResponse = Invoke-RestMethod -Uri "$BaseUrl/worker/cv/parse" -Method Post -Headers $headers -Body $parseBody
    Print-Result $true "CV Parsing"
} catch {
    Print-Result $false "CV Parsing - $_"
}

# Update Profile
Write-Host "`nTesting: Update Profile"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
        "Content-Type" = "application/json"
    }

    $profileBody = @{
        bio = "Experienced bartender with 5 years experience"
        cv_summary = "Expert in cocktails and customer service"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "$BaseUrl/auth/profile" -Method Patch -Headers $headers -Body $profileBody
    Print-Result $true "Update Profile"
} catch {
    Print-Result $false "Update Profile - $_"
}

# ===============================================
# 3. AVAILABILITY CALENDAR TESTS
# ===============================================
Print-Header "3. AVAILABILITY CALENDAR TESTS"

# Set Availability - Unavailable
Write-Host "Testing: Set Availability (Unavailable)"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
        "Content-Type" = "application/json"
    }

    $availBody = @{
        date = "2025-12-25"
        is_available = $false
        reason = "Christmas Holiday"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "$BaseUrl/worker/availability" -Method Post -Headers $headers -Body $availBody
    Print-Result $true "Set Availability (Unavailable)"
} catch {
    Print-Result $false "Set Availability - $_"
}

# Get Availability
Write-Host "`nTesting: Get Availability"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
    }

    $availResponse = Invoke-RestMethod -Uri "$BaseUrl/worker/availability" -Method Get -Headers $headers
    Print-Result $true "Get Availability"
} catch {
    Print-Result $false "Get Availability - $_"
}

# ===============================================
# 4. REFERRAL SYSTEM TESTS
# ===============================================
Print-Header "4. REFERRAL SYSTEM TESTS"

# Get Referrals
Write-Host "Testing: Get Referrals"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
    }

    $refResponse = Invoke-RestMethod -Uri "$BaseUrl/referrals" -Method Get -Headers $headers
    Print-Result $true "Get Referrals"
} catch {
    Print-Result $false "Get Referrals - $_"
}

# Refer a Venue
Write-Host "`nTesting: Refer Venue"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
        "Content-Type" = "application/json"
    }

    $referBody = @{
        venue_name = "The New Pub"
        manager_name = "John Manager"
        manager_email = "john@thenewpub.com"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "$BaseUrl/referrals/venue" -Method Post -Headers $headers -Body $referBody
    Print-Result $true "Refer Venue"
} catch {
    Print-Result $false "Refer Venue - $_"
}

# ===============================================
# 5. DISPUTE RESOLUTION TESTS
# ===============================================
Print-Header "5. DISPUTE RESOLUTION TESTS"

# Create dummy evidence file
"Evidence photo data" | Out-File -FilePath "test_evidence.jpg"

# Create Dispute
Write-Host "Testing: Create Dispute"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
    }

    $form = @{
        shift_id = "1"
        dispute_type = "hours_dispute"
        description = "Venue says I worked 5 hours but I worked 6 hours"
        evidence = Get-Item -Path "test_evidence.jpg"
    }

    Invoke-RestMethod -Uri "$BaseUrl/disputes" -Method Post -Headers $headers -Form $form
    Print-Result $true "Create Dispute"
} catch {
    Print-Result $false "Create Dispute - $_"
}

# Get Disputes
Write-Host "`nTesting: Get Disputes"
try {
    $headers = @{
        "Authorization" = "Bearer $WorkerToken"
    }

    Invoke-RestMethod -Uri "$BaseUrl/disputes" -Method Get -Headers $headers
    Print-Result $true "Get Disputes"
} catch {
    Print-Result $false "Get Disputes - $_"
}

# ===============================================
# 6. SHIFT BOOSTING TESTS (VENUE)
# ===============================================
Print-Header "6. SHIFT BOOSTING TESTS"

# Create Boost Payment Intent
Write-Host "Testing: Create Boost Payment Intent"
try {
    $headers = @{
        "Authorization" = "Bearer $VenueToken"
        "Content-Type" = "application/json"
    }

    $boostBody = @{
        shift_id = 1
        amount = 1999
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "$BaseUrl/payments/boost" -Method Post -Headers $headers -Body $boostBody
    Print-Result $true "Create Boost Payment Intent"
} catch {
    Print-Result $false "Create Boost Payment - $_"
}

# ===============================================
# 7. MULTI-VENUE MANAGEMENT TESTS
# ===============================================
Print-Header "7. MULTI-VENUE MANAGEMENT TESTS"

# Get Venues
Write-Host "Testing: Get Venues"
try {
    $headers = @{
        "Authorization" = "Bearer $VenueToken"
    }

    Invoke-RestMethod -Uri "$BaseUrl/venues" -Method Get -Headers $headers
    Print-Result $true "Get Venues"
} catch {
    Print-Result $false "Get Venues - $_"
}

# Create Venue Location
Write-Host "`nTesting: Create Venue Location"
try {
    $headers = @{
        "Authorization" = "Bearer $VenueToken"
        "Content-Type" = "application/json"
    }

    $venueBody = @{
        name = "The Golden Bar - Downtown"
        address = "456 Main St, London"
        phone = "+44 20 7946 0958"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "$BaseUrl/venues" -Method Post -Headers $headers -Body $venueBody
    Print-Result $true "Create Venue Location"
} catch {
    Print-Result $false "Create Venue - $_"
}

# Invite Team Member
Write-Host "`nTesting: Invite Team Member"
try {
    $headers = @{
        "Authorization" = "Bearer $VenueToken"
        "Content-Type" = "application/json"
    }

    $inviteBody = @{
        name = "Sarah Manager"
        email = "sarah@goldebar.com"
        role = "manager"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "$BaseUrl/venues/team/invite" -Method Post -Headers $headers -Body $inviteBody
    Print-Result $true "Invite Team Member"
} catch {
    Print-Result $false "Invite Team Member - $_"
}

# ===============================================
# 8. SMART MATCHING TESTS
# ===============================================
Print-Header "8. SMART MATCHING TESTS"

# Get Smart Matches
Write-Host "Testing: Get Smart Matches"
try {
    $headers = @{
        "Authorization" = "Bearer $VenueToken"
    }

    Invoke-RestMethod -Uri "$BaseUrl/shifts/1/matches" -Method Get -Headers $headers
    Print-Result $true "Get Smart Matches"
} catch {
    Print-Result $false "Get Smart Matches - $_"
}

# ===============================================
# 9. RATINGS TESTS
# ===============================================
Print-Header "9. RATINGS TESTS"

# Create Rating
Write-Host "Testing: Create Rating"
try {
    $headers = @{
        "Authorization" = "Bearer $VenueToken"
        "Content-Type" = "application/json"
    }

    $ratingBody = @{
        shift_id = 1
        rated_user_id = 1
        stars = 4.5
        comment = "Great worker, very professional"
        tags = @("Punctual", "Professional", "Friendly")
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "$BaseUrl/ratings" -Method Post -Headers $headers -Body $ratingBody
    Print-Result $true "Create Rating"
} catch {
    Print-Result $false "Create Rating - $_"
}

# ===============================================
# CLEANUP
# ===============================================
Print-Header "CLEANUP"
Remove-Item -Path "test_cv.txt" -ErrorAction SilentlyContinue
Remove-Item -Path "test_evidence.jpg" -ErrorAction SilentlyContinue
Write-Host "Temporary test files removed"

# ===============================================
# SUMMARY
# ===============================================
Print-Header "TEST SUMMARY"
Write-Host "All endpoints have been tested!"
Write-Host ""
Write-Host "Note: Some tests may fail if:" -ForegroundColor Cyan
Write-Host "  - Backend is not running (flask run)" -ForegroundColor Cyan
Write-Host "  - Database is not initialized (flask db upgrade)" -ForegroundColor Cyan
Write-Host "  - New routes are not added to app.py yet" -ForegroundColor Cyan
Write-Host "  - Shift ID 1 doesn't exist in database" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run this script:" -ForegroundColor Yellow
Write-Host "  powershell -ExecutionPolicy Bypass -File test_api_endpoints.ps1" -ForegroundColor Yellow
