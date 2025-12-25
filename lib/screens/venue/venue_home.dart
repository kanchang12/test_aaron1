import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';
import '../auth/login_screen.dart';
import 'edit_venue_profile_screen.dart';

class VenueHomeScreen extends StatefulWidget {
  const VenueHomeScreen({super.key});

  @override
  State<VenueHomeScreen> createState() => _VenueHomeScreenState();
}

class _VenueHomeScreenState extends State<VenueHomeScreen> {
  int _selectedIndex = 0;

  final List<Widget> _screens = [
    const VenueShiftsScreen(),
    const VenueProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) => setState(() => _selectedIndex = index),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.work),
            label: 'My Shifts',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.business),
            label: 'Venue',
          ),
        ],
      ),
      floatingActionButton: _selectedIndex == 0
          ? FloatingActionButton.extended(
              onPressed: () => _showCreateShift(context),
              icon: const Icon(Icons.add),
              label: const Text('Post Shift'),
            )
          : null,
    );
  }

  void _showCreateShift(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => const CreateShiftSheet(),
    );
  }
}

// Venue Shifts Screen
class VenueShiftsScreen extends StatefulWidget {
  const VenueShiftsScreen({super.key});

  @override
  State<VenueShiftsScreen> createState() => _VenueShiftsScreenState();
}

class _VenueShiftsScreenState extends State<VenueShiftsScreen> {
  List<Shift> _shifts = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadShifts();
  }

  Future<void> _loadShifts() async {
    setState(() => _isLoading = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final data = await api.getVenueShifts();

      if (mounted) {
        setState(() {
          _shifts = data.map((json) => Shift.fromJson(json)).toList();
          _isLoading = false;
        });
      }
    } catch (e) {
      print('Error loading shifts: $e');
      if (mounted) {
        setState(() {
          _isLoading = false;
          _shifts = []; // Set empty list on error
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Cannot connect to server. Deploy backend first.'),
            backgroundColor: Colors.orange,
            duration: Duration(seconds: 5),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Shifts'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadShifts,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _shifts.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.work_off, size: 64, color: Colors.grey[400]),
                      const SizedBox(height: 16),
                      Text(
                        'No shifts posted yet',
                        style: TextStyle(fontSize: 18, color: Colors.grey[600]),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Tap the + button to create your first shift',
                        style: TextStyle(color: Colors.grey[500]),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadShifts,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _shifts.length,
                    itemBuilder: (context, index) {
                      final shift = _shifts[index];
                      return VenueShiftCard(
                        shift: shift,
                        onTap: () => _viewShiftDetails(shift),
                        onRefresh: _loadShifts,
                      );
                    },
                  ),
                ),
    );
  }

  void _viewShiftDetails(Shift shift) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ShiftApplicationsScreen(shift: shift),
      ),
    ).then((_) => _loadShifts());
  }
}

// Venue Shift Card
class VenueShiftCard extends StatelessWidget {
  final Shift shift;
  final VoidCallback onTap;
  final VoidCallback onRefresh;

