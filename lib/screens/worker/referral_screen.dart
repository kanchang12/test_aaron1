import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:provider/provider.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';

class ReferralScreen extends StatefulWidget {
  const ReferralScreen({super.key});

  @override
  State<ReferralScreen> createState() => _ReferralScreenState();
}

class _ReferralScreenState extends State<ReferralScreen> {
  String? _referralCode;
  double _referralBalance = 0.0;
  List<Referral> _referrals = [];
  bool _isLoading = true;
  bool _isWithdrawing = false;

  final _venueNameController = TextEditingController();
  final _venueEmailController = TextEditingController();
  final _venueManagerController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadReferralData();
  }

  @override
  void dispose() {
    _venueNameController.dispose();
    _venueEmailController.dispose();
    _venueManagerController.dispose();
    super.dispose();
  }

  Future<void> _loadReferralData() async {
    try {
      final api = Provider.of<ApiService>(context, listen: false);

      // Get user profile for referral code and balance
      final user = await api.getCurrentUser();

      // Get referral list
      final referralsResponse = await api.getReferrals();
      final referrals = (referralsResponse as List)
          .map((json) => Referral.fromJson(json))
          .toList();

      setState(() {
        _referralCode = user['referral_code'] ?? 'DIISCO${user['id']}';
        _referralBalance = user['referral_balance']?.toDouble() ?? 0.0;
        _referrals = referrals;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to load referral data: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  String get _referralLink =>
      'https://diisco.app/join?ref=$_referralCode';

  void _copyReferralLink() {
    Clipboard.setData(ClipboardData(text: _referralLink));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Referral link copied to clipboard!'),
        backgroundColor: Colors.green,
      ),
    );
  }

  void _showQRCode() {
    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.white,
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Scan to Join Diisco',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: Colors.black,
                ),
              ),
              const SizedBox(height: 16),
              QrImageView(
                data: _referralLink,
                version: QrVersions.auto,
                size: 250.0,
                backgroundColor: Colors.white,
              ),
              const SizedBox(height: 16),
              Text(
                'Code: $_referralCode',
                style: const TextStyle(
                  fontSize: 16,
                  color: Colors.black87,
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Close'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showVenueReferralDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Theme.of(context).colorScheme.surface,
        title: const Text('Refer a Venue'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Earn £1 per shift when you refer a venue to Diisco!',
                style: TextStyle(fontSize: 14, color: Color(0xFFFFD700)),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _venueNameController,
                decoration: const InputDecoration(
                  labelText: 'Venue Name *',
                  hintText: 'The Golden Lion',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _venueManagerController,
                decoration: const InputDecoration(
                  labelText: "Manager's Name *",
                  hintText: 'John Smith',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _venueEmailController,
                decoration: const InputDecoration(
                  labelText: "Manager's Email *",
                  hintText: 'john@goldenlion.com',
                ),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blue.withOpacity(0.3)),
                ),
                child: const Text(
                  'The venue has 7 days to accept this referral. They will receive 90 days of free premium features!',
                  style: TextStyle(fontSize: 12, color: Colors.white70),
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _venueNameController.clear();
              _venueEmailController.clear();
              _venueManagerController.clear();
            },
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: _submitVenueReferral,
            child: const Text('Send Invitation'),
          ),
        ],
      ),
    );
  }

  Future<void> _submitVenueReferral() async {
    if (_venueNameController.text.isEmpty ||
        _venueEmailController.text.isEmpty ||
        _venueManagerController.text.isEmpty) {
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
      await api.referVenue(
        venueName: _venueNameController.text,
        managerName: _venueManagerController.text,
        managerEmail: _venueEmailController.text,
      );

      if (!mounted) return;
      Navigator.pop(context);
      _venueNameController.clear();
      _venueEmailController.clear();
      _venueManagerController.clear();

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Venue invitation sent successfully!'),
          backgroundColor: Colors.green,
        ),
      );

      _loadReferralData();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to send invitation: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _withdrawBalance() async {
    if (_referralBalance <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No balance to withdraw'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() => _isWithdrawing = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      await api.withdrawReferralBalance();

      setState(() {
        _referralBalance = 0.0;
        _isWithdrawing = false;
      });

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Withdrawal successful! Funds will be transferred to your account.'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (e) {
      setState(() => _isWithdrawing = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Withdrawal failed: $e'),
          backgroundColor: Colors.red,
        ),
      );
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

    final activeReferrals = _referrals.where((r) => r.status == 'active').length;
    final totalShifts = _referrals.fold<int>(
      0,
      (sum, r) => sum + r.shiftsCompleted,
    );
    final totalEarned = _referrals.fold<double>(
      0.0,
      (sum, r) => sum + r.totalEarned,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Referrals & Rewards'),
        backgroundColor: Colors.transparent,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Balance Card
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFFFFD700), Color(0xFFFFA500)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                children: [
                  const Text(
                    'Referral Balance',
                    style: TextStyle(
                      fontSize: 16,
                      color: Colors.black87,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '£${_referralBalance.toStringAsFixed(2)}',
                    style: const TextStyle(
                      fontSize: 48,
                      fontWeight: FontWeight.bold,
                      color: Colors.black,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_isWithdrawing)
                    const CircularProgressIndicator(color: Colors.black)
                  else
                    ElevatedButton.icon(
                      onPressed: _withdrawBalance,
                      icon: const Icon(Icons.account_balance_wallet),
                      label: const Text('Withdraw'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.black,
                        foregroundColor: const Color(0xFFFFD700),
                      ),
                    ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // Stats Row
            Row(
              children: [
                Expanded(
                  child: _buildStatCard(
                    'Active Referrals',
                    activeReferrals.toString(),
                    Icons.people,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildStatCard(
                    'Total Shifts',
                    totalShifts.toString(),
                    Icons.work,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 12),

            Row(
              children: [
                Expanded(
                  child: _buildStatCard(
                    'Total Earned',
                    '£${totalEarned.toStringAsFixed(2)}',
                    Icons.monetization_on,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildStatCard(
                    'Per Shift',
                    '£1.00',
                    Icons.trending_up,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 32),

            // Referral Code Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Your Referral Code',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.05),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          _referralCode ?? 'Loading...',
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFFFFD700),
                            letterSpacing: 2,
                          ),
                        ),
                        IconButton(
                          onPressed: _copyReferralLink,
                          icon: const Icon(Icons.copy),
                          color: const Color(0xFFFFD700),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _copyReferralLink,
                          icon: const Icon(Icons.link),
                          label: const Text('Copy Link'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: const Color(0xFFFFD700),
                            side: const BorderSide(color: Color(0xFFFFD700)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _showQRCode,
                          icon: const Icon(Icons.qr_code),
                          label: const Text('Show QR'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: const Color(0xFFFFD700),
                            side: const BorderSide(color: Color(0xFFFFD700)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // Refer Venue Button
            ElevatedButton.icon(
              onPressed: _showVenueReferralDialog,
              icon: const Icon(Icons.business),
              label: const Text('Refer a Venue'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                backgroundColor: const Color(0xFFFFD700),
                foregroundColor: Colors.black,
              ),
            ),

            const SizedBox(height: 24),

            // Info Card
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
                        'How Referrals Work',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.blue,
                        ),
                      ),
                    ],
                  ),
                  SizedBox(height: 8),
                  Text(
                    '• Earn £1 for each shift your referrals complete\n'
                    '• Share your code or QR with other workers\n'
                    '• Refer venues and earn from every shift they post\n'
                    '• Referred venues get 90 days free premium\n'
                    '• Withdraw your balance anytime',
                    style: TextStyle(fontSize: 12, color: Colors.white70),
                  ),
                ],
              ),
            ),

            if (_referrals.isNotEmpty) ...[
              const SizedBox(height: 32),
              const Text(
                'Your Referrals',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              ..._referrals.map((referral) => _buildReferralItem(referral)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStatCard(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Icon(icon, color: const Color(0xFFFFD700), size: 24),
          const SizedBox(height: 8),
          Text(
            value,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 12,
              color: Colors.white60,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReferralItem(Referral referral) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
            referral.referredUserType == 'worker'
                ? Icons.person
                : Icons.business,
            color: const Color(0xFFFFD700),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  referral.referredUserType == 'worker'
                      ? 'Worker Referral'
                      : 'Venue Referral',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                Text(
                  '${referral.shiftsCompleted} shifts completed',
                  style: const TextStyle(fontSize: 12, color: Colors.white60),
                ),
              ],
            ),
          ),
          Text(
            '£${referral.totalEarned.toStringAsFixed(2)}',
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: Color(0xFFFFD700),
            ),
          ),
        ],
      ),
    );
  }
}
