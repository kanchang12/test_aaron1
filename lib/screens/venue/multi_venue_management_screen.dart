import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../services/api_service.dart';

class MultiVenueManagementScreen extends StatefulWidget {
  const MultiVenueManagementScreen({super.key});

  @override
  State<MultiVenueManagementScreen> createState() =>
      _MultiVenueManagementScreenState();
}

class _MultiVenueManagementScreenState
    extends State<MultiVenueManagementScreen> {
  List<dynamic> _venues = [];
  List<dynamic> _teamMembers = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final api = Provider.of<ApiService>(context, listen: false);

      final venuesResponse = await api.getVenues();
      final teamResponse = await api.getTeamMembers();

      setState(() {
        _venues = venuesResponse as List;
        _teamMembers = teamResponse as List;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to load data: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void _showAddVenueDialog() {
    final nameController = TextEditingController();
    final addressController = TextEditingController();
    final phoneController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Theme.of(context).colorScheme.surface,
        title: const Text('Add Venue Location'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameController,
                decoration: const InputDecoration(
                  labelText: 'Venue Name',
                  hintText: 'Downtown Location',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: addressController,
                decoration: const InputDecoration(
                  labelText: 'Address',
                  hintText: '123 Main St, London',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: phoneController,
                decoration: const InputDecoration(
                  labelText: 'Contact Phone',
                  hintText: '+44 20 1234 5678',
                ),
                keyboardType: TextInputType.phone,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              if (nameController.text.isEmpty ||
                  addressController.text.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Please fill all required fields'),
                    backgroundColor: Colors.orange,
                  ),
                );
                return;
              }

              try {
                final api = Provider.of<ApiService>(context, listen: false);
                await api.createVenue(
                  name: nameController.text,
                  address: addressController.text,
                  phone: phoneController.text,
                );

                if (!context.mounted) return;
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Venue added successfully!'),
                    backgroundColor: Colors.green,
                  ),
                );
                _loadData();
              } catch (e) {
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('Failed to add venue: $e'),
                    backgroundColor: Colors.red,
                  ),
                );
              }
            },
            child: const Text('Add Venue'),
          ),
        ],
      ),
    );
  }

  void _showInviteTeamMemberDialog() {
    final emailController = TextEditingController();
    final nameController = TextEditingController();
    String selectedRole = 'manager';

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: Theme.of(context).colorScheme.surface,
          title: const Text('Invite Team Member'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(
                    labelText: 'Name',
                    hintText: 'John Smith',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: emailController,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    hintText: 'john@example.com',
                  ),
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 16),
                const Text(
                  'Role',
                  style: TextStyle(fontSize: 14, color: Colors.white70),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  value: selectedRole,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'owner',
                      child: Text('Owner - Full access'),
                    ),
                    DropdownMenuItem(
                      value: 'manager',
                      child: Text('Manager - Post & manage shifts'),
                    ),
                    DropdownMenuItem(
                      value: 'staff',
                      child: Text('Staff - View only'),
                    ),
                  ],
                  onChanged: (value) {
                    setDialogState(() {
                      selectedRole = value!;
                    });
                  },
                ),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.blue.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.blue.withOpacity(0.3)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Role Permissions:',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _getRoleDescription(selectedRole),
                        style: const TextStyle(
                          fontSize: 11,
                          color: Colors.white70,
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
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                if (emailController.text.isEmpty ||
                    nameController.text.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Please fill all fields'),
                      backgroundColor: Colors.orange,
                    ),
                  );
                  return;
                }

                try {
                  final api = Provider.of<ApiService>(context, listen: false);
                  await api.inviteTeamMember(
                    name: nameController.text,
                    email: emailController.text,
                    role: selectedRole,
                  );

                  if (!context.mounted) return;
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Invitation sent successfully!'),
                      backgroundColor: Colors.green,
                    ),
                  );
                  _loadData();
                } catch (e) {
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Failed to send invitation: $e'),
                      backgroundColor: Colors.red,
                    ),
                  );
                }
              },
              child: const Text('Send Invitation'),
            ),
          ],
        ),
      ),
    );
  }

  String _getRoleDescription(String role) {
    switch (role) {
      case 'owner':
        return '• Full access to all venues\n'
            '• Manage team members\n'
            '• View all reports\n'
            '• Billing and settings';
      case 'manager':
        return '• Post and manage shifts\n'
            '• Chat with workers\n'
            '• View reports for assigned venues\n'
            '• No billing access';
      case 'staff':
        return '• View shifts and workers\n'
            '• Cannot make changes\n'
            '• Read-only access';
      default:
        return '';
    }
  }

  Color _getRoleColor(String role) {
    switch (role) {
      case 'owner':
        return const Color(0xFFFFD700);
      case 'manager':
        return Colors.blue;
      case 'staff':
        return Colors.grey;
      default:
        return Colors.white;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: Color(0xFFFFD700)),
        ),
      );
    }

    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Multi-Venue Management'),
          backgroundColor: Colors.transparent,
          bottom: const TabBar(
            indicatorColor: Color(0xFFFFD700),
            tabs: [
              Tab(text: 'Venues', icon: Icon(Icons.business)),
              Tab(text: 'Team', icon: Icon(Icons.people)),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            // Venues Tab
            _buildVenuesTab(),

            // Team Tab
            _buildTeamTab(),
          ],
        ),
      ),
    );
  }

  Widget _buildVenuesTab() {
    return Column(
      children: [
        // Add Venue Button
        Padding(
          padding: const EdgeInsets.all(16),
          child: ElevatedButton.icon(
            onPressed: _showAddVenueDialog,
            icon: const Icon(Icons.add_business),
            label: const Text('Add Venue Location'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
              backgroundColor: const Color(0xFFFFD700),
              foregroundColor: Colors.black,
            ),
          ),
        ),

        // Venues List
        Expanded(
          child: _venues.isEmpty
              ? const Center(
                  child: Text(
                    'No venues yet',
                    style: TextStyle(color: Colors.white60),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: _venues.length,
                  itemBuilder: (context, index) {
                    final venue = _venues[index];
                    return _buildVenueCard(venue);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildTeamTab() {
    return Column(
      children: [
        // Invite Member Button
        Padding(
          padding: const EdgeInsets.all(16),
          child: ElevatedButton.icon(
            onPressed: _showInviteTeamMemberDialog,
            icon: const Icon(Icons.person_add),
            label: const Text('Invite Team Member'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
              backgroundColor: const Color(0xFFFFD700),
              foregroundColor: Colors.black,
            ),
          ),
        ),

        // Team Members List
        Expanded(
          child: _teamMembers.isEmpty
              ? const Center(
                  child: Text(
                    'No team members yet',
                    style: TextStyle(color: Colors.white60),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: _teamMembers.length,
                  itemBuilder: (context, index) {
                    final member = _teamMembers[index];
                    return _buildTeamMemberCard(member);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildVenueCard(dynamic venue) {
    return Card(
      color: Theme.of(context).colorScheme.surface,
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: const CircleAvatar(
          backgroundColor: Color(0xFFFFD700),
          child: Icon(Icons.business, color: Colors.black),
        ),
        title: Text(
          venue['name'] ?? 'Unnamed Venue',
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          venue['address'] ?? 'No address',
          style: const TextStyle(fontSize: 12, color: Colors.white60),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          // Navigate to venue detail or switch venue
        },
      ),
    );
  }

  Widget _buildTeamMemberCard(dynamic member) {
    final role = member['venue_role'] ?? 'staff';
    final roleColor = _getRoleColor(role);

    return Card(
      color: Theme.of(context).colorScheme.surface,
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: roleColor.withOpacity(0.2),
          child: Text(
            (member['name'] ?? 'U')[0].toUpperCase(),
            style: TextStyle(
              color: roleColor,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        title: Text(
          member['name'] ?? 'Unknown',
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              member['email'] ?? '',
              style: const TextStyle(fontSize: 12, color: Colors.white60),
            ),
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: roleColor.withOpacity(0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                role.toUpperCase(),
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  color: roleColor,
                ),
              ),
            ),
          ],
        ),
        trailing: member['is_active'] == true
            ? const Icon(Icons.check_circle, color: Colors.green)
            : const Icon(Icons.pending, color: Colors.orange),
      ),
    );
  }
}
