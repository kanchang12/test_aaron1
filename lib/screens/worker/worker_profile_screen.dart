import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';
import '../auth/login_screen.dart';

class WorkerProfileScreen extends StatefulWidget {
  const WorkerProfileScreen({super.key});

  @override
  State<WorkerProfileScreen> createState() => _WorkerProfileScreenState();
}

class _WorkerProfileScreenState extends State<WorkerProfileScreen> {
  User? _user;
  bool _isLoading = true;
  final _emailController = TextEditingController();
  bool _isEditingEmail = false;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    setState(() => _isLoading = true);
    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final data = await api.getCurrentUser();
      print('Profile data received: $data');
      setState(() {
        _user = User.fromJson(data);
        _emailController.text = _user?.email ?? '';
        _isLoading = false;
      });
    } catch (e) {
      print('Error loading profile: $e');
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to load profile: ${e.toString()}'),
            duration: const Duration(seconds: 5),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Logout',
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
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _user == null
              ? const Center(child: Text('No profile data'))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 32,
                            child: Text(
                              _user!.name != null && _user!.name!.isNotEmpty
                                  ? _user!.name![0].toUpperCase()
                                  : '?',
                              style: const TextStyle(fontSize: 32),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  _user!.name ?? 'No name',
                                  style: const TextStyle(
                                    fontSize: 24,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Row(
                                  children: [
                                    Expanded(
                                      child: _isEditingEmail
                                          ? TextFormField(
                                              controller: _emailController,
                                              decoration: const InputDecoration(
                                                labelText: 'Email',
                                              ),
                                            )
                                          : Text(
                                              _user!.email,
                                              style: TextStyle(color: Colors.grey[600]),
                                            ),
                                    ),
                                    if (_isEditingEmail)
                                      IconButton(
                                        icon: const Icon(Icons.check),
                                        onPressed: () async {
                                          setState(() => _isLoading = true);
                                          try {
                                            final api = Provider.of<ApiService>(context, listen: false);
                                            await api.updateEmail(_emailController.text.trim());
                                            await _loadProfile();
                                            setState(() => _isEditingEmail = false);
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              const SnackBar(content: Text('Email updated successfully')),
                                            );
                                          } catch (e) {
                                            setState(() => _isLoading = false);
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              SnackBar(content: Text('Failed to update email: ${e.toString()}')),
                                            );
                                          }
                                        },
                                      )
                                    else
                                      IconButton(
                                        icon: const Icon(Icons.edit),
                                        onPressed: () {
                                          setState(() => _isEditingEmail = true);
                                        },
                                      ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 24),
                      if (_user!.bio != null && _user!.bio!.isNotEmpty) ...[
                        const Text('Bio', style: TextStyle(fontWeight: FontWeight.bold)),
                        Text(_user!.bio!),
                        const SizedBox(height: 16),
                      ],
                      if (_user!.cvSummary != null && _user!.cvSummary!.isNotEmpty) ...[
                        const Text('CV Summary', style: TextStyle(fontWeight: FontWeight.bold)),
                        Text(_user!.cvSummary!),
                        const SizedBox(height: 16),
                      ],
                      if (_user!.address != null && _user!.address!.isNotEmpty) ...[
                        const Text('Address', style: TextStyle(fontWeight: FontWeight.bold)),
                        Text(_user!.address!),
                        const SizedBox(height: 16),
                      ],
                      if (_user!.phone != null && _user!.phone!.isNotEmpty) ...[
                        const Text('Phone', style: TextStyle(fontWeight: FontWeight.bold)),
                        Text(_user!.phone!),
                        const SizedBox(height: 16),
                      ],
                      if (_user!.referralCode != null && _user!.referralCode!.isNotEmpty) ...[
                        const Text('Referral Code', style: TextStyle(fontWeight: FontWeight.bold)),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.green.shade50,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.green.shade300),
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  _user!.referralCode!,
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 2,
                                  ),
                                ),
                              ),
                              IconButton(
                                icon: const Icon(Icons.copy),
                                onPressed: () {
                                  Clipboard.setData(ClipboardData(text: _user!.referralCode!));
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(content: Text('Referral code copied!')),
                                  );
                                },
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],
                      if (_user!.referralBalance != null && _user!.referralBalance! > 0) ...[
                        const Text('Referral Balance', style: TextStyle(fontWeight: FontWeight.bold)),
                        Text('£${_user!.referralBalance!.toStringAsFixed(2)}',
                          style: const TextStyle(fontSize: 18, color: Colors.green)),
                        const SizedBox(height: 16),
                      ],
                      const SizedBox(height: 32),
                      ElevatedButton.icon(
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
                        icon: const Icon(Icons.logout),
                        label: const Text('Logout'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.red,
                          foregroundColor: Colors.white,
                          minimumSize: const Size.fromHeight(50),
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }
}
