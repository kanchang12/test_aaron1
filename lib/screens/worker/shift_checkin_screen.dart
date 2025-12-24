import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:geolocator/geolocator.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';

/// Screen for checking into a shift with GPS verification
/// Verifies worker is at venue location before allowing check-in
class ShiftCheckInScreen extends StatefulWidget {
  final Shift shift;

  const ShiftCheckInScreen({
    super.key,
    required this.shift,
  });

  @override
  State<ShiftCheckInScreen> createState() => _ShiftCheckInScreenState();
}

class _ShiftCheckInScreenState extends State<ShiftCheckInScreen> {
  bool _isCheckingIn = false;
  bool _isLoadingLocation = false;
  Position? _currentPosition;
  double? _distanceToVenue;
  bool _locationServiceEnabled = false;
  bool _hasLocationPermission = false;
  String? _locationError;

  // GPS verification radius in meters (e.g., 100 meters = ~328 feet)
  static const double _checkInRadiusMeters = 100.0;

  @override
  void initState() {
    super.initState();
    _checkLocationServices();
  }

  Future<void> _checkLocationServices() async {
    setState(() {
      _isLoadingLocation = true;
      _locationError = null;
    });

    try {
      // Check if location services are enabled
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        setState(() {
          _locationServiceEnabled = false;
          _locationError = 'Location services are disabled. Please enable them in your device settings.';
          _isLoadingLocation = false;
        });
        return;
      }

      // Check location permission
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          setState(() {
            _hasLocationPermission = false;
            _locationError = 'Location permission denied. Please grant permission to check in.';
            _isLoadingLocation = false;
          });
          return;
        }
      }

      if (permission == LocationPermission.deniedForever) {
        setState(() {
          _hasLocationPermission = false;
          _locationError = 'Location permission permanently denied. Please enable in app settings.';
          _isLoadingLocation = false;
        });
        return;
      }

      // Get current location
      setState(() {
        _locationServiceEnabled = true;
        _hasLocationPermission = true;
      });

      await _getCurrentLocation();
    } catch (e) {
      setState(() {
        _locationError = 'Error checking location: ${e.toString()}';
        _isLoadingLocation = false;
      });
    }
  }

  Future<void> _getCurrentLocation() async {
    setState(() => _isLoadingLocation = true);

    try {
      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );

      // Calculate distance to venue
      // Note: In production, venue coordinates would come from shift.venue
      // For now, we'll use mock coordinates from shift.location
      double distance = _calculateDistance(position);

      setState(() {
        _currentPosition = position;
        _distanceToVenue = distance;
        _isLoadingLocation = false;
      });
    } catch (e) {
      setState(() {
        _locationError = 'Failed to get location: ${e.toString()}';
        _isLoadingLocation = false;
      });
    }
  }

  double _calculateDistance(Position position) {
    // TODO: Replace with actual venue coordinates from shift data
    // For now, using mock coordinates
    // In production: Parse shift.location or shift.venue.latitude/longitude

    // Mock venue coordinates (replace with actual from backend)
    double venueLat = 51.5074; // London example
    double venueLon = -0.1278;

    return Geolocator.distanceBetween(
      position.latitude,
      position.longitude,
      venueLat,
      venueLon,
    );
  }

  Future<void> _performCheckIn() async {
    if (_currentPosition == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please wait for location to be verified'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    if (_distanceToVenue != null && _distanceToVenue! > _checkInRadiusMeters) {
      _showDistanceWarningDialog();
      return;
    }

    setState(() => _isCheckingIn = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      await api.checkInToShift(
        widget.shift.id,
        _currentPosition!.latitude,
        _currentPosition!.longitude,
      );

      if (!mounted) return;

      // Show success message
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Successfully checked in!'),
          backgroundColor: Colors.green,
        ),
      );

      // Return to previous screen
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;

      setState(() => _isCheckingIn = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Check-in failed: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void _showDistanceWarningDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Too Far From Venue'),
        content: Text(
          'You are ${(_distanceToVenue! / 1000).toStringAsFixed(2)} km (${(_distanceToVenue! * 3.28084).toStringAsFixed(0)} ft) from the venue.\n\n'
          'You must be within ${(_checkInRadiusMeters * 3.28084).toStringAsFixed(0)} feet to check in.\n\n'
          'Please move closer to the venue location.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
          ElevatedButton.icon(
            onPressed: () {
              Navigator.pop(context);
              _getCurrentLocation();
            },
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final startTime = DateTime.parse(widget.shift.startTime);
    final endTime = DateTime.parse(widget.shift.endTime);
    final canCheckIn = _currentPosition != null &&
        _distanceToVenue != null &&
        _distanceToVenue! <= _checkInRadiusMeters;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Check In to Shift'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Shift Details Card
            Card(
              elevation: 4,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.shift.role,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 16),
                    _buildInfoRow(
                      Icons.calendar_today,
                      'Date',
                      DateFormat('EEEE, MMMM dd, yyyy').format(startTime),
                    ),
                    _buildInfoRow(
                      Icons.access_time,
                      'Time',
                      '${DateFormat.jm().format(startTime)} - ${DateFormat.jm().format(endTime)}',
                    ),
                    if (widget.shift.location != null)
                      _buildInfoRow(
                        Icons.location_on,
                        'Location',
                        widget.shift.location!,
                      ),
                    _buildInfoRow(
                      Icons.attach_money,
                      'Rate',
                      '£${widget.shift.hourlyRate.toStringAsFixed(2)}/hr',
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // GPS Verification Section
            Card(
              elevation: 4,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          Icons.gps_fixed,
                          color: Theme.of(context).primaryColor,
                          size: 28,
                        ),
                        const SizedBox(width: 12),
                        const Text(
                          'Location Verification',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    if (_isLoadingLocation) ...[
                      const Center(
                        child: Column(
                          children: [
                            CircularProgressIndicator(),
                            SizedBox(height: 16),
                            Text('Verifying your location...'),
                          ],
                        ),
                      ),
                    ] else if (_locationError != null) ...[
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.red.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.red.withOpacity(0.3)),
                        ),
                        child: Column(
                          children: [
                            const Icon(Icons.error_outline, color: Colors.red, size: 48),
                            const SizedBox(height: 12),
                            Text(
                              _locationError!,
                              textAlign: TextAlign.center,
                              style: const TextStyle(color: Colors.red),
                            ),
                            const SizedBox(height: 16),
                            ElevatedButton.icon(
                              onPressed: _checkLocationServices,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Retry'),
                            ),
                          ],
                        ),
                      ),
                    ] else if (_currentPosition != null && _distanceToVenue != null) ...[
                      // Location Status
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: canCheckIn
                              ? Colors.green.withOpacity(0.1)
                              : Colors.orange.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: canCheckIn
                                ? Colors.green.withOpacity(0.3)
                                : Colors.orange.withOpacity(0.3),
                          ),
                        ),
                        child: Column(
                          children: [
                            Icon(
                              canCheckIn ? Icons.check_circle : Icons.warning,
                              color: canCheckIn ? Colors.green : Colors.orange,
                              size: 48,
                            ),
                            const SizedBox(height: 12),
                            Text(
                              canCheckIn
                                  ? 'You are at the venue!'
                                  : 'You are too far from the venue',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: canCheckIn ? Colors.green : Colors.orange,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Distance: ${(_distanceToVenue! / 1000).toStringAsFixed(2)} km (${(_distanceToVenue! * 3.28084).toStringAsFixed(0)} ft)',
                              style: const TextStyle(fontSize: 14),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Required: Within ${(_checkInRadiusMeters * 3.28084).toStringAsFixed(0)} feet',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey[600],
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Refresh Location Button
                      OutlinedButton.icon(
                        onPressed: _isLoadingLocation ? null : _getCurrentLocation,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Refresh Location'),
                        style: OutlinedButton.styleFrom(
                          minimumSize: const Size.fromHeight(48),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Info Box
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue.withOpacity(0.3)),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.info_outline, color: Colors.blue, size: 20),
                      SizedBox(width: 8),
                      Text(
                        'Check-In Requirements',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.blue,
                        ),
                      ),
                    ],
                  ),
                  SizedBox(height: 8),
                  Text(
                    '• You must be at the venue location to check in\n'
                    '• Enable location services on your device\n'
                    '• Check in within 15 minutes of shift start time\n'
                    '• Your check-in time is recorded for the timesheet',
                    style: TextStyle(fontSize: 14, height: 1.5),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 32),

            // Check-In Button
            ElevatedButton.icon(
              onPressed: (_isCheckingIn || !canCheckIn) ? null : _performCheckIn,
              icon: _isCheckingIn
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Icon(Icons.check_circle),
              label: Text(_isCheckingIn ? 'Checking In...' : 'Check In to Shift'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                minimumSize: const Size.fromHeight(56),
                backgroundColor: canCheckIn ? null : Colors.grey,
              ),
            ),

            if (!canCheckIn && _distanceToVenue != null) ...[
              const SizedBox(height: 12),
              Text(
                'Move closer to the venue to enable check-in',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.grey[600],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 20, color: Colors.grey[600]),
          const SizedBox(width: 12),
          Text(
            label,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
