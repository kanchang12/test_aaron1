import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';

class MyApplicationsScreen extends StatefulWidget {
  const MyApplicationsScreen({super.key});

  @override
  State<MyApplicationsScreen> createState() => _MyApplicationsScreenState();
}

class _MyApplicationsScreenState extends State<MyApplicationsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<Map<String, dynamic>> _applications = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadApplications();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadApplications() async {
    setState(() => _isLoading = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final data = await api.getWorkerApplications();

      if (mounted) {
        setState(() {
          _applications = data;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to load applications: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  List<Map<String, dynamic>> _filterApplications(String status) {
    if (status == 'all') return _applications;
    return _applications.where((app) => app['status'] == status).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Applications'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: [
            Tab(
              child: Row(
                children: [
                  const Text('All'),
                  const SizedBox(width: 8),
                  _buildBadge(_applications.length),
                ],
              ),
            ),
            Tab(
              child: Row(
                children: [
                  const Text('Pending'),
                  const SizedBox(width: 8),
                  _buildBadge(_filterApplications('pending').length),
                ],
              ),
            ),
            Tab(
              child: Row(
                children: [
                  const Text('Accepted'),
                  const SizedBox(width: 8),
                  _buildBadge(_filterApplications('accepted').length),
                ],
              ),
            ),
            Tab(
              child: Row(
                children: [
                  const Text('Rejected'),
                  const SizedBox(width: 8),
                  _buildBadge(_filterApplications('rejected').length),
                ],
              ),
            ),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadApplications,
              child: TabBarView(
                controller: _tabController,
                children: [
                  _buildApplicationsList('all'),
                  _buildApplicationsList('pending'),
                  _buildApplicationsList('accepted'),
                  _buildApplicationsList('rejected'),
                ],
              ),
            ),
    );
  }

  Widget _buildBadge(int count) {
    if (count == 0) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: Theme.of(context).primaryColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        count.toString(),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildApplicationsList(String status) {
    final applications = _filterApplications(status);

    if (applications.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.inbox_outlined,
              size: 64,
              color: Colors.grey[400],
            ),
            const SizedBox(height: 16),
            Text(
              'No ${status == 'all' ? '' : status} applications',
              style: TextStyle(
                fontSize: 18,
                color: Colors.grey[600],
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Start applying to shifts to see them here',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[500],
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: applications.length,
      itemBuilder: (context, index) {
        final application = applications[index];
        return ApplicationCard(
          application: application,
          onTap: () => _showApplicationDetails(application),
        );
      },
    );
  }

  void _showApplicationDetails(Map<String, dynamic> application) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => ApplicationDetailsSheet(
        application: application,
        onUpdate: _loadApplications,
      ),
    );
  }
}

class ApplicationCard extends StatelessWidget {
  final Map<String, dynamic> application;
  final VoidCallback onTap;

  const ApplicationCard({
    super.key,
    required this.application,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final shift = Shift.fromJson(application['shift']);
    final status = application['status'] as String;
    final appliedAt = DateTime.parse(application['created_at']);
    final counterRate = application['counter_rate'];
    final isCounterOffer = counterRate != null;

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
              // Header
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
                  _buildStatusBadge(status),
                ],
              ),
              const SizedBox(height: 12),

              // Shift Details
              Row(
                children: [
                  Icon(Icons.calendar_today, size: 14, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(
                    DateFormat('MMM dd, yyyy')
                        .format(DateTime.parse(shift.startTime)),
                    style: const TextStyle(fontSize: 13),
                  ),
                  const SizedBox(width: 16),
                  Icon(Icons.access_time, size: 14, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(
                    '${DateFormat.jm().format(DateTime.parse(shift.startTime))} - ${DateFormat.jm().format(DateTime.parse(shift.endTime))}',
                    style: const TextStyle(fontSize: 13),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              // Rate Info
              Row(
                children: [
                  Icon(Icons.attach_money, size: 14, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  if (isCounterOffer) ...[
                    Text(
                      '£${shift.hourlyRate.toStringAsFixed(0)}/hr',
                      style: const TextStyle(
                        fontSize: 13,
                        decoration: TextDecoration.lineThrough,
                        color: Colors.grey,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Icon(Icons.arrow_forward, size: 12, color: Colors.grey[600]),
                    const SizedBox(width: 8),
                    Text(
                      '£${counterRate.toStringAsFixed(0)}/hr (Your offer)',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).primaryColor,
                      ),
                    ),
                  ] else ...[
                    Text(
                      '£${shift.hourlyRate.toStringAsFixed(0)}/hr',
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 12),

              // Applied Date
              Row(
                children: [
                  Icon(Icons.history, size: 14, color: Colors.grey[500]),
                  const SizedBox(width: 4),
                  Text(
                    'Applied ${_formatRelativeTime(appliedAt)}',
                    style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                  ),
                ],
              ),

              // Counter Offer Expiry Warning
              if (isCounterOffer && status == 'pending') ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.orange.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.orange.withOpacity(0.3)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.info_outline,
                          size: 16, color: Colors.orange),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Counter offer expires in 2 hours if not accepted',
                          style: const TextStyle(
                            fontSize: 11,
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
    );
  }

  Widget _buildStatusBadge(String status) {
    Color color;
    IconData icon;
    String label;

    switch (status) {
      case 'pending':
        color = Colors.orange;
        icon = Icons.pending;
        label = 'Pending';
        break;
      case 'accepted':
      case 'hired':
        color = Colors.green;
        icon = Icons.check_circle;
        label = 'Accepted';
        break;
      case 'rejected':
        color = Colors.red;
        icon = Icons.cancel;
        label = 'Rejected';
        break;
      case 'counter_pending':
        color = Colors.blue;
        icon = Icons.sync;
        label = 'Counter Offer';
        break;
      default:
        color = Colors.grey;
        icon = Icons.help_outline;
        label = status;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  String _formatRelativeTime(DateTime dateTime) {
    final now = DateTime.now();
    final difference = now.difference(dateTime);

    if (difference.inMinutes < 1) {
      return 'just now';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes}m ago';
    } else if (difference.inHours < 24) {
      return '${difference.inHours}h ago';
    } else if (difference.inDays == 1) {
      return 'yesterday';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}d ago';
    } else {
      return DateFormat('MMM dd').format(dateTime);
    }
  }
}

class ApplicationDetailsSheet extends StatelessWidget {
  final Map<String, dynamic> application;
  final VoidCallback onUpdate;

  const ApplicationDetailsSheet({
    super.key,
    required this.application,
    required this.onUpdate,
  });

  @override
  Widget build(BuildContext context) {
    final shift = Shift.fromJson(application['shift']);
    final status = application['status'] as String;

    return DraggableScrollableSheet(
      initialChildSize: 0.7,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return SingleChildScrollView(
          controller: scrollController,
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Title and Status
              Row(
                children: [
                  Expanded(
                    child: Text(
                      shift.role,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  ApplicationCard(
                    application: application,
                    onTap: () {},
                  )._buildStatusBadge(status),
                ],
              ),
              const SizedBox(height: 24),

              // Shift Details
              _buildDetailRow(
                Icons.calendar_today,
                'Date',
                DateFormat('EEEE, MMMM dd, yyyy')
                    .format(DateTime.parse(shift.startTime)),
              ),
              _buildDetailRow(
                Icons.access_time,
                'Time',
                '${DateFormat.jm().format(DateTime.parse(shift.startTime))} - ${DateFormat.jm().format(DateTime.parse(shift.endTime))}',
              ),
              _buildDetailRow(
                Icons.attach_money,
                'Hourly Rate',
                '£${shift.hourlyRate.toStringAsFixed(2)}',
              ),
              if (shift.location != null)
                _buildDetailRow(
                  Icons.location_on,
                  'Location',
                  shift.location!,
                ),
              if (shift.description != null) ...[
                const SizedBox(height: 16),
                const Text(
                  'Description',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(shift.description!),
              ],

              const SizedBox(height: 24),

              // Actions
              if (status == 'pending') ...[
                ElevatedButton(
                  onPressed: () {
                    Navigator.pop(context);
                    _showWithdrawDialog(context);
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                    minimumSize: const Size.fromHeight(50),
                  ),
                  child: const Text('Withdraw Application'),
                ),
              ],

              if (status == 'accepted') ...[
                ElevatedButton.icon(
                  onPressed: () {
                    // Navigate to shift details/check-in
                  },
                  icon: const Icon(Icons.check_circle),
                  label: const Text('View Shift Details'),
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size.fromHeight(50),
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  Widget _buildDetailRow(IconData icon, String label, String value) {
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

  void _showWithdrawDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Withdraw Application?'),
        content: const Text(
          'Are you sure you want to withdraw this application? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              // Implement withdraw logic
              onUpdate();
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Withdraw'),
          ),
        ],
      ),
    );
  }
}
