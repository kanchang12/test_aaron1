import 'package:flutter/material.dart';
import 'package:table_calendar/table_calendar.dart';
import 'package:provider/provider.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';

class AvailabilityCalendarScreen extends StatefulWidget {
  const AvailabilityCalendarScreen({super.key});

  @override
  State<AvailabilityCalendarScreen> createState() =>
      _AvailabilityCalendarScreenState();
}

class _AvailabilityCalendarScreenState
    extends State<AvailabilityCalendarScreen> {
  CalendarFormat _calendarFormat = CalendarFormat.month;
  DateTime _focusedDay = DateTime.now();
  DateTime? _selectedDay;
  Map<DateTime, bool> _availability = {};
  List<Shift> _acceptedShifts = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadAvailability();
  }

  Future<void> _loadAvailability() async {
    setState(() => _isLoading = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);

      // Load availability slots
      final availabilityResponse = await api.getAvailability();
      final slots = availabilityResponse
          .map((json) => AvailabilitySlot.fromJson(json))
          .toList();

      // Load accepted shifts (auto-locked times)
      final shiftsResponse = await api.getWorkerApplications();
      final acceptedShifts = shiftsResponse
          .where((app) => app['status'] == 'accepted' || app['status'] == 'hired')
          .map((app) => Shift.fromJson(app['shift']))
          .toList();

      if (mounted) {
        setState(() {
          _availability = {
            for (var slot in slots)
              DateTime.parse(slot.date): slot.isAvailable
          };
          _acceptedShifts = acceptedShifts;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to load availability: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  bool _isDateLocked(DateTime date) {
    return _acceptedShifts.any((shift) {
      final shiftDate = DateTime.parse(shift.startTime);
      return shiftDate.year == date.year &&
          shiftDate.month == date.month &&
          shiftDate.day == date.day;
    });
  }

  Future<void> _toggleAvailability(DateTime date) async {
    // Prevent modifying past dates
    if (date.isBefore(DateTime.now().subtract(const Duration(days: 1)))) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cannot modify past dates'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    // Check if locked by accepted shift
    if (_isDateLocked(date)) {
      _showLockedDateDialog(date);
      return;
    }

    final currentStatus = _availability[date] ?? true;
    final newStatus = !currentStatus;

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final dateString = '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
      await api.setAvailability(dateString, newStatus);

      setState(() {
        _availability[date] = newStatus;
      });

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            newStatus ? 'Marked as available' : 'Marked as unavailable',
          ),
          backgroundColor: Colors.green,
          duration: const Duration(seconds: 1),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to update: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void _showLockedDateDialog(DateTime date) {
    final shift = _acceptedShifts.firstWhere((shift) {
      final shiftDate = DateTime.parse(shift.startTime);
      return shiftDate.year == date.year &&
          shiftDate.month == date.month &&
          shiftDate.day == date.day;
    });

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.lock, color: Colors.orange),
            SizedBox(width: 8),
            Text('Date Locked'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'This date is locked because you have an accepted shift:',
              style: TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.orange.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.orange.withOpacity(0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    shift.role,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    DateTime.parse(shift.startTime).toString().split('.')[0],
                    style: const TextStyle(fontSize: 14),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'To modify this date, you must first cancel the shift.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showRecurringDialog() {
    showDialog(
      context: context,
      builder: (context) => const RecurringAvailabilityDialog(),
    ).then((result) {
      if (result == true) {
        _loadAvailability(); // Refresh after setting recurring
      }
    });
  }

  void _showBulkActionsDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Bulk Actions'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.check_circle, color: Colors.green),
              title: const Text('Mark all as Available'),
              subtitle: const Text('For next 30 days'),
              onTap: () {
                Navigator.pop(context);
                _bulkSetAvailability(true, 30);
              },
            ),
            ListTile(
              leading: const Icon(Icons.cancel, color: Colors.red),
              title: const Text('Mark all as Unavailable'),
              subtitle: const Text('For next 30 days'),
              onTap: () {
                Navigator.pop(context);
                _bulkSetAvailability(false, 30);
              },
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }

  Future<void> _bulkSetAvailability(bool isAvailable, int days) async {
    setState(() => _isLoading = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final startDate = DateTime.now();

      for (int i = 0; i < days; i++) {
        final date = startDate.add(Duration(days: i));
        if (!_isDateLocked(date)) {
          final dateString = '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
          await api.setAvailability(dateString, isAvailable);
          setState(() {
            _availability[date] = isAvailable;
          });
        }
      }

      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Bulk update complete: Marked as ${isAvailable ? 'available' : 'unavailable'}',
            ),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Bulk update failed: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Manage Availability'),
        actions: [
          IconButton(
            icon: const Icon(Icons.repeat),
            onPressed: _showRecurringDialog,
            tooltip: 'Set Recurring Availability',
          ),
          IconButton(
            icon: const Icon(Icons.more_vert),
            onPressed: _showBulkActionsDialog,
            tooltip: 'Bulk Actions',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadAvailability,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  children: [
                    // Calendar
                    Container(
                      margin: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.1),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: TableCalendar(
                        firstDay: DateTime.now(),
                        lastDay: DateTime.now().add(const Duration(days: 365)),
                        focusedDay: _focusedDay,
                        calendarFormat: _calendarFormat,
                        selectedDayPredicate: (day) {
                          return isSameDay(_selectedDay, day);
                        },
                        onDaySelected: (selectedDay, focusedDay) {
                          setState(() {
                            _selectedDay = selectedDay;
                            _focusedDay = focusedDay;
                          });
                          _toggleAvailability(selectedDay);
                        },
                        onFormatChanged: (format) {
                          setState(() {
                            _calendarFormat = format;
                          });
                        },
                        onPageChanged: (focusedDay) {
                          setState(() {
                            _focusedDay = focusedDay;
                          });
                        },
                        calendarStyle: const CalendarStyle(
                          outsideDaysVisible: false,
                        ),
                        calendarBuilders: CalendarBuilders(
                          defaultBuilder: (context, day, focusedDay) {
                            final isLocked = _isDateLocked(day);
                            final isAvailable = _availability[day] ?? true;
                            final isPast = day.isBefore(DateTime.now().subtract(const Duration(days: 1)));

                            return Container(
                              margin: const EdgeInsets.all(4),
                              decoration: BoxDecoration(
                                color: isPast
                                    ? Colors.grey.withOpacity(0.2)
                                    : isLocked
                                        ? Colors.amber.withOpacity(0.3)
                                        : isAvailable
                                            ? Colors.green.withOpacity(0.2)
                                            : Colors.red.withOpacity(0.2),
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: isLocked
                                      ? Colors.amber
                                      : isAvailable
                                          ? Colors.green
                                          : Colors.red,
                                  width: 1,
                                ),
                              ),
                              child: Center(
                                child: Stack(
                                  alignment: Alignment.center,
                                  children: [
                                    Text(
                                      '${day.day}',
                                      style: TextStyle(
                                        color: isPast
                                            ? Colors.grey
                                            : isLocked
                                                ? Colors.amber[900]
                                                : isAvailable
                                                    ? Colors.green[900]
                                                    : Colors.red[900],
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    if (isLocked)
                                      const Positioned(
                                        bottom: 0,
                                        child: Icon(
                                          Icons.lock,
                                          size: 10,
                                          color: Colors.amber,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                    ),

                    // Legend
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: Wrap(
                        spacing: 16,
                        runSpacing: 8,
                        alignment: WrapAlignment.center,
                        children: [
                          _buildLegendItem(Colors.green, 'Available'),
                          _buildLegendItem(Colors.red, 'Unavailable'),
                          _buildLegendItem(Colors.amber, 'Locked (Shift)'),
                        ],
                      ),
                    ),

                    const SizedBox(height: 24),

                    // Instructions
                    Container(
                      margin: const EdgeInsets.symmetric(horizontal: 24),
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
                                'How it works',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.blue,
                                ),
                              ),
                            ],
                          ),
                          SizedBox(height: 8),
                          Text(
                            '• Tap any date to toggle availability\n'
                            '• Green = Available for shifts\n'
                            '• Red = Unavailable (blocked)\n'
                            '• Amber/Locked = You have an accepted shift\n'
                            '• Use 🔁 for recurring patterns\n'
                            '• Use ⋮ for bulk actions\n'
                            '• Accepted shifts auto-lock dates',
                            style: TextStyle(fontSize: 14, height: 1.5),
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 32),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildLegendItem(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 16,
          height: 16,
          decoration: BoxDecoration(
            color: color.withOpacity(0.3),
            shape: BoxShape.circle,
            border: Border.all(color: color, width: 1),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: const TextStyle(fontSize: 13),
        ),
      ],
    );
  }
}

// Recurring Availability Dialog
class RecurringAvailabilityDialog extends StatefulWidget {
  const RecurringAvailabilityDialog({super.key});

  @override
  State<RecurringAvailabilityDialog> createState() =>
      _RecurringAvailabilityDialogState();
}

class _RecurringAvailabilityDialogState
    extends State<RecurringAvailabilityDialog> {
  final Map<int, bool> _weekdayAvailability = {
    1: true, // Monday
    2: true, // Tuesday
    3: true, // Wednesday
    4: true, // Thursday
    5: true, // Friday
    6: true, // Saturday
    7: true, // Sunday
  };

  bool _isLoading = false;

  final Map<int, String> _weekdayNames = {
    1: 'Monday',
    2: 'Tuesday',
    3: 'Wednesday',
    4: 'Thursday',
    5: 'Friday',
    6: 'Saturday',
    7: 'Sunday',
  };

  Future<void> _saveRecurringPattern() async {
    setState(() => _isLoading = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final startDate = DateTime.now();

      // Apply pattern for next 90 days
      for (int i = 0; i < 90; i++) {
        final date = startDate.add(Duration(days: i));
        final weekday = date.weekday;
        final isAvailable = _weekdayAvailability[weekday] ?? true;

        final dateString = '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
        await api.setAvailability(dateString, isAvailable);
      }

      if (!mounted) return;

      Navigator.of(context).pop(true);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Recurring availability pattern saved for next 90 days!'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (e) {
      if (!mounted) return;

      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to save pattern: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Set Recurring Availability'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Select which days of the week you\'re typically available:',
              style: TextStyle(fontSize: 14, color: Colors.grey),
            ),
            const SizedBox(height: 16),
            ..._weekdayAvailability.entries.map((entry) {
              return CheckboxListTile(
                title: Text(_weekdayNames[entry.key]!),
                value: entry.value,
                onChanged: _isLoading
                    ? null
                    : (value) {
                        setState(() {
                          _weekdayAvailability[entry.key] = value ?? true;
                        });
                      },
                activeColor: Theme.of(context).primaryColor,
              );
            }).toList(),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(
                children: [
                  Icon(Icons.info_outline, size: 16, color: Colors.blue),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'This pattern will be applied to the next 90 days',
                      style: TextStyle(fontSize: 12, color: Colors.blue),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _isLoading ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _isLoading ? null : _saveRecurringPattern,
          child: _isLoading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Apply Pattern'),
        ),
      ],
    );
  }
}
