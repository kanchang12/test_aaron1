import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_stripe/flutter_stripe.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';
import 'package:intl/intl.dart';

class BoostShiftScreen extends StatefulWidget {
  final Shift shift;

  const BoostShiftScreen({super.key, required this.shift});

  @override
  State<BoostShiftScreen> createState() => _BoostShiftScreenState();
}

class _BoostShiftScreenState extends State<BoostShiftScreen> {
  bool _isProcessing = false;
  final double _boostPrice = 19.99;

  Future<void> _processBoost() async {
    setState(() => _isProcessing = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);

      // Step 1: Create payment intent
      final paymentIntentResponse = await api.createBoostPaymentIntent(
        shiftId: widget.shift.id,
        amount: (_boostPrice * 100).toInt(), // Convert to cents
      );

      final clientSecret = paymentIntentResponse['client_secret'];

      // Step 2: Confirm payment with Stripe
      await Stripe.instance.confirmPayment(
        paymentIntentParams: PaymentIntentParams(
          clientSecret: clientSecret,
          paymentMethodData: const PaymentMethodParams.card(
            paymentMethodData: PaymentMethodData(),
          ),
        ),
      );

      // Step 3: Activate boost
      await api.activateShiftBoost(widget.shift.id);

      setState(() => _isProcessing = false);

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Shift boosted successfully!'),
          backgroundColor: Colors.green,
        ),
      );

      Navigator.pop(context, true);
    } catch (e) {
      setState(() => _isProcessing = false);

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Boost failed: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final shiftDate = DateTime.parse(widget.shift.startTime);
    final timeFormat = DateFormat('MMM d, y h:mm a');

    return Scaffold(
      appBar: AppBar(
        title: const Text('Boost Shift'),
        backgroundColor: Colors.transparent,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Icon
            const Icon(
              Icons.rocket_launch,
              size: 80,
              color: Color(0xFFFFD700),
            ),
            const SizedBox(height: 24),

            // Title
            const Text(
              'Boost Your Shift',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Get your shift filled faster with premium visibility',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 14, color: Colors.white70),
            ),

            const SizedBox(height: 32),

            // Shift Info Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.shift.role,
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const Icon(Icons.access_time, size: 16),
                      const SizedBox(width: 4),
                      Text(timeFormat.format(shiftDate)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.monetization_on, size: 16),
                      const SizedBox(width: 4),
                      Text('£${widget.shift.hourlyRate}/hour'),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 32),

            // Benefits List
            const Text(
              'Boost Benefits',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),

            _buildBenefitItem(
              Icons.stars,
              'Featured Placement',
              'Your shift appears at the top of all worker feeds',
            ),
            _buildBenefitItem(
              Icons.notifications_active,
              'Push Notifications',
              'Sent to all qualified workers in your area',
            ),
            _buildBenefitItem(
              Icons.badge,
              'URGENT Badge',
              'Eye-catching orange badge to grab attention',
            ),
            _buildBenefitItem(
              Icons.speed,
              '3x Faster Fill',
              'Boosted shifts fill on average 3x faster',
            ),

            const SizedBox(height: 32),

            // Price Card
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
                    'One-Time Payment',
                    style: TextStyle(
                      fontSize: 16,
                      color: Colors.black87,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '£${_boostPrice.toStringAsFixed(2)}',
                    style: const TextStyle(
                      fontSize: 48,
                      fontWeight: FontWeight.bold,
                      color: Colors.black,
                    ),
                  ),
                  const Text(
                    'Active until shift is filled',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.black87,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 32),

            // Boost Button
            if (_isProcessing)
              const Center(
                child: CircularProgressIndicator(color: Color(0xFFFFD700)),
              )
            else
              ElevatedButton.icon(
                onPressed: _processBoost,
                icon: const Icon(Icons.rocket_launch),
                label: const Text('Boost Now - £19.99'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: const Color(0xFFFFD700),
                  foregroundColor: Colors.black,
                ),
              ),

            const SizedBox(height: 16),

            // Info Note
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue.withOpacity(0.3)),
              ),
              child: const Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_outline, color: Colors.blue, size: 20),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Boost is a one-time fee. Payment is non-refundable once activated. Your shift will receive premium placement until filled.',
                      style: TextStyle(fontSize: 12, color: Colors.white70),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBenefitItem(IconData icon, String title, String description) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFFFFD700).withOpacity(0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              icon,
              color: const Color(0xFFFFD700),
              size: 24,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: const TextStyle(
                    fontSize: 13,
                    color: Colors.white70,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
