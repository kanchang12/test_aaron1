import 'package:flutter/material.dart';

class AdminDashboardScreen extends StatelessWidget {
  const AdminDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Admin Dashboard')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.people),
              title: const Text('User Management'),
              subtitle: const Text('View, edit, suspend, or ban users'),
              onTap: () {
                // TODO: Implement user management
              },
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.work),
              title: const Text('Shift Moderation'),
              subtitle: const Text('Review, edit, or cancel shifts'),
              onTap: () {
                // TODO: Implement shift moderation
              },
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.report),
              title: const Text('Dispute Resolution'),
              subtitle: const Text('Handle disputes and evidence'),
              onTap: () {
                // TODO: Implement dispute resolution
              },
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.shield),
              title: const Text('Content Moderation'),
              subtitle: const Text('Review and moderate user content'),
              onTap: () {
                // TODO: Implement content moderation
              },
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.card_giftcard),
              title: const Text('Referral & Payment Tracking'),
              subtitle: const Text('Monitor referral bonuses and payments'),
              onTap: () {
                // TODO: Implement referral and payment tracking
              },
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.warning),
              title: const Text('Emergency Actions'),
              subtitle: const Text('Handle cancellations and no-shows'),
              onTap: () {
                // TODO: Implement emergency actions
              },
            ),
          ),
        ],
      ),
    );
  }
}
