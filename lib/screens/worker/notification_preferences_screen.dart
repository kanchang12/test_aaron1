import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../services/api_service.dart';

class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  State<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends State<NotificationPreferencesScreen> {
  bool _isLoading = true;
  bool _isSaving = false;

  // Notification Channels
  bool _pushEnabled = true;
  bool _emailEnabled = false;
  bool _smsEnabled = false;

  // Criteria-based Filters
  List<String> _selectedRoles = [];
  double _minRate = 0.0;
  double _maxDistance = 50.0; // miles

  final List<String> _availableRoles = [
    'Bartender',
    'Server',
    'Chef',
    'Kitchen Staff',
    'Host/Hostess',
    'Dishwasher',
    'Barista',
    'Cook',
    'Manager',
  ];

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    setState(() => _isLoading = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final prefs = await api.getNotificationPreferences();

      if (mounted) {
        setState(() {
          _pushEnabled = prefs['push_enabled'] ?? true;
          _emailEnabled = prefs['email_enabled'] ?? false;
          _smsEnabled = prefs['sms_enabled'] ?? false;
          _selectedRoles = List<String>.from(prefs['filter_roles'] ?? []);
          _minRate = prefs['min_rate']?.toDouble() ?? 0.0;
          _maxDistance = prefs['max_distance']?.toDouble() ?? 50.0;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to load preferences: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _savePreferences() async {
    setState(() => _isSaving = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      await api.updateNotificationPreferences({
        'push_enabled': _pushEnabled,
        'email_enabled': _emailEnabled,
        'sms_enabled': _smsEnabled,
        'filter_roles': _selectedRoles,
        'min_rate': _minRate,
        'max_distance': _maxDistance,
      });

      if (!mounted) return;

      setState(() => _isSaving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Preferences saved successfully!'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (e) {
      if (!mounted) return;

      setState(() => _isSaving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to save: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notification Preferences'),
        actions: [
          if (_isSaving)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header
                  const Text(
                    'Customize Your Notifications',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Control when and how you receive shift notifications',
                    style: TextStyle(fontSize: 16, color: Colors.grey),
                  ),
                  const SizedBox(height: 32),

                  // Notification Channels Section
                  _buildSectionHeader('Notification Channels'),
                  const SizedBox(height: 16),

                  Card(
                    elevation: 2,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      children: [
                        SwitchListTile(
                          title: const Text('Push Notifications'),
                          subtitle: const Text('Get instant alerts on your device'),
                          secondary: const Icon(Icons.notifications_active),
                          value: _pushEnabled,
                          onChanged: (value) {
                            setState(() => _pushEnabled = value);
                          },
                        ),
                        const Divider(height: 1),
                        SwitchListTile(
                          title: const Text('Email Notifications'),
                          subtitle: const Text('Receive alerts via email'),
                          secondary: const Icon(Icons.email),
                          value: _emailEnabled,
                          onChanged: (value) {
                            setState(() => _emailEnabled = value);
                          },
                        ),
                        const Divider(height: 1),
                        SwitchListTile(
                          title: const Text('SMS Notifications'),
                          subtitle: const Text('Get text messages for urgent shifts'),
                          secondary: const Icon(Icons.sms),
                          value: _smsEnabled,
                          onChanged: (value) {
                            setState(() => _smsEnabled = value);
                          },
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 32),

                  // Criteria-Based Filters Section
                  _buildSectionHeader('Smart Filters'),
                  const SizedBox(height: 8),
                  const Text(
                    'Only get notified for shifts that match your criteria',
                    style: TextStyle(fontSize: 14, color: Colors.grey),
                  ),
                  const SizedBox(height: 16),

                  // Role Filter
                  Card(
                    elevation: 2,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.work_outline,
                                color: Theme.of(context).primaryColor,
                              ),
                              const SizedBox(width: 12),
                              const Text(
                                'Preferred Roles',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'Select the types of shifts you want to be notified about',
                            style: TextStyle(fontSize: 12, color: Colors.grey),
                          ),
                          const SizedBox(height: 16),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: _availableRoles.map((role) {
                              final isSelected = _selectedRoles.contains(role);
                              return FilterChip(
                                label: Text(role),
                                selected: isSelected,
                                onSelected: (selected) {
                                  setState(() {
                                    if (selected) {
                                      _selectedRoles.add(role);
                                    } else {
                                      _selectedRoles.remove(role);
                                    }
                                  });
                                },
                                selectedColor:
                                    Theme.of(context).primaryColor.withOpacity(0.3),
                              );
                            }).toList(),
                          ),
                          if (_selectedRoles.isEmpty) ...[
                            const SizedBox(height: 12),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: Colors.orange.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Row(
                                children: [
                                  Icon(Icons.info_outline,
                                      color: Colors.orange, size: 16),
                                  SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      'No roles selected = All roles',
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: Colors.orange,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Minimum Rate Filter
                  Card(
                    elevation: 2,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.attach_money,
                                color: Theme.of(context).primaryColor,
                              ),
                              const SizedBox(width: 12),
                              const Text(
                                'Minimum Hourly Rate',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Only notify for shifts paying £${_minRate.toStringAsFixed(0)}/hour or more',
                            style: const TextStyle(fontSize: 12, color: Colors.grey),
                          ),
                          const SizedBox(height: 16),
                          Row(
                            children: [
                              const Text('£0', style: TextStyle(fontSize: 12)),
                              Expanded(
                                child: Slider(
                                  value: _minRate,
                                  min: 0,
                                  max: 50,
                                  divisions: 50,
                                  label: '£${_minRate.toStringAsFixed(0)}',
                                  onChanged: (value) {
                                    setState(() => _minRate = value);
                                  },
                                ),
                              ),
                              const Text('£50', style: TextStyle(fontSize: 12)),
                            ],
                          ),
                          Center(
                            child: Text(
                              '£${_minRate.toStringAsFixed(0)}/hour',
                              style: TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.bold,
                                color: Theme.of(context).primaryColor,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Distance Filter
                  Card(
                    elevation: 2,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.location_on,
                                color: Theme.of(context).primaryColor,
                              ),
                              const SizedBox(width: 12),
                              const Text(
                                'Maximum Distance',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Only notify for shifts within ${_maxDistance.toStringAsFixed(0)} miles',
                            style: const TextStyle(fontSize: 12, color: Colors.grey),
                          ),
                          const SizedBox(height: 16),
                          Row(
                            children: [
                              const Text('5mi', style: TextStyle(fontSize: 12)),
                              Expanded(
                                child: Slider(
                                  value: _maxDistance,
                                  min: 5,
                                  max: 100,
                                  divisions: 19,
                                  label: '${_maxDistance.toStringAsFixed(0)} mi',
                                  onChanged: (value) {
                                    setState(() => _maxDistance = value);
                                  },
                                ),
                              ),
                              const Text('100mi', style: TextStyle(fontSize: 12)),
                            ],
                          ),
                          Center(
                            child: Text(
                              '${_maxDistance.toStringAsFixed(0)} miles',
                              style: TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.bold,
                                color: Theme.of(context).primaryColor,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 32),

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
                            Icon(Icons.lightbulb_outline,
                                color: Colors.blue, size: 20),
                            SizedBox(width: 8),
                            Text(
                              'Pro Tips',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Colors.blue,
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 8),
                        Text(
                          '• Enable push for instant notifications\n'
                          '• Set specific roles to reduce noise\n'
                          '• Adjust min rate to match your expectations\n'
                          '• Distance filter uses your profile address\n'
                          '• You can always view all shifts manually',
                          style: TextStyle(fontSize: 14, height: 1.5),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 32),

                  // Save Button
                  ElevatedButton(
                    onPressed: _isSaving ? null : _savePreferences,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      minimumSize: const Size.fromHeight(50),
                    ),
                    child: _isSaving
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                            ),
                          )
                        : const Text(
                            'Save Preferences',
                            style: TextStyle(fontSize: 16),
                          ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 20,
        fontWeight: FontWeight.bold,
      ),
    );
  }
}
