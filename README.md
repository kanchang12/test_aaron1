# Diisco Flutter Android App

Flutter Android application for the Diisco hospitality gig platform - connecting workers with venue shifts.

## Features

### For Workers
- Browse and search available shifts
- Apply to shifts with one-tap
- Make counter-offers on rates
- GPS check-in/check-out
- Track applications and earnings
- Chat with venues
- Real-time notifications
- Profile and CV management

### For Venues
- Post and manage shifts
- Review applications
- Hire workers
- Approve timesheets
- Chat with workers
- Analytics and reporting
- Favorite workers management

## Prerequisites

- Flutter SDK (>=3.0.0)
- Android Studio / VS Code
- Android device or emulator (API 21+)
- Backend API running (see `/diisco_backend`)

## Setup

### 1. Install Dependencies

```bash
cd diisco_flutter
flutter pub get
```

### 2. Configure Backend URL

Edit `lib/services/api_service.dart` and update the `baseUrl`:

```dart
// For Android emulator
static const String baseUrl = 'http://10.0.2.2:5000/api';

// For physical device (use your computer's IP)
static const String baseUrl = 'http://192.168.1.XXX:5000/api';

// For production
static const String baseUrl = 'https://your-backend.com/api';
```

### 3. Run the App

```bash
# Check connected devices
flutter devices

# Run on connected device/emulator
flutter run

# Build APK for release
flutter build apk --release
```

## Project Structure

```
lib/
├── main.dart              # App entry point
├── models/
│   └── models.dart        # Data models
├── services/
│   └── api_service.dart   # Backend API communication
└── screens/
    ├── auth/              # Login & Registration
    ├── worker/            # Worker features
    └── venue/             # Venue features
```

## Key Packages

- `http` - API communication
- `provider` - State management
- `shared_preferences` - Local storage
- `flutter_secure_storage` - Secure token storage
- `geolocator` - GPS location
- `google_maps_flutter` - Maps integration
- `intl` - Date/time formatting

## Testing

### Quick Test Login

The app includes quick test buttons in development mode:

**Worker Account:**
- Email: worker@test.com
- Password: password123

**Venue Account:**
- Email: venue@test.com
- Password: password123

*Note: Backend must be seeded with these accounts using `flask seed-db`*

## Common Tasks

### Worker Flow
1. Login/Register as Worker
2. Browse available shifts in "Find Shifts" tab
3. Tap a shift to view details
4. Apply or make counter offer
5. Check "Applications" tab for status
6. When hired, check-in with GPS when arriving
7. Check-out when shift completes

### Venue Flow
1. Login/Register as Venue
2. Tap "+" to create a new shift
3. Fill shift details and create
4. Publish shift to make it live
5. View applications when workers apply
6. Hire workers from applications
7. Approve timesheets after shift completion

## Troubleshooting

### Cannot connect to backend

- Ensure backend is running on port 5000
- Check `baseUrl` in `api_service.dart`
- For Android emulator, use `10.0.2.2` instead of `localhost`
- For physical device, use your computer's local IP
- Ensure phone and computer are on same WiFi network

### Build errors

```bash
# Clean and rebuild
flutter clean
flutter pub get
flutter run
```

### Location permissions

- Enable location permissions in device settings
- Check AndroidManifest.xml has location permissions

## Next Steps

1. Implement Firebase push notifications
2. Add Google Maps for shift locations
3. Implement CV upload with AI parsing
4. Add chat with real-time messaging
5. Implement payment processing
6. Add analytics dashboard
7. Implement referral system UI
8. Add ratings and reviews UI

## Environment Variables

The app uses the backend API which requires:
- Stripe API keys (for payments)
- OpenAI API key (for CV parsing)
- Twilio credentials (for SMS)

See backend `.env.example` for full configuration.

## Production Deployment

### Build Release APK

```bash
flutter build apk --release
```

Output: `build/app/outputs/flutter-apk/app-release.apk`

### Build App Bundle (for Play Store)

```bash
flutter build appbundle --release
```

Output: `build/app/outputs/bundle/release/app-release.aab`

### Before Publishing

1. Update version in `pubspec.yaml`
2. Generate app signing key
3. Update backend URL to production
4. Remove debug features
5. Test thoroughly on physical devices
6. Add privacy policy
7. Prepare app store listings

## Support

For issues or questions:
- Backend API: See `/diisco_backend/README.md`
- Flutter issues: Check Flutter docs
- App issues: Create GitHub issue
