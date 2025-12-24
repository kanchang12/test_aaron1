import 'dart:io';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../../services/api_service.dart';

class IDVerificationScreen extends StatefulWidget {
  final bool isRequired;
  final VoidCallback? onComplete;

  const IDVerificationScreen({
    super.key,
    this.isRequired = false,
    this.onComplete,
  });

  @override
  State<IDVerificationScreen> createState() => _IDVerificationScreenState();
}

class _IDVerificationScreenState extends State<IDVerificationScreen> {
  File? _governmentIdFile;
  File? _workAuthFile;
  File? _certificationFile;

  String? _governmentIdUrl;
  String? _workAuthUrl;
  String? _certificationUrl;

  bool _isLoading = false;
  bool _isUploadingGovId = false;
  bool _isUploadingWorkAuth = false;
  bool _isUploadingCert = false;

  String _verificationStatus = 'pending';

  @override
  void initState() {
    super.initState();
    _loadVerificationStatus();
  }

  Future<void> _loadVerificationStatus() async {
    setState(() => _isLoading = true);

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final verification = await api.getVerificationStatus();

      if (mounted) {
        setState(() {
          _governmentIdUrl = verification['government_id_url'];
          _workAuthUrl = verification['work_authorization_url'];
          _certificationUrl = verification['certification_url'];
          _verificationStatus = verification['status'] ?? 'pending';
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _pickDocument(String documentType) async {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera),
              title: const Text('Take Photo'),
              onTap: () async {
                Navigator.pop(context);
                await _captureImage(documentType);
              },
            ),
            ListTile(
              leading: const Icon(Icons.photo_library),
              title: const Text('Choose from Gallery'),
              onTap: () async {
                Navigator.pop(context);
                await _pickImage(documentType);
              },
            ),
            ListTile(
              leading: const Icon(Icons.attach_file),
              title: const Text('Choose PDF File'),
              onTap: () async {
                Navigator.pop(context);
                await _pickFile(documentType);
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _captureImage(String documentType) async {
    final ImagePicker picker = ImagePicker();
    final XFile? image = await picker.pickImage(
      source: ImageSource.camera,
      maxWidth: 1920,
      maxHeight: 1920,
      imageQuality: 85,
    );

    if (image != null) {
      setState(() {
        if (documentType == 'government_id') {
          _governmentIdFile = File(image.path);
        } else if (documentType == 'work_auth') {
          _workAuthFile = File(image.path);
        } else if (documentType == 'certification') {
          _certificationFile = File(image.path);
        }
      });
      await _uploadDocument(documentType);
    }
  }

  Future<void> _pickImage(String documentType) async {
    final ImagePicker picker = ImagePicker();
    final XFile? image = await picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 1920,
      maxHeight: 1920,
      imageQuality: 85,
    );

    if (image != null) {
      setState(() {
        if (documentType == 'government_id') {
          _governmentIdFile = File(image.path);
        } else if (documentType == 'work_auth') {
          _workAuthFile = File(image.path);
        } else if (documentType == 'certification') {
          _certificationFile = File(image.path);
        }
      });
      await _uploadDocument(documentType);
    }
  }

  Future<void> _pickFile(String documentType) async {
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png'],
    );

    if (result != null) {
      setState(() {
        if (documentType == 'government_id') {
          _governmentIdFile = File(result.files.single.path!);
        } else if (documentType == 'work_auth') {
          _workAuthFile = File(result.files.single.path!);
        } else if (documentType == 'certification') {
          _certificationFile = File(result.files.single.path!);
        }
      });
      await _uploadDocument(documentType);
    }
  }

  Future<void> _uploadDocument(String documentType) async {
    File? fileToUpload;

    if (documentType == 'government_id') {
      fileToUpload = _governmentIdFile;
      setState(() => _isUploadingGovId = true);
    } else if (documentType == 'work_auth') {
      fileToUpload = _workAuthFile;
      setState(() => _isUploadingWorkAuth = true);
    } else if (documentType == 'certification') {
      fileToUpload = _certificationFile;
      setState(() => _isUploadingCert = true);
    }

    if (fileToUpload == null) return;

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      final result = await api.uploadVerificationDocument(
        fileToUpload.path,
        documentType,
      );

      if (mounted) {
        setState(() {
          if (documentType == 'government_id') {
            _governmentIdUrl = result['document_url'];
            _isUploadingGovId = false;
          } else if (documentType == 'work_auth') {
            _workAuthUrl = result['document_url'];
            _isUploadingWorkAuth = false;
          } else if (documentType == 'certification') {
            _certificationUrl = result['document_url'];
            _isUploadingCert = false;
          }
          _verificationStatus = 'pending_review';
        });

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Document uploaded! Awaiting admin review.'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          if (documentType == 'government_id') _isUploadingGovId = false;
          if (documentType == 'work_auth') _isUploadingWorkAuth = false;
          if (documentType == 'certification') _isUploadingCert = false;
        });

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Upload failed: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _submitForReview() async {
    if (_governmentIdUrl == null || _workAuthUrl == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please upload Government ID and Work Authorization'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    try {
      final api = Provider.of<ApiService>(context, listen: false);
      await api.submitForVerification();

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Submitted for verification! We will review within 24 hours.'),
          backgroundColor: Colors.green,
        ),
      );

      if (widget.onComplete != null) {
        widget.onComplete!();
      } else {
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Submission failed: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('ID Verification'),
        automaticallyImplyLeading: !widget.isRequired,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Header
                  const Text(
                    'Verify Your Identity',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Upload documents to verify your identity and work eligibility',
                    style: TextStyle(fontSize: 16, color: Colors.grey),
                  ),
                  const SizedBox(height: 24),

                  // Status Badge
                  _buildStatusBadge(),
                  const SizedBox(height: 24),

                  // Government ID
                  _buildDocumentCard(
                    title: 'Government ID *',
                    description: 'Driver\'s license, passport, or national ID',
                    icon: Icons.badge_outlined,
                    file: _governmentIdFile,
                    url: _governmentIdUrl,
                    isUploading: _isUploadingGovId,
                    onTap: () => _pickDocument('government_id'),
                  ),
                  const SizedBox(height: 16),

                  // Work Authorization
                  _buildDocumentCard(
                    title: 'Work Authorization *',
                    description: 'Visa, work permit, or proof of right to work',
                    icon: Icons.work_outline,
                    file: _workAuthFile,
                    url: _workAuthUrl,
                    isUploading: _isUploadingWorkAuth,
                    onTap: () => _pickDocument('work_auth'),
                  ),
                  const SizedBox(height: 16),

                  // Certifications (Optional)
                  _buildDocumentCard(
                    title: 'Certifications (Optional)',
                    description: 'Food safety, bartending, or other relevant certifications',
                    icon: Icons.verified_outlined,
                    file: _certificationFile,
                    url: _certificationUrl,
                    isUploading: _isUploadingCert,
                    onTap: () => _pickDocument('certification'),
                    isOptional: true,
                  ),
                  const SizedBox(height: 32),

                  // Info box
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
                              'Important Information',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Colors.blue,
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 8),
                        Text(
                          '• All documents are securely stored and encrypted\n'
                          '• Verification typically takes 24-48 hours\n'
                          '• You will be notified when verification is complete\n'
                          '• You cannot accept shifts until verified',
                          style: TextStyle(fontSize: 14, color: Colors.black87),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 32),

                  // Submit Button
                  ElevatedButton(
                    onPressed: (_governmentIdUrl != null && _workAuthUrl != null)
                        ? _submitForReview
                        : null,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: const Text(
                      'Submit for Verification',
                      style: TextStyle(fontSize: 16),
                    ),
                  ),
                  const SizedBox(height: 16),

                  if (!widget.isRequired)
                    TextButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('Do This Later'),
                    ),
                ],
              ),
            ),
    );
  }

  Widget _buildStatusBadge() {
    Color badgeColor;
    IconData badgeIcon;
    String badgeText;

    switch (_verificationStatus) {
      case 'verified':
        badgeColor = Colors.green;
        badgeIcon = Icons.check_circle;
        badgeText = 'Verified';
        break;
      case 'pending_review':
        badgeColor = Colors.orange;
        badgeIcon = Icons.pending;
        badgeText = 'Pending Review';
        break;
      case 'rejected':
        badgeColor = Colors.red;
        badgeIcon = Icons.cancel;
        badgeText = 'Verification Failed';
        break;
      default:
        badgeColor = Colors.grey;
        badgeIcon = Icons.info_outline;
        badgeText = 'Not Verified';
    }

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      decoration: BoxDecoration(
        color: badgeColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: badgeColor.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(badgeIcon, color: badgeColor),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Verification Status',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                  ),
                ),
                Text(
                  badgeText,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: badgeColor,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDocumentCard({
    required String title,
    required String description,
    required IconData icon,
    required File? file,
    required String? url,
    required bool isUploading,
    required VoidCallback onTap,
    bool isOptional = false,
  }) {
    final bool hasDocument = file != null || url != null;

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: isUploading ? null : onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Theme.of(context).primaryColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      icon,
                      color: Theme.of(context).primaryColor,
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
                        Text(
                          description,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (isUploading)
                    const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  else if (hasDocument)
                    const Icon(Icons.check_circle, color: Colors.green, size: 24)
                  else
                    Icon(Icons.upload_file, color: Colors.grey[400], size: 24),
                ],
              ),
              if (hasDocument) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.green.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.description, size: 16, color: Colors.green),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          file != null ? file.path.split('/').last : 'Uploaded',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.green,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      TextButton(
                        onPressed: onTap,
                        child: const Text('Replace', style: TextStyle(fontSize: 12)),
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
}