  const VenueShiftCard({
    super.key,
    required this.shift,
    required this.onTap,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    final startTime = DateTime.parse(shift.startTime);
    
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      shift.role,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  _StatusChip(status: shift.status),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                DateFormat('MMM dd, yyyy - hh:mm a').format(startTime),
                style: TextStyle(color: Colors.grey[600]),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(Icons.people, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(
                    '${shift.numWorkersHired}/${shift.numWorkersNeeded} hired',
                    style: TextStyle(color: Colors.grey[600]),
                  ),
                  const Spacer(),
                  Text(
                    '£${shift.hourlyRate.toStringAsFixed(2)}/hr',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                ],
              ),
              if (shift.status == 'draft') ...[
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () async {
                      try {
                        final api = Provider.of<ApiService>(context, listen: false);
                        await api.publishShift(shift.id);
                        onRefresh();
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Shift published!'),
                              backgroundColor: Colors.green,
                            ),
                          );
                        }
                      } catch (e) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Error: ${e.toString()}')),
                          );
                        }
                      }
                    },
                    child: const Text('Publish Shift'),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  final String status;

  const _StatusChip({required this.status});

  @override
  Widget build(BuildContext context) {
    Color color;
    String label;

    switch (status) {
      case 'draft':
        color = Colors.grey;
        label = 'DRAFT';
        break;
      case 'live':
        color = Colors.blue;
        label = 'LIVE';
        break;
      case 'filled':
        color = Colors.green;
        label = 'FILLED';
        break;
      case 'in_progress':
        color = Colors.orange;
        label = 'IN PROGRESS';
        break;
      case 'completed':
        color = Colors.teal;
        label = 'COMPLETED';
        break;
      default:
        color = Colors.grey;
        label = status.toUpperCase();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}

// Create Shift Sheet
class CreateShiftSheet extends StatefulWidget {
  const CreateShiftSheet({super.key});

  @override
  State<CreateShiftSheet> createState() => _CreateShiftSheetState();
}

class _CreateShiftSheetState extends State<CreateShiftSheet> {
  final _formKey = GlobalKey<FormState>();
  final _roleController = TextEditingController();
  final _hourlyRateController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _numWorkersController = TextEditingController(text: '1');
  
  DateTime _startDate = DateTime.now();
  TimeOfDay _startTime = TimeOfDay.now();
  TimeOfDay _endTime = TimeOfDay(hour: TimeOfDay.now().hour + 4, minute: 0);
  
  bool _isCreating = false;

  @override
  void dispose() {
    _roleController.dispose();
    _hourlyRateController.dispose();
    _descriptionController.dispose();
    _numWorkersController.dispose();
    super.dispose();
  }

  Future<void> _createShift() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isCreating = true);

    try {
      final startDateTime = DateTime(
        _startDate.year,
        _startDate.month,
        _startDate.day,
        _startTime.hour,
        _startTime.minute,
      );

      final endDateTime = DateTime(
        _startDate.year,
        _startDate.month,
        _startDate.day,
        _endTime.hour,
        _endTime.minute,
      );

      final api = Provider.of<ApiService>(context, listen: false);
      await api.createShift(
        role: _roleController.text.trim(),
        startTime: startDateTime.toIso8601String(),
        endTime: endDateTime.toIso8601String(),
        hourlyRate: double.parse(_hourlyRateController.text),
        description: _descriptionController.text.trim(),
        numWorkersNeeded: int.parse(_numWorkersController.text),
      );

      if (!mounted) return;

      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Shift created! Publish it to make it visible to workers.'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e.toString().replaceAll('Exception: ', '')),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isCreating = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.9,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return Padding(
          padding: EdgeInsets.only(
            left: 24,
            right: 24,
            top: 24,
            bottom: MediaQuery.of(context).viewInsets.bottom + 24,
          ),
          child: Form(
            key: _formKey,
            child: ListView(
              controller: scrollController,
              children: [
                const Text(
                  'Create New Shift',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 24),
                
                TextFormField(
                  controller: _roleController,
                  decoration: const InputDecoration(
                    labelText: 'Role/Position *',
                    hintText: 'e.g., Bartender, Server, Chef',
                  ),
                  validator: (v) => v?.isEmpty == true ? 'Required' : null,
                ),
                const SizedBox(height: 16),
                
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _hourlyRateController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Hourly Rate (£) *',
                          prefixText: '£',
                        ),
                        validator: (v) => v?.isEmpty == true ? 'Required' : null,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: TextFormField(
                        controller: _numWorkersController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Workers Needed *',
                        ),
                        validator: (v) => v?.isEmpty == true ? 'Required' : null,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                
                ListTile(
                  title: const Text('Shift Date'),
                  subtitle: Text(DateFormat('MMM dd, yyyy').format(_startDate)),
                  trailing: const Icon(Icons.calendar_today),
                  onTap: () async {
                    final date = await showDatePicker(
                      context: context,
                      initialDate: _startDate,
                      firstDate: DateTime.now(),
                      lastDate: DateTime.now().add(const Duration(days: 365)),
                    );
                    if (date != null) {
                      setState(() => _startDate = date);
                    }
                  },
                ),
                
                ListTile(
                  title: const Text('Start Time'),
                  subtitle: Text(_startTime.format(context)),
                  trailing: const Icon(Icons.access_time),
                  onTap: () async {
                    final time = await showTimePicker(
                      context: context,
                      initialTime: _startTime,
                    );
                    if (time != null) {
                      setState(() => _startTime = time);
                    }
                  },
                ),
                
                ListTile(
                  title: const Text('End Time'),
                  subtitle: Text(_endTime.format(context)),
                  trailing: const Icon(Icons.access_time),
                  onTap: () async {
                    final time = await showTimePicker(
                      context: context,
                      initialTime: _endTime,
                    );
                    if (time != null) {
                      setState(() => _endTime = time);
                    }
                  },
                ),
                const SizedBox(height: 16),
                
                TextFormField(
                  controller: _descriptionController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Description (optional)',
                    hintText: 'Additional details about the shift...',
                  ),
                ),
                const SizedBox(height: 24),
                
                ElevatedButton(
                  onPressed: _isCreating ? null : _createShift,
                  child: _isCreating
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Create Shift'),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// Shift Applications Screen
class ShiftApplicationsScreen extends StatefulWidget {
  final Shift shift;

  const ShiftApplicationsScreen({super.key, required this.shift});

  @override
  State<ShiftApplicationsScreen> createState() => _ShiftApplicationsScreenState();
}

class _ShiftApplicationsScreenState extends State<ShiftApplicationsScreen> {
  List<Application> _applications = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadApplications();
  }

  Future<void> _loadApplications() async {
    setState(() => _isLoading = true);
    
    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final data = await api.getShiftApplications(widget.shift.id);
      
      setState(() {
        _applications = data.map((json) => Application.fromJson(json)).toList();
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Applications')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _applications.isEmpty
              ? const Center(child: Text('No applications yet'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _applications.length,
                  itemBuilder: (context, index) {
                    final app = _applications[index];
                    return Card(
                      child: ListTile(
                        title: Text('Application #${app.id}'),
                        subtitle: Text('Status: ${app.status}'),
                        trailing: app.status == 'applied'
                            ? ElevatedButton(
                                onPressed: () => _hireWorker(app.id),
                                child: const Text('Hire'),
                              )
                            : null,
                      ),
                    );
                  },
                ),
    );
  }

  Future<void> _hireWorker(int appId) async {
    try {
      final api = Provider.of<ApiService>(context, listen: false);
      await api.hireWorker(appId);
      
      _loadApplications();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Worker hired!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}')),
        );
      }
    }
  }
}

// Venue Profile Screen
class VenueProfileScreen extends StatelessWidget {
  const VenueProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Venue Management')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          // Profile Section
          Card(
            child: ListTile(
              leading: const Icon(Icons.business),
              title: const Text('Edit Venue Profile'),
              subtitle: const Text('Update venue name, address, contact info'),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => const EditVenueProfileScreen(),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          // Payment Setup
          Card(
            child: ListTile(
              leading: const Icon(Icons.payment),
              title: const Text('Payment Method Setup'),
              subtitle: const Text('Add or update Stripe/bank details'),
              onTap: () {
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Payment Method Setup'),
                    content: const Text('This feature is coming soon!'),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('OK'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          // Team Management
          Card(
            child: ListTile(
              leading: const Icon(Icons.group),
              title: const Text('Manage Team'),
              subtitle: const Text('Invite, edit, or remove team members'),
              onTap: () {
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Manage Team'),
                    content: const Text('This feature is coming soon!'),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('OK'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          // Shift Analytics
          Card(
            child: ListTile(
              leading: const Icon(Icons.analytics),
              title: const Text('Shift Analytics & Reports'),
              subtitle: const Text('View shift history, fill rates, spend, and more'),
              onTap: () {
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Shift Analytics & Reports'),
                    content: const Text('This feature is coming soon!'),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('OK'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          // Ratings & Reviews
          Card(
            child: ListTile(
              leading: const Icon(Icons.star),
              title: const Text('Ratings & Reviews'),
              subtitle: const Text('See feedback from workers and venues'),
              onTap: () {
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Ratings & Reviews'),
                    content: const Text('This feature is coming soon!'),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('OK'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          // Logout
          Card(
            child: ListTile(
              leading: const Icon(Icons.logout),
              title: const Text('Logout'),
              onTap: () async {
                final api = Provider.of<ApiService>(context, listen: false);
                await api.clearToken();
                if (context.mounted) {
                  Navigator.of(context).pushAndRemoveUntil(
                    MaterialPageRoute(builder: (_) => const LoginScreen()),
                    (route) => false,
                  );
                }
              },
            ),
          ),
        ],
      ),
    );
  }
}
