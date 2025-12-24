import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';

/// Screen for rating a venue after shift completion
/// Collects ratings and feedback to build venue reputation
class RateVenueScreen extends StatefulWidget {
  final Shift shift;
  final String venueName;

  const RateVenueScreen({
    super.key,
    required this.shift,
    required this.venueName,
  });

  @override
  State<RateVenueScreen> createState() => _RateVenueScreenState();
}

class _RateVenueScreenState extends State<RateVenueScreen> {
  bool _isSubmitting = false;

  // Overall rating
  double _overallRating = 0.0;

  // Category ratings
  double _managementRating = 0.0;
  double _environmentRating = 0.0;
  double _paymentRating = 0.0;
  double _communicationRating = 0.0;

  // Feedback
  final TextEditingController _feedbackController = TextEditingController();

  // Would work here again
  bool _wouldWorkAgain = true;

  // Issues checklist
  final Map<String, bool> _issues = {
    'Late payment': false,
    'Poor management': false,
    'Unsafe conditions': false,
    'Miscommunication': false,
    'Unprofessional behavior': false,
    'Shift hours incorrect': false,
  };

  @override
  void dispose() {
    _feedbackController.dispose();
    super.dispose();
  }

  Future<void> _submitRating() async {
    if (_overallRating == 0.0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please provide an overall rating'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);

      final ratingData = {
        'shift_id': widget.shift.id,
        'overall_rating': _overallRating,
        'management_rating': _managementRating,
        'environment_rating': _environmentRating,
        'payment_rating': _paymentRating,
        'communication_rating': _communicationRating,
        'would_work_again': _wouldWorkAgain,
        'feedback': _feedbackController.text.trim(),
        'issues': _issues.entries
            .where((entry) => entry.value)
            .map((entry) => entry.key)
            .toList(),
      };

      await api.submitVenueRating(ratingData);

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Thank you for your feedback!'),
          backgroundColor: Colors.green,
        ),
      );

      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;

      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to submit rating: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rate Venue'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Text(
              'How was your experience at ${widget.venueName}?',
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Your feedback helps other workers make informed decisions',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[600],
              ),
            ),
            const SizedBox(height: 32),

            // Overall Rating Card
            Card(
              elevation: 4,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    const Text(
                      'Overall Rating',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 16),
                    _buildStarRating(
                      _overallRating,
                      (rating) => setState(() => _overallRating = rating),
                      size: 48,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _getRatingLabel(_overallRating),
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: _getRatingColor(_overallRating),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Category Ratings
            const Text(
              'Rate Specific Areas',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),

            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    _buildCategoryRating(
                      'Management',
                      Icons.people,
                      _managementRating,
                      (rating) => setState(() => _managementRating = rating),
                    ),
                    const Divider(height: 24),
                    _buildCategoryRating(
                      'Work Environment',
                      Icons.place,
                      _environmentRating,
                      (rating) => setState(() => _environmentRating = rating),
                    ),
                    const Divider(height: 24),
                    _buildCategoryRating(
                      'Payment & Compensation',
                      Icons.attach_money,
                      _paymentRating,
                      (rating) => setState(() => _paymentRating = rating),
                    ),
                    const Divider(height: 24),
                    _buildCategoryRating(
                      'Communication',
                      Icons.chat,
                      _communicationRating,
                      (rating) => setState(() => _communicationRating = rating),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Would Work Again
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Icon(
                      Icons.refresh,
                      color: Theme.of(context).primaryColor,
                      size: 28,
                    ),
                    const SizedBox(width: 16),
                    const Expanded(
                      child: Text(
                        'Would you work here again?',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    Switch(
                      value: _wouldWorkAgain,
                      onChanged: (value) {
                        setState(() => _wouldWorkAgain = value);
                      },
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Issues Checklist
            const Text(
              'Any Issues? (Optional)',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Select any problems you experienced',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey,
              ),
            ),
            const SizedBox(height: 16),

            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Column(
                  children: _issues.entries.map((entry) {
                    return CheckboxListTile(
                      title: Text(entry.key),
                      value: entry.value,
                      onChanged: (value) {
                        setState(() {
                          _issues[entry.key] = value ?? false;
                        });
                      },
                      controlAffinity: ListTileControlAffinity.leading,
                    );
                  }).toList(),
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Written Feedback
            const Text(
              'Additional Feedback (Optional)',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),

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
                    TextField(
                      controller: _feedbackController,
                      maxLines: 5,
                      maxLength: 500,
                      decoration: const InputDecoration(
                        hintText: 'Share more details about your experience...',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Your feedback is kept confidential and helps improve the platform',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[600],
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
                      Icon(Icons.info_outline, color: Colors.blue, size: 20),
                      SizedBox(width: 8),
                      Text(
                        'Your Privacy',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.blue,
                        ),
                      ),
                    ],
                  ),
                  SizedBox(height: 8),
                  Text(
                    '• Your rating is anonymous to the venue\n'
                    '• Aggregate ratings are shown publicly\n'
                    '• Serious issues are reviewed by our team\n'
                    '• Honest feedback helps the community',
                    style: TextStyle(fontSize: 14, height: 1.5),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 32),

            // Submit Button
            ElevatedButton.icon(
              onPressed: _isSubmitting ? null : _submitRating,
              icon: _isSubmitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Icon(Icons.send),
              label: Text(_isSubmitting ? 'Submitting...' : 'Submit Rating'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                minimumSize: const Size.fromHeight(56),
              ),
            ),

            const SizedBox(height: 16),

            // Skip Button
            TextButton(
              onPressed: _isSubmitting
                  ? null
                  : () => Navigator.pop(context, false),
              child: const Text('Skip for Now'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCategoryRating(
    String title,
    IconData icon,
    double rating,
    ValueChanged<double> onRatingChanged,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 20, color: Colors.grey[600]),
            const SizedBox(width: 12),
            Text(
              title,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        _buildStarRating(rating, onRatingChanged, size: 32),
      ],
    );
  }

  Widget _buildStarRating(
    double rating,
    ValueChanged<double> onRatingChanged, {
    double size = 32,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(5, (index) {
        return GestureDetector(
          onTap: () => onRatingChanged((index + 1).toDouble()),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Icon(
              index < rating ? Icons.star : Icons.star_border,
              color: Colors.amber,
              size: size,
            ),
          ),
        );
      }),
    );
  }

  String _getRatingLabel(double rating) {
    if (rating == 0) return 'Tap to rate';
    if (rating == 1) return 'Poor';
    if (rating == 2) return 'Fair';
    if (rating == 3) return 'Good';
    if (rating == 4) return 'Very Good';
    return 'Excellent';
  }

  Color _getRatingColor(double rating) {
    if (rating == 0) return Colors.grey;
    if (rating <= 2) return Colors.red;
    if (rating == 3) return Colors.orange;
    if (rating == 4) return Colors.lightGreen;
    return Colors.green;
  }
}
