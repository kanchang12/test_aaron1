import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';
import '../auth/login_screen.dart';

class WorkerHomeScreen extends StatefulWidget {
  const WorkerHomeScreen({super.key});

  @override
  State<WorkerHomeScreen> createState() => _WorkerHomeScreenState();
}

class _WorkerHomeScreenState extends State<WorkerHomeScreen> {
  int _selectedIndex = 0;

  final List<Widget> _screens = [
    const ShiftSearchScreen(),
    const MyApplicationsScreen(),
    const WorkerProfileScreen(),
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
            icon: Icon(Icons.search),
            label: 'Find Shifts',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.assignment),
            label: 'Applications',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
      ),
    );
  }
}

// Shift Search Screen
class ShiftSearchScreen extends StatefulWidget {
  const ShiftSearchScreen({super.key});

  @override
  State<ShiftSearchScreen> createState() => _ShiftSearchScreenState();
}

class _ShiftSearchScreenState extends State<ShiftSearchScreen> {
  List<Shift> _shifts = [];
  bool _isLoading = true;
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _loadShifts();
  }

  Future<void> _loadShifts() async {
    setState(() => _isLoading = true);
    
    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final data = await api.searchShifts();
      
      setState(() {
        _shifts = data.map((json) => Shift.fromJson(json)).toList();
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
      appBar: AppBar(
        title: const Text('Find Shifts'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadShifts,
          ),
        ],
      ),
      body: Column(
        children: [
          // Search bar
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Search shifts...',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              onChanged: (value) {
                setState(() => _searchQuery = value.toLowerCase());
              },
            ),
          ),
          
          // Shifts list
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _shifts.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.work_off, size: 64, color: Colors.grey[400]),
                            const SizedBox(height: 16),
                            Text(
                              'No shifts available',
                              style: TextStyle(fontSize: 18, color: Colors.grey[600]),
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
                            
                            if (_searchQuery.isNotEmpty &&
                                !shift.role.toLowerCase().contains(_searchQuery) &&
                                !(shift.location ?? '').toLowerCase().contains(_searchQuery)) {
                              return const SizedBox.shrink();
                            }
                            
                            return ShiftCard(
                              shift: shift,
                              onTap: () => _showShiftDetails(shift),
                            );
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  void _showShiftDetails(Shift shift) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => ShiftDetailsSheet(shift: shift),
    );
  }
}

// Shift Card Widget
class ShiftCard extends StatelessWidget {
  final Shift shift;
  final VoidCallback onTap;

  const ShiftCard({super.key, required this.shift, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final startTime = DateTime.parse(shift.startTime);
    final endTime = DateTime.parse(shift.endTime);
    
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
                  if (shift.isBoosted)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.orange,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'URGENT',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.calendar_today, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(
                    DateFormat('MMM dd, yyyy').format(startTime),
                    style: TextStyle(color: Colors.grey[600]),
                  ),
                  const SizedBox(width: 16),
                  Icon(Icons.access_time, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(
                    '${DateFormat.jm().format(startTime)} - ${DateFormat.jm().format(endTime)}',
                    style: TextStyle(color: Colors.grey[600]),
                  ),
                ],
              ),
              if (shift.location != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.location_on, size: 16, color: Colors.grey[600]),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        shift.location!,
                        style: TextStyle(color: Colors.grey[600]),
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '£${shift.hourlyRate.toStringAsFixed(2)}/hour',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).primaryColor,
                      ),
                    ),
                  ),
                  Text(
                    '${shift.numWorkersHired}/${shift.numWorkersNeeded} filled',
                    style: TextStyle(color: Colors.grey[600]),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Shift Details Bottom Sheet
class ShiftDetailsSheet extends StatefulWidget {
  final Shift shift;

  const ShiftDetailsSheet({super.key, required this.shift});

  @override
  State<ShiftDetailsSheet> createState() => _ShiftDetailsSheetState();
}

class _ShiftDetailsSheetState extends State<ShiftDetailsSheet> {
  bool _showCounterOffer = false;
  final _counterRateController = TextEditingController();
  bool _isApplying = false;

  @override
  void dispose() {
    _counterRateController.dispose();
    super.dispose();
  }

  Future<void> _apply({double? counterRate}) async {
    setState(() => _isApplying = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      await api.applyToShift(
        shiftId: widget.shift.id,
        counterRate: counterRate,
      );

      if (!mounted) return;

      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Application submitted!'),
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
        setState(() => _isApplying = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.75,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                widget.shift.role,
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              
              if (widget.shift.description != null) ...[
                Text(widget.shift.description!),
                const SizedBox(height: 16),
              ],
              
              InfoRow(
                icon: Icons.attach_money,
                label: 'Rate',
                value: '£${widget.shift.hourlyRate.toStringAsFixed(2)}/hour',
              ),
              InfoRow(
                icon: Icons.people,
                label: 'Workers',
                value: '${widget.shift.numWorkersNeeded - widget.shift.numWorkersHired} positions available',
              ),
              
              const SizedBox(height: 24),
              
              if (!_showCounterOffer)
                ElevatedButton(
                  onPressed: _isApplying ? null : () => _apply(),
                  child: _isApplying
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Apply Now'),
                ),
              
              const SizedBox(height: 8),
              
              OutlinedButton(
                onPressed: () {
                  setState(() => _showCounterOffer = !_showCounterOffer);
                },
                child: Text(_showCounterOffer ? 'Cancel Counter Offer' : 'Make Counter Offer'),
              ),
              
              if (_showCounterOffer) ...[
                const SizedBox(height: 16),
                TextField(
                  controller: _counterRateController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Your desired rate (£/hour)',
                    prefixText: '£',
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _isApplying
                      ? null
                      : () {
                          final rate = double.tryParse(_counterRateController.text);
                          if (rate != null && rate > 0) {
                            _apply(counterRate: rate);
                          }
                        },
                  child: const Text('Submit Counter Offer'),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const InfoRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 20, color: Colors.grey[600]),
          const SizedBox(width: 12),
          Text(
            label,
            style: TextStyle(color: Colors.grey[600]),
          ),
          const Spacer(),
          Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

// Placeholder screens
class MyApplicationsScreen extends StatelessWidget {
  const MyApplicationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Applications')),
      body: const Center(child: Text('Applications screen - Coming soon')),
    );
  }
}

class WorkerProfileScreen extends StatelessWidget {
  const WorkerProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: Center(
        child: ElevatedButton(
          onPressed: () async {
            final api = Provider.of<ApiService>(context, listen: false);
            await api.clearToken();
            if (context.mounted) {
              Navigator.of(context).pushAndRemoveUntil(
                MaterialPageRoute(builder: (_) => const LoginScreen()),
                (route) => false,
              );
            }
          },
          child: const Text('Logout'),
        ),
      ),
    );
  }
}
