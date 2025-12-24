import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../../services/api_service.dart';
import '../../models/models.dart';
import 'package:intl/intl.dart';

class DisputeScreen extends StatefulWidget {
  final int? shiftId;

  const DisputeScreen({super.key, this.shiftId});

  @override
  State<DisputeScreen> createState() => _DisputeScreenState();
}

class _DisputeScreenState extends State<DisputeScreen> {
  List<Dispute> _disputes = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadDisputes();
  }

  Future<void> _loadDisputes() async {
    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final disputesResponse = await api.getDisputes(shiftId: widget.shiftId);
      final disputes = (disputesResponse as List)
          .map((json) => Dispute.fromJson(json))
          .toList();

      setState(() {
        _disputes = disputes;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to load disputes: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void _showCreateDisputeDialog() {
    String? selectedType;
    final descriptionController = TextEditingController();
    String? evidencePath;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: Theme.of(context).colorScheme.surface,
          title: const Text('Report an Issue'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'What type of issue are you reporting?',
                  style: TextStyle(fontSize: 14, color: Colors.white70),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: selectedType,
                  decoration: const InputDecoration(
                    labelText: 'Issue Type',
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'hours_dispute',
                      child: Text('Incorrect Hours'),
                    ),
                    DropdownMenuItem(
                      value: 'no_show_venue',
                      child: Text('Venue No-Show'),
                    ),
                    DropdownMenuItem(
                      value: 'early_dismissal',
                      child: Text('Early Dismissal'),
                    ),
                    DropdownMenuItem(
                      value: 'unsafe_conditions',
                      child: Text('Unsafe Conditions'),
                    ),
                    DropdownMenuItem(
                      value: 'harassment',
                      child: Text('Harassment/Abuse'),
                    ),
                    DropdownMenuItem(
                      value: 'other',
                      child: Text('Other'),
                    ),
                  ],
                  onChanged: (value) {
                    setDialogState(() {
                      selectedType = value;
                    });
                  },
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: descriptionController,
                  decoration: const InputDecoration(
                    labelText: 'Description',
                    hintText: 'Please describe the issue in detail...',
                  ),
                  maxLines: 4,
                ),
                const SizedBox(height: 16),
                OutlinedButton.icon(
                  onPressed: () async {
                    final result = await FilePicker.platform.pickFiles(
                      type: FileType.custom,
                      allowedExtensions: ['jpg', 'jpeg', 'png', 'pdf'],
                    );
                    if (result != null) {
                      setDialogState(() {
                        evidencePath = result.files.single.path;
                      });
                    }
                  },
                  icon: const Icon(Icons.attach_file),
                  label: Text(
                    evidencePath != null
                        ? 'Evidence attached'
                        : 'Attach Evidence (Optional)',
                  ),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFFFFD700),
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.orange.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.orange.withOpacity(0.3)),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.warning, color: Colors.orange, size: 16),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'False reports may result in account suspension',
                          style: TextStyle(fontSize: 11, color: Colors.white70),
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
                if (selectedType == null ||
                    descriptionController.text.isEmpty) {
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
                  await api.createDispute(
                    shiftId: widget.shiftId!,
                    disputeType: selectedType!,
                    description: descriptionController.text,
                    evidencePath: evidencePath,
                  );

                  if (!context.mounted) return;
                  Navigator.pop(context);

                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Dispute submitted successfully'),
                      backgroundColor: Colors.green,
                    ),
                  );

                  _loadDisputes();
                } catch (e) {
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Failed to submit dispute: $e'),
                      backgroundColor: Colors.red,
                    ),
                  );
                }
              },
              child: const Text('Submit'),
            ),
          ],
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'open':
        return Colors.orange;
      case 'under_review':
        return Colors.blue;
      case 'resolved':
        return Colors.green;
      case 'rejected':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  String _getDisputeTypeLabel(String type) {
    switch (type) {
      case 'hours_dispute':
        return 'Incorrect Hours';
      case 'no_show_venue':
        return 'Venue No-Show';
      case 'early_dismissal':
        return 'Early Dismissal';
      case 'unsafe_conditions':
        return 'Unsafe Conditions';
      case 'harassment':
        return 'Harassment/Abuse';
      default:
        return 'Other';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Disputes & Reports'),
        backgroundColor: Colors.transparent,
      ),
      body: _isLoading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFFFFD700)),
            )
          : _disputes.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.check_circle_outline,
                        size: 80,
                        color: Colors.white.withOpacity(0.3),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'No disputes',
                        style: TextStyle(
                          fontSize: 18,
                          color: Colors.white.withOpacity(0.5),
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'All your shifts are in good standing',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.white38,
                        ),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _disputes.length,
                  itemBuilder: (context, index) {
                    final dispute = _disputes[index];
                    return _buildDisputeCard(dispute);
                  },
                ),
      floatingActionButton: widget.shiftId != null
          ? FloatingActionButton.extended(
              onPressed: _showCreateDisputeDialog,
              backgroundColor: const Color(0xFFFFD700),
              foregroundColor: Colors.black,
              icon: const Icon(Icons.report_problem),
              label: const Text('Report Issue'),
            )
          : null,
    );
  }

  Widget _buildDisputeCard(Dispute dispute) {
    final createdDate = DateTime.parse(dispute.createdAt);
    final statusColor = _getStatusColor(dispute.status);

    return Card(
      color: Theme.of(context).colorScheme.surface,
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () => _showDisputeDetails(dispute),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: statusColor.withOpacity(0.5)),
                    ),
                    child: Text(
                      dispute.status.toUpperCase(),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: statusColor,
                      ),
                    ),
                  ),
                  const Spacer(),
                  Text(
                    DateFormat('MMM d, y').format(createdDate),
                    style: const TextStyle(
                      fontSize: 12,
                      color: Colors.white60,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                _getDisputeTypeLabel(dispute.disputeType),
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                dispute.description,
                style: const TextStyle(fontSize: 14, color: Colors.white70),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(
                    Icons.work_outline,
                    size: 16,
                    color: Colors.white.withOpacity(0.5),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'Shift #${dispute.shiftId}',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.white.withOpacity(0.5),
                    ),
                  ),
                  if (dispute.evidenceUrl != null) ...[
                    const Spacer(),
                    const Icon(
                      Icons.attach_file,
                      size: 16,
                      color: Color(0xFFFFD700),
                    ),
                    const SizedBox(width: 4),
                    const Text(
                      'Evidence attached',
                      style: TextStyle(
                        fontSize: 12,
                        color: Color(0xFFFFD700),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showDisputeDetails(Dispute dispute) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Theme.of(context).colorScheme.surface,
        title: Text(_getDisputeTypeLabel(dispute.disputeType)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildDetailRow('Status', dispute.status.toUpperCase(),
                  color: _getStatusColor(dispute.status)),
              const SizedBox(height: 12),
              _buildDetailRow('Shift ID', '#${dispute.shiftId}'),
              const SizedBox(height: 12),
              _buildDetailRow(
                'Reported',
                DateFormat('MMM d, y h:mm a')
                    .format(DateTime.parse(dispute.createdAt)),
              ),
              const Divider(height: 24),
              const Text(
                'Description',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: Colors.white60,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                dispute.description,
                style: const TextStyle(fontSize: 14),
              ),
              if (dispute.resolution != null) ...[
                const Divider(height: 24),
                const Text(
                  'Admin Resolution',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFFFFD700),
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.green.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.green.withOpacity(0.3)),
                  ),
                  child: Text(
                    dispute.resolution!,
                    style: const TextStyle(fontSize: 13),
                  ),
                ),
                if (dispute.resolvedAt != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      'Resolved: ${DateFormat('MMM d, y').format(DateTime.parse(dispute.resolvedAt!))}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: Colors.white60,
                      ),
                    ),
                  ),
              ],
            ],
          ),
        ),
        actions: [
          if (dispute.evidenceUrl != null)
            TextButton.icon(
              onPressed: () {
                // TODO: Open evidence URL
              },
              icon: const Icon(Icons.attach_file),
              label: const Text('View Evidence'),
            ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value, {Color? color}) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$label: ',
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.bold,
            color: Colors.white60,
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              fontSize: 13,
              color: color ?? Colors.white,
            ),
          ),
        ),
      ],
    );
  }
}
