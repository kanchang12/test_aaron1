import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';

class SmartMatchingScreen extends StatefulWidget {
  final Shift shift;

  const SmartMatchingScreen({super.key, required this.shift});

  @override
  State<SmartMatchingScreen> createState() => _SmartMatchingScreenState();
}

class _SmartMatchingScreenState extends State<SmartMatchingScreen> {
  List<Map<String, dynamic>> _matches = [];
  bool _isLoading = true;
  bool _autoInviteEnabled = false;

  @override
  void initState() {
    super.initState();
    _loadMatches();
  }

  Future<void> _loadMatches() async {
    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final matchesResponse = await api.getSmartMatches(widget.shift.id);

      setState(() {
        _matches = List<Map<String, dynamic>>.from(matchesResponse as List);
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to load matches: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _inviteWorker(int workerId, String workerName) async {
    try {
      final api = Provider.of<ApiService>(context, listen: false);
      await api.inviteWorkerToShift(widget.shift.id, workerId);

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Invitation sent to $workerName'),
          backgroundColor: Colors.green,
        ),
      );
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

  Future<void> _inviteAllTop() async {
    final topMatches = _matches.take(5).toList();
    for (final match in topMatches) {
      await _inviteWorker(
        match['worker']['id'],
        match['worker']['name'] ?? 'Worker',
      );
    }

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Invitations sent to top 5 matches'),
        backgroundColor: Colors.green,
      ),
    );
  }

  Color _getMatchScoreColor(double score) {
    if (score >= 90) return Colors.green;
    if (score >= 70) return const Color(0xFFFFD700);
    if (score >= 50) return Colors.orange;
    return Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Smart Matching'),
        backgroundColor: Colors.transparent,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadMatches,
            tooltip: 'Refresh Matches',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFFFFD700)),
            )
          : Column(
              children: [
                // Header Card
                Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFFFFD700), Color(0xFFFFA500)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.stars, color: Colors.black, size: 28),
                          SizedBox(width: 8),
                          Text(
                            'Top Matches',
                            style: TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                              color: Colors.black,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${_matches.length} qualified workers found',
                        style: const TextStyle(
                          fontSize: 14,
                          color: Colors.black87,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: ElevatedButton.icon(
                              onPressed: _matches.isEmpty ? null : _inviteAllTop,
                              icon: const Icon(Icons.send),
                              label: const Text('Invite Top 5'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.black,
                                foregroundColor: const Color(0xFFFFD700),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Text(
                                  'Auto-Invite',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.black87,
                                  ),
                                ),
                                Switch(
                                  value: _autoInviteEnabled,
                                  onChanged: (value) {
                                    setState(() {
                                      _autoInviteEnabled = value;
                                    });
                                    // TODO: Save preference
                                  },
                                  activeColor: Colors.black,
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                // Info Card
                Container(
                  margin: const EdgeInsets.symmetric(horizontal: 16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.blue.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.blue.withOpacity(0.3)),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.info_outline, color: Colors.blue, size: 20),
                      SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Workers are ranked by skills, experience, reliability, and availability',
                          style: TextStyle(fontSize: 12, color: Colors.white70),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 16),

                // Matches List
                Expanded(
                  child: _matches.isEmpty
                      ? const Center(
                          child: Text(
                            'No matches found',
                            style: TextStyle(color: Colors.white60),
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: _matches.length,
                          itemBuilder: (context, index) {
                            final match = _matches[index];
                            return _buildMatchCard(match, index + 1);
                          },
                        ),
                ),
              ],
            ),
    );
  }

  Widget _buildMatchCard(Map<String, dynamic> match, int rank) {
    final worker = match['worker'];
    final matchScore = (match['match_score'] ?? 0).toDouble();
    final acceptLikelihood = (match['accept_likelihood'] ?? 0).toDouble();
    final matchReason = match['match_reason'] ?? '';

    final scoreColor = _getMatchScoreColor(matchScore);

    return Card(
      color: Theme.of(context).colorScheme.surface,
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () => _showWorkerDetails(worker, match),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // Rank Badge
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: rank <= 3
                          ? const Color(0xFFFFD700).withOpacity(0.2)
                          : Colors.white.withOpacity(0.05),
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: rank <= 3
                            ? const Color(0xFFFFD700)
                            : Colors.white24,
                      ),
                    ),
                    child: Center(
                      child: Text(
                        '#$rank',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: rank <= 3
                              ? const Color(0xFFFFD700)
                              : Colors.white,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Worker Info
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          worker['name'] ?? 'Unknown Worker',
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        if (worker['cv_summary'] != null)
                          Text(
                            worker['cv_summary'],
                            style: const TextStyle(
                              fontSize: 12,
                              color: Colors.white60,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                      ],
                    ),
                  ),

                  // Match Score
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: scoreColor.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: scoreColor.withOpacity(0.5)),
                    ),
                    child: Text(
                      '${matchScore.toInt()}%',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: scoreColor,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 12),

              // Match Details
              Row(
                children: [
                  _buildStatBadge(
                    Icons.star,
                    worker['average_rating']?.toStringAsFixed(1) ?? 'N/A',
                    Colors.amber,
                  ),
                  const SizedBox(width: 8),
                  _buildStatBadge(
                    Icons.verified,
                    '${worker['reliability_score']?.toInt() ?? 0}%',
                    Colors.green,
                  ),
                  const SizedBox(width: 8),
                  _buildStatBadge(
                    Icons.work,
                    '${worker['completed_shifts'] ?? 0} shifts',
                    Colors.blue,
                  ),
                ],
              ),

              const SizedBox(height: 12),

              // Match Reason
              if (matchReason.isNotEmpty)
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.05),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.lightbulb_outline,
                        size: 16,
                        color: Color(0xFFFFD700),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          matchReason,
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.white70,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

              const SizedBox(height: 12),

              // Accept Likelihood & Invite Button
              Row(
                children: [
                  Expanded(
                    child: Row(
                      children: [
                        const Icon(
                          Icons.trending_up,
                          size: 16,
                          color: Colors.green,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'Accept Likelihood: ${acceptLikelihood.toInt()}%',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.green,
                          ),
                        ),
                      ],
                    ),
                  ),
                  ElevatedButton.icon(
                    onPressed: () => _inviteWorker(
                      worker['id'],
                      worker['name'] ?? 'Worker',
                    ),
                    icon: const Icon(Icons.send, size: 16),
                    label: const Text('Invite'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFFFD700),
                      foregroundColor: Colors.black,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatBadge(IconData icon, String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: color,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  void _showWorkerDetails(
      Map<String, dynamic> worker, Map<String, dynamic> match) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Theme.of(context).colorScheme.surface,
        title: Text(worker['name'] ?? 'Worker Details'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (worker['cv_summary'] != null) ...[
                const Text(
                  'Experience Summary',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: Colors.white60,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  worker['cv_summary'],
                  style: const TextStyle(fontSize: 13),
                ),
                const Divider(height: 24),
              ],
              _buildDetailRow('Average Rating',
                  '⭐ ${worker['average_rating']?.toStringAsFixed(1) ?? 'N/A'}'),
              const SizedBox(height: 8),
              _buildDetailRow('Reliability Score',
                  '${worker['reliability_score']?.toInt() ?? 0}%'),
              const SizedBox(height: 8),
              _buildDetailRow(
                  'Completed Shifts', '${worker['completed_shifts'] ?? 0}'),
              const SizedBox(height: 8),
              _buildDetailRow('Match Score',
                  '${(match['match_score'] ?? 0).toInt()}%'),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              _inviteWorker(worker['id'], worker['name'] ?? 'Worker');
            },
            child: const Text('Invite'),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 13, color: Colors.white60),
        ),
        Text(
          value,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
        ),
      ],
    );
  }
}
