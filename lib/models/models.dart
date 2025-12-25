class User {
  final int id;
  final String email;
  final String role;
  final String? name;
  final String? phone;
  final String? profilePhoto;
  final bool isActive;
  final String? createdAt;

  // CV & Profile enhancements
  final String? cvUrl;
  final String? cvSummary;
  final String? bio;
  final String? address;

  // Reliability & Rating
  final double? reliabilityScore;
  final double? averageRating;
  final int? completedShifts;

  // Referral System
  final String? referralCode;
  final double? referralBalance;
  final int? referredBy;

  // Multi-Venue Management (for venues)
  final int? parentVenueId;
  final String? venueRole; // owner, manager, staff

  User({
    required this.id,
    required this.email,
    required this.role,
    this.name,
    this.phone,
    this.profilePhoto,
    required this.isActive,
    this.createdAt,
    this.cvUrl,
    this.cvSummary,
    this.bio,
    this.address,
    this.reliabilityScore,
    this.averageRating,
    this.completedShifts,
    this.referralCode,
    this.referralBalance,
    this.referredBy,
    this.parentVenueId,
    this.venueRole,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    // Extract worker_profile data if exists
    final workerProfile = json['worker_profile'];

    return User(
      id: json['id'],
      email: json['email'],
      role: json['role'],
      name: json['name'],
      phone: json['phone'],
      profilePhoto: json['profile_photo'],
      isActive: json['is_active'] ?? true,
      createdAt: json['created_at'],
      cvUrl: json['cv_url'] ?? workerProfile?['cv_document'],
      cvSummary: json['cv_summary'] ?? workerProfile?['cv_summary'],
      bio: json['bio'],
      address: json['address'],
      reliabilityScore: json['reliability_score']?.toDouble() ?? workerProfile?['reliability_score']?.toDouble(),
      averageRating: json['average_rating']?.toDouble() ?? workerProfile?['average_rating']?.toDouble(),
      completedShifts: json['completed_shifts'] ?? workerProfile?['completed_shifts'],
      referralCode: json['referral_code'] ?? workerProfile?['referral_code'],
      referralBalance: json['referral_balance']?.toDouble() ?? workerProfile?['referral_earnings']?.toDouble(),
      referredBy: json['referred_by'] ?? workerProfile?['referred_by'],
      parentVenueId: json['parent_venue_id'],
      venueRole: json['venue_role'],
    );
  }
}

class Shift {
  final int id;
  final int venueId;
  final String role;
  final String startTime;
  final String endTime;
  final String? location;
  final int numWorkersNeeded;
  final int numWorkersHired;
  final double hourlyRate;
  final String? description;
  final String status;
  final bool isBoosted;
  final String? fillRisk;
  
  Shift({
    required this.id,
    required this.venueId,
    required this.role,
    required this.startTime,
    required this.endTime,
    this.location,
    required this.numWorkersNeeded,
    required this.numWorkersHired,
    required this.hourlyRate,
    this.description,
    required this.status,
    required this.isBoosted,
    this.fillRisk,
  });
  
  factory Shift.fromJson(Map<String, dynamic> json) {
    return Shift(
      id: json['id'],
      venueId: json['venue_id'],
      role: json['role'],
      startTime: json['start_time'],
      endTime: json['end_time'],
      location: json['location'],
      numWorkersNeeded: json['num_workers_needed'],
      numWorkersHired: json['num_workers_hired'],
      hourlyRate: json['hourly_rate'].toDouble(),
      description: json['description'],
      status: json['status'],
      isBoosted: json['is_boosted'] ?? false,
      fillRisk: json['fill_risk'],
    );
  }
  
  bool get isAvailable => numWorkersHired < numWorkersNeeded;
}

class Application {
  final int id;
  final int shiftId;
  final int workerId;
  final String status;
  final double? offeredRate;
  final double? venueCounterRate;
  final double? hiredRate;
  final String? appliedAt;
  
  Application({
    required this.id,
    required this.shiftId,
    required this.workerId,
    required this.status,
    this.offeredRate,
    this.venueCounterRate,
    this.hiredRate,
    this.appliedAt,
  });
  
  factory Application.fromJson(Map<String, dynamic> json) {
    return Application(
      id: json['id'],
      shiftId: json['shift_id'],
      workerId: json['worker_id'],
      status: json['status'],
      offeredRate: json['offered_rate']?.toDouble(),
      venueCounterRate: json['venue_counter_rate']?.toDouble(),
      hiredRate: json['hired_rate']?.toDouble(),
      appliedAt: json['applied_at'],
    );
  }
}

class Notification {
  final int id;
  final String title;
  final String message;
  final String? type;
  final int? shiftId;
  final bool isRead;
  final String createdAt;
  
  Notification({
    required this.id,
    required this.title,
    required this.message,
    this.type,
    this.shiftId,
    required this.isRead,
    required this.createdAt,
  });
  
  factory Notification.fromJson(Map<String, dynamic> json) {
    return Notification(
      id: json['id'],
      title: json['title'],
      message: json['message'],
      type: json['type'],
      shiftId: json['shift_id'],
      isRead: json['is_read'] ?? false,
      createdAt: json['created_at'],
    );
  }
}

class ChatMessage {
  final int id;
  final int senderId;
  final String message;
  final String createdAt;
  final bool isRead;

  ChatMessage({
    required this.id,
    required this.senderId,
    required this.message,
    required this.createdAt,
    required this.isRead,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'],
      senderId: json['sender_id'],
      message: json['message'],
      createdAt: json['created_at'],
      isRead: json['is_read'] ?? false,
    );
  }
}

// Availability Calendar
class AvailabilitySlot {
  final int id;
  final int userId;
  final String date;
  final String? startTime;
  final String? endTime;
  final bool isAvailable;
  final String? reason;
  final bool isRecurring;

  AvailabilitySlot({
    required this.id,
    required this.userId,
    required this.date,
    this.startTime,
    this.endTime,
    required this.isAvailable,
    this.reason,
    this.isRecurring = false,
  });

  factory AvailabilitySlot.fromJson(Map<String, dynamic> json) {
    return AvailabilitySlot(
      id: json['id'],
      userId: json['user_id'],
      date: json['date'],
      startTime: json['start_time'],
      endTime: json['end_time'],
      isAvailable: json['is_available'] ?? true,
      reason: json['reason'],
      isRecurring: json['is_recurring'] ?? false,
    );
  }
}

// Dispute Resolution
class Dispute {
  final int id;
  final int shiftId;
  final int reporterId;
  final String disputeType;
  final String description;
  final String status;
  final String? resolution;
  final String? evidenceUrl;
  final String createdAt;
  final String? resolvedAt;

  Dispute({
    required this.id,
    required this.shiftId,
    required this.reporterId,
    required this.disputeType,
    required this.description,
    required this.status,
    this.resolution,
    this.evidenceUrl,
    required this.createdAt,
    this.resolvedAt,
  });

  factory Dispute.fromJson(Map<String, dynamic> json) {
    return Dispute(
      id: json['id'],
      shiftId: json['shift_id'],
      reporterId: json['reporter_id'],
      disputeType: json['dispute_type'],
      description: json['description'],
      status: json['status'],
      resolution: json['resolution'],
      evidenceUrl: json['evidence_url'],
      createdAt: json['created_at'],
      resolvedAt: json['resolved_at'],
    );
  }
}

// Rating & Review
class Rating {
  final int id;
  final int shiftId;
  final int raterId;
  final int ratedUserId;
  final double stars;
  final String? comment;
  final List<String>? tags;
  final String createdAt;

  Rating({
    required this.id,
    required this.shiftId,
    required this.raterId,
    required this.ratedUserId,
    required this.stars,
    this.comment,
    this.tags,
    required this.createdAt,
  });

  factory Rating.fromJson(Map<String, dynamic> json) {
    return Rating(
      id: json['id'],
      shiftId: json['shift_id'],
      raterId: json['rater_id'],
      ratedUserId: json['rated_user_id'],
      stars: json['stars'].toDouble(),
      comment: json['comment'],
      tags: json['tags'] != null ? List<String>.from(json['tags']) : null,
      createdAt: json['created_at'],
    );
  }
}

// Referral Tracking
class Referral {
  final int id;
  final int referrerId;
  final int referredUserId;
  final String referredUserType;
  final double totalEarned;
  final int shiftsCompleted;
  final String status;
  final String createdAt;

  Referral({
    required this.id,
    required this.referrerId,
    required this.referredUserId,
    required this.referredUserType,
    required this.totalEarned,
    required this.shiftsCompleted,
    required this.status,
    required this.createdAt,
  });

  factory Referral.fromJson(Map<String, dynamic> json) {
    return Referral(
      id: json['id'],
      referrerId: json['referrer_id'],
      referredUserId: json['referred_user_id'],
      referredUserType: json['referred_user_type'],
      totalEarned: json['total_earned'].toDouble(),
      shiftsCompleted: json['shifts_completed'],
      status: json['status'],
      createdAt: json['created_at'],
    );
  }
}

// Smart Matching
class MatchScore {
  final int workerId;
  final int shiftId;
  final double matchScore;
  final String? matchReason;
  final double acceptLikelihood;

  MatchScore({
    required this.workerId,
    required this.shiftId,
    required this.matchScore,
    this.matchReason,
    required this.acceptLikelihood,
  });

  factory MatchScore.fromJson(Map<String, dynamic> json) {
    return MatchScore(
      workerId: json['worker_id'],
      shiftId: json['shift_id'],
      matchScore: json['match_score'].toDouble(),
      matchReason: json['match_reason'],
      acceptLikelihood: json['accept_likelihood'].toDouble(),
    );
  }
}
