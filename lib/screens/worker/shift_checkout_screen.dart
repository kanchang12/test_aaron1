import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:geolocator/geolocator.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';

/// Screen for checking out of a shift with GPS verification and timesheet generation
/// Records end time, verifies location, and generates timesheet for approval
class ShiftCheckOutScreen extends StatefulWidget {
  final Shift shift;
  final DateTime checkInTime;

  const ShiftCheckOutScreen({
    super.key,
    required this.shift,
    required this.checkInTime,
  });

  @override
  State<ShiftCheckOutScreen> createState() => _ShiftCheckOutScreenState();
}

class _ShiftCheckOutScreenState extends State<ShiftCheckOutScreen> {
  bool _isCheckingOut = false;
  bool _isLoadingLocation = false;
  Position? _currentPosition;
  double? _distanceToVenue;
  String? _locationError;

  // Break tracking
  final List<Map<String, DateTime>> _breaks = [];
  DateTime? _breakStartTime;
  bool _isOnBreak = false;

  // Notes for timesheet
  final TextEditingController _notesController = TextEditingController();

  static const double _checkOutRadiusMeters = 100.0;

  @override
  void initState() {
    super.initState();
    _getCurrentLocation();
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _getCurrentLocation() async {
    setState(() {
      _isLoadingLocation = true;
      _locationError = null;
    });

    try {
      // Check location services
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        setState(() {
          _locationError = 'Location services are disabled';
          _isLoadingLocation = false;
        });
        return;
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        setState(() {
          _locationError = 'Location permission denied';
          _isLoadingLocation = false;
        });
        return;
      }

      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );

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
    // Mock venue coordinates (replace with actual from backend)
    double venueLat = 51.5074;
    double venueLon = -0.1278;

    return Geolocator.distanceBetween(
      position.latitude,
      position.longitude,
      venueLat,
      venueLon,
    );
  }

  void _startBreak() {
    setState(() {
      _breakStartTime = DateTime.now();
      _isOnBreak = true;
    });
  }

  void _endBreak() {
    if (_breakStartTime != null) {
      setState(() {
        _breaks.add({
          'start': _breakStartTime!,
          'end': DateTime.now(),
        });
        _breakStartTime = null;
        _isOnBreak = false;
      });
    }
  }

  Duration _calculateTotalBreakTime() {
    Duration total = Duration.zero;
    for (var breakPeriod in _breaks) {
      total += breakPeriod['end']!.difference(breakPeriod['start']!);
    }
    return total;
  }

  Duration _calculateWorkedTime() {
    final now = DateTime.now();
    final totalTime = now.difference(widget.checkInTime);
    final breakTime = _calculateTotalBreakTime();
    return totalTime - breakTime;
  }

  double _calculateEarnings() {
    final workedHours = _calculateWorkedTime().inMinutes / 60.0;
    return workedHours * widget.shift.hourlyRate;
  }

  Future<void> _performCheckOut() async {
    if (_currentPosition == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please wait for location to be verified'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    if (_isOnBreak) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please end your break before checking out'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    if (_distanceToVenue != null && _distanceToVenue! > _checkOutRadiusMeters) {
      _showDistanceWarningDialog();
      return;
    }

    // Confirm check-out
    final confirm = await _showCheckOutConfirmation();
    if (confirm != true) return;

    setState(() => _isCheckingOut = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);

      // Prepare timesheet data
      final timesheetData = {
        'shift_id': widget.shift.id,
        'check_in_time': widget.checkInTime.toIso8601String(),
        'check_out_time': DateTime.now().toIso8601String(),
        'breaks': _breaks.map((b) => {
          'start': b['start']!.toIso8601String(),
          'end': b['end']!.toIso8601String(),
        }).toList(),
        'total_worked_minutes': _calculateWorkedTime().inMinutes,
        'total_break_minutes': _calculateTotalBreakTime().inMinutes,
        'notes': _notesController.text.trim(),
        'checkout_latitude': _currentPosition!.latitude,
        'checkout_longitude': _currentPosition!.longitude,
      };

      await api.checkOutFromShift(timesheetData);

      if (!mounted) return;

      // Show success and navigate
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Successfully checked out! Timesheet submitted for approval.'),
          backgroundColor: Colors.green,
        ),
      );

      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;

      setState(() => _isCheckingOut = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Check-out failed: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<bool?> _showCheckOutConfirmation() {
    final workedTime = _calculateWorkedTime();
    final earnings = _calculateEarnings();

    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm Check-Out'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Are you sure you want to check out?'),
            const SizedBox(height: 16),
            Text(
              'Worked Time: ${workedTime.inHours}h ${workedTime.inMinutes % 60}m',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            Text(
              'Estimated Earnings: £${earnings.toStringAsFixed(2)}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'Your timesheet will be submitted to the venue for approval.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirm Check-Out'),
          ),
        ],
      ),
    );
  }

  void _showDistanceWarningDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Too Far From Venue'),
        content: Text(
          'You are ${(_distanceToVenue! / 1000).toStringAsFixed(2)} km from the venue.\n\n'
          'You must be within ${(_checkOutRadiusMeters * 3.28084).toStringAsFixed(0)} feet to check out.\n\n'
          'Please return to the venue to check out.',
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
    final canCheckOut = _currentPosition != null &&
        _distanceToVenue != null &&
        _distanceToVenue! <= _checkOutRadiusMeters &&
        !_isOnBreak;

    final workedTime = _calculateWorkedTime();
    final breakTime = _calculateTotalBreakTime();
    final earnings = _calculateEarnings();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Check Out'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Shift Summary Card
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
                      Icons.login,
                      'Checked In',
                      DateFormat('h:mm a').format(widget.checkInTime),
                    ),
                    _buildInfoRow(
                      Icons.logout,
                      'Current Time',
                      DateFormat('h:mm a').format(DateTime.now()),
                    ),
                    const Divider(height: 24),
                    _buildInfoRow(
                      Icons.timer,
                      'Total Time',
                      '${DateTime.now().difference(widget.checkInTime).inHours}h ${DateTime.now().difference(widget.checkInTime).inMinutes % 60}m',
                    ),
                    _buildInfoRow(
                      Icons.coffee,
                      'Break Time',
                      '${breakTime.inHours}h ${breakTime.inMinutes % 60}m',
                    ),
                    _buildInfoRow(
                      Icons.work,
                      'Worked Time',
                      '${workedTime.inHours}h ${workedTime.inMinutes % 60}m',
                      highlight: true,
                    ),
                    const Divider(height: 24),
                    _buildInfoRow(
                      Icons.attach_money,
                      'Estimated Earnings',
                      '£${earnings.toStringAsFixed(2)}',
                      highlight: true,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Break Management Card
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
                          Icons.coffee,
                          color: Theme.of(context).primaryColor,
                          size: 24,
                        ),
                        const SizedBox(width: 12),
                        const Text(
                          'Break Management',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    if (_isOnBreak) ...[
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.orange.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.orange.withOpacity(0.3)),
                        ),
                        child: Column(
                          children: [
                            const Icon(Icons.pause_circle, color: Colors.orange, size: 48),
                            const SizedBox(height: 12),
                            const Text(
                              'On Break',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: Colors.orange,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Started: ${DateFormat('h:mm a').format(_breakStartTime!)}',
                              style: const TextStyle(fontSize: 14),
                            ),
                            const SizedBox(height: 16),
                            ElevatedButton.icon(
                              onPressed: _endBreak,
                              icon: const Icon(Icons.play_arrow),
                              label: const Text('End Break'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.green,
                                minimumSize: const Size.fromHeight(48),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ] else ...[
                      OutlinedButton.icon(
                        onPressed: _startBreak,
                        icon: const Icon(Icons.coffee),
                        label: const Text('Start Break'),
                        style: OutlinedButton.styleFrom(
                          minimumSize: const Size.fromHeight(48),
                        ),
                      ),
                    ],

                    if (_breaks.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      const Text(
                        'Break History:',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      ..._breaks.asMap().entries.map((entry) {
                        final index = entry.key;
                        final breakPeriod = entry.value;
                        final duration = breakPeriod['end']!.difference(breakPeriod['start']!);
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Text(
                            'Break ${index + 1}: ${DateFormat('h:mm a').format(breakPeriod['start']!)} - ${DateFormat('h:mm a').format(breakPeriod['end']!)} (${duration.inMinutes} min)',
                            style: const TextStyle(fontSize: 12, color: Colors.grey),
                          ),
                        );
                      }),
                    ],
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Notes Section
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
                          Icons.note,
                          color: Theme.of(context).primaryColor,
                          size: 24,
                        ),
                        const SizedBox(width: 12),
                        const Text(
                          'Shift Notes (Optional)',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _notesController,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        hintText: 'Add any notes about this shift...',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'These notes will be included in your timesheet',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
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
                          size: 24,
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
                              onPressed: _getCurrentLocation,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Retry'),
                            ),
                          ],
                        ),
                      ),
                    ] else if (_currentPosition != null && _distanceToVenue != null) ...[
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: (_distanceToVenue! <= _checkOutRadiusMeters)
                              ? Colors.green.withOpacity(0.1)
                              : Colors.orange.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: (_distanceToVenue! <= _checkOutRadiusMeters)
                                ? Colors.green.withOpacity(0.3)
                                : Colors.orange.withOpacity(0.3),
                          ),
                        ),
                        child: Column(
                          children: [
                            Icon(
                              (_distanceToVenue! <= _checkOutRadiusMeters)
                                  ? Icons.check_circle
                                  : Icons.warning,
                              color: (_distanceToVenue! <= _checkOutRadiusMeters)
                                  ? Colors.green
                                  : Colors.orange,
                              size: 48,
                            ),
                            const SizedBox(height: 12),
                            Text(
                              (_distanceToVenue! <= _checkOutRadiusMeters)
                                  ? 'Location Verified'
                                  : 'Too Far From Venue',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: (_distanceToVenue! <= _checkOutRadiusMeters)
                                    ? Colors.green
                                    : Colors.orange,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Distance: ${(_distanceToVenue! / 1000).toStringAsFixed(2)} km',
                              style: const TextStyle(fontSize: 14),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
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

            const SizedBox(height: 32),

            // Check-Out Button
            ElevatedButton.icon(
              onPressed: (_isCheckingOut || !canCheckOut) ? null : _performCheckOut,
              icon: _isCheckingOut
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Icon(Icons.logout),
              label: Text(_isCheckingOut ? 'Checking Out...' : 'Check Out & Submit Timesheet'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                minimumSize: const Size.fromHeight(56),
                backgroundColor: canCheckOut ? null : Colors.grey,
              ),
            ),

            if (_isOnBreak) ...[
              const SizedBox(height: 12),
              const Text(
                'Please end your break before checking out',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: Colors.orange),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value, {bool highlight = false}) {
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
              style: TextStyle(
                fontSize: highlight ? 16 : 14,
                fontWeight: highlight ? FontWeight.bold : FontWeight.w600,
                color: highlight ? Theme.of(context).primaryColor : null,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
