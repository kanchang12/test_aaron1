import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  // Change this to your backend URL
  static const String baseUrl = 'https://mathtales.top/api'; // All users (worker, venue, admin)
  // static const String baseUrl = 'http://localhost:5000/api'; // iOS simulator
  // static const String baseUrl = 'https://your-backend.com/api'; // Production
  
  final storage = const FlutterSecureStorage();
  
  // Get auth token from storage
  Future<String?> getToken() async {
    return await storage.read(key: 'auth_token');
  }
  
  // Save auth token to storage
  Future<void> saveToken(String token) async {
    await storage.write(key: 'auth_token', value: token);
  }
  
  // Clear auth token (logout)
  Future<void> clearToken() async {
    await storage.delete(key: 'auth_token');
  }
  
  // Get headers with auth token
  Future<Map<String, String>> getHeaders() async {
    final token = await getToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  // Helper to handle API responses and errors
  dynamic _handleResponse(http.Response response) {
    // Check if response is HTML instead of JSON
    if (response.body.trim().startsWith('<') ||
        response.headers['content-type']?.contains('text/html') == true) {
      throw Exception(
        'Server error: The backend returned HTML instead of JSON. '
        'This usually means:\n'
        '1. The backend is not running\n'
        '2. The URL is incorrect\n'
        '3. There is a server error\n\n'
        'Please check that your Flask backend is running at: $baseUrl'
      );
    }

    try {
      final data = jsonDecode(response.body);

      // Check for error responses
      if (response.statusCode >= 400) {
        final errorMessage = data['error'] ?? data['message'] ?? 'Request failed';
        throw Exception(errorMessage);
      }

      return data;
    } catch (e) {
      if (e is Exception) rethrow;
      throw Exception('Invalid response format from server');
    }
  }
  
  // ===========================
  // AUTHENTICATION
  // ===========================
  
  Future<Map<String, dynamic>> register({
    required String email,
    required String password,
    required String name,
    required String role,
    String? phone,
    String? venueName,
    String? referralCode,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'password': password,
          'name': name,
          'role': role,
          'phone': phone,
          'venue_name': venueName,
          if (referralCode != null && referralCode.isNotEmpty) 'referral_code': referralCode,
        }),
      );

      final data = _handleResponse(response);

      if (response.statusCode == 201 || response.statusCode == 200) {
        await saveToken(data['access_token']);
        return data;
      } else {
        throw Exception(data['error'] ?? 'Registration failed');
      }
    } catch (e) {
      rethrow;
    }
  }
  
  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'password': password,
        }),
      );

      final data = _handleResponse(response);

      if (response.statusCode == 200) {
        await saveToken(data['access_token']);
        return data;
      } else {
        throw Exception(data['error'] ?? 'Login failed');
      }
    } catch (e) {
      rethrow;
    }
  }
  
  Future<Map<String, dynamic>> getCurrentUser() async {
    final response = await http.get(
      Uri.parse('$baseUrl/auth/me'),
      headers: await getHeaders(),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      String details = response.body;
      try {
        final data = jsonDecode(response.body);
        details = data['error'] ?? data['message'] ?? response.body;
      } catch (_) {}
      throw Exception('Failed to load user: $details');
    }
  }
  
  // ===========================
  // WORKER ENDPOINTS
  // ===========================
  
  Future<List<Map<String, dynamic>>> searchShifts({
    String? role,
    double? minRate,
    String? startDate,
  }) async {
    final queryParams = <String, String>{};
    if (role != null) queryParams['role'] = role;
    if (minRate != null) queryParams['min_rate'] = minRate.toString();
    if (startDate != null) queryParams['start_date'] = startDate;

    final uri = Uri.parse('$baseUrl/api/shifts/search').replace(queryParameters: queryParams);
    final response = await http.get(uri, headers: await getHeaders());
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['shifts']);
    } else if (response.statusCode == 401) {
      throw Exception('Authentication failed. Please login again.');
    } else {
      String details = 'Failed to load shifts';
      try {
        final data = jsonDecode(response.body);
        details = data['error'] ?? data['msg'] ?? data['message'] ?? details;
      } catch (_) {}
      throw Exception(details);
    }
  }

  Future<List<Map<String, dynamic>>> getShiftRecommendations() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/worker/recommendations'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['recommendations']);
    } else {
      throw Exception('Failed to load recommendations');
    }
  }
  
  Future<Map<String, dynamic>> applyToShift({
    required int shiftId,
    double? counterRate,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/shifts/$shiftId/apply'),
      headers: await getHeaders(),
      body: jsonEncode({
        if (counterRate != null) 'counter_rate': counterRate,
      }),
    );
    
    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to apply');
    }
  }
  
  Future<List<Map<String, dynamic>>> getWorkerApplications() async {
    final response = await http.get(
      Uri.parse('$baseUrl/worker/applications'),
      headers: await getHeaders(),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['applications']);
    } else {
      throw Exception('Failed to load applications');
    }
  }
  
  Future<Map<String, dynamic>> checkinShift({
    required int shiftId,
    double? latitude,
    double? longitude,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/shifts/$shiftId/checkin'),
      headers: await getHeaders(),
      body: jsonEncode({
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
      }),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception(jsonDecode(response.body)['error'] ?? 'Check-in failed');
    }
  }
  
  Future<Map<String, dynamic>> checkoutShift({
    required int shiftId,
    double? latitude,
    double? longitude,
    int? breakMinutes,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/shifts/$shiftId/checkout'),
      headers: await getHeaders(),
      body: jsonEncode({
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        if (breakMinutes != null) 'break_minutes': breakMinutes,
      }),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception(jsonDecode(response.body)['error'] ?? 'Check-out failed');
    }
  }
  
  // ===========================
  // VENUE ENDPOINTS
  // ===========================
  
  Future<List<Map<String, dynamic>>> getVenueShifts() async {
    final response = await http.get(
      Uri.parse('$baseUrl/shifts'),
      headers: await getHeaders(),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['shifts']);
    } else {
      throw Exception('Failed to load shifts');
    }
  }
  
  Future<Map<String, dynamic>> createShift({
    required String role,
    required String startTime,
    required String endTime,
    required double hourlyRate,
    String? description,
    int? numWorkersNeeded,
    List<String>? requiredSkills,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/shifts'),
      headers: await getHeaders(),
      body: jsonEncode({
        'role': role,
        'start_time': startTime,
        'end_time': endTime,
        'hourly_rate': hourlyRate,
        'description': description,
        'num_workers_needed': numWorkersNeeded ?? 1,
        'required_skills': requiredSkills ?? [],
      }),
    );
    
    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to create shift');
    }
  }
  
  Future<Map<String, dynamic>> publishShift(int shiftId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/shifts/$shiftId/publish'),
      headers: await getHeaders(),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to publish shift');
    }
  }
  
  Future<List<Map<String, dynamic>>> getShiftApplications(int shiftId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/shifts/$shiftId/applications'),
      headers: await getHeaders(),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['applications']);
    } else {
      throw Exception('Failed to load applications');
    }
  }
  
  Future<Map<String, dynamic>> hireWorker(int applicationId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/applications/$applicationId/hire'),
      headers: await getHeaders(),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to hire');
    }
  }
  
  Future<Map<String, dynamic>> approveTimesheet({
    required int timesheetId,
    required String action, // approve, query, reject
    String? reason,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/timesheets/$timesheetId/approve'),
      headers: await getHeaders(),
      body: jsonEncode({
        'action': action,
        if (reason != null) 'reason': reason,
      }),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to process timesheet');
    }
  }
  
  // ===========================
  // CHAT & NOTIFICATIONS
  // ===========================
  
  Future<List<Map<String, dynamic>>> getChatMessages(int shiftId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/shifts/$shiftId/chat'),
      headers: await getHeaders(),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['messages']);
    } else {
      throw Exception('Failed to load messages');
    }
  }
  
  Future<Map<String, dynamic>> sendChatMessage({
    required int shiftId,
    required String message,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/shifts/$shiftId/chat'),
      headers: await getHeaders(),
      body: jsonEncode({'message': message}),
    );
    
    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to send message');
    }
  }
  
  Future<List<Map<String, dynamic>>> getNotifications() async {
    final response = await http.get(
      Uri.parse('$baseUrl/notifications'),
      headers: await getHeaders(),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['notifications']);
    } else {
      throw Exception('Failed to load notifications');
    }
  }
  
  Future<void> markNotificationRead(int notificationId) async {
    await http.post(
      Uri.parse('$baseUrl/notifications/$notificationId/read'),
      headers: await getHeaders(),
    );
  }

  Future<Map<String, dynamic>> getNotificationPreferences() async {
    final response = await http.get(
      Uri.parse('$baseUrl/notifications/preferences'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load notification preferences');
    }
  }

  Future<Map<String, dynamic>> updateNotificationPreferences(
      Map<String, dynamic> preferences) async {
    final response = await http.put(
      Uri.parse('$baseUrl/notifications/preferences'),
      headers: await getHeaders(),
      body: jsonEncode(preferences),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to update notification preferences');
    }
  }

  // ===========================
  // CV UPLOAD & PARSING
  // ===========================

  Future<Map<String, dynamic>> uploadCV(String filePath) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/worker/cv/upload'),
    );
    request.headers.addAll(await getHeaders());
    request.files.add(await http.MultipartFile.fromPath('cv', filePath));

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to upload CV');
    }
  }

  Future<Map<String, dynamic>> parseCV(String cvUrl) async {
    final response = await http.post(
      Uri.parse('$baseUrl/worker/cv/parse'),
      headers: await getHeaders(),
      body: jsonEncode({'cv_url': cvUrl}),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to parse CV');
    }
  }

  Future<Map<String, dynamic>> updateProfile(
      Map<String, dynamic> updates) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/auth/profile'),
      headers: await getHeaders(),
      body: jsonEncode(updates),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to update profile');
    }
  }

  Future<Map<String, dynamic>> uploadProfilePhoto(String filePath) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/auth/profile/photo'),
    );
    request.headers.addAll(await getHeaders());
    request.files.add(await http.MultipartFile.fromPath('photo', filePath));

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to upload profile photo');
    }
  }

  // ===========================
  // ID VERIFICATION
  // ===========================

  Future<Map<String, dynamic>> getVerificationStatus() async {
    final response = await http.get(
      Uri.parse('$baseUrl/worker/verification'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load verification status');
    }
  }

  Future<Map<String, dynamic>> uploadVerificationDocument(
    String filePath,
    String documentType,
  ) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/worker/verification/upload'),
    );
    request.headers.addAll(await getHeaders());
    request.fields['document_type'] = documentType;
    request.files.add(await http.MultipartFile.fromPath('document', filePath));

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to upload verification document');
    }
  }

  Future<Map<String, dynamic>> submitForVerification() async {
    final response = await http.post(
      Uri.parse('$baseUrl/worker/verification/submit'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to submit for verification');
    }
  }

  // ===========================
  // AVAILABILITY CALENDAR
  // ===========================

  Future<List<Map<String, dynamic>>> getAvailability() async {
    final response = await http.get(
      Uri.parse('$baseUrl/worker/availability'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['availability']);
    } else {
      throw Exception('Failed to load availability');
    }
  }

  Future<Map<String, dynamic>> setAvailability(
      String date, bool isAvailable) async {
    final response = await http.post(
      Uri.parse('$baseUrl/worker/availability'),
      headers: await getHeaders(),
      body: jsonEncode({
        'date': date,
        'is_available': isAvailable,
      }),
    );

    if (response.statusCode == 200 || response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to set availability');
    }
  }

  // ===========================
  // REFERRAL SYSTEM
  // ===========================

  Future<List<Map<String, dynamic>>> getReferrals() async {
    final response = await http.get(
      Uri.parse('$baseUrl/referrals'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['referrals']);
    } else {
      throw Exception('Failed to load referrals');
    }
  }

  Future<Map<String, dynamic>> referVenue({
    required String venueName,
    required String managerName,
    required String managerEmail,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/referrals/venue'),
      headers: await getHeaders(),
      body: jsonEncode({
        'venue_name': venueName,
        'manager_name': managerName,
        'manager_email': managerEmail,
      }),
    );

    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to refer venue');
    }
  }

  Future<Map<String, dynamic>> withdrawReferralBalance() async {
    final response = await http.post(
      Uri.parse('$baseUrl/referrals/withdraw'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to withdraw balance');
    }
  }

  // ===========================
  // DISPUTE RESOLUTION
  // ===========================

  Future<List<Map<String, dynamic>>> getDisputes({int? shiftId}) async {
    final queryParams = shiftId != null ? {'shift_id': shiftId.toString()} : null;
    final uri = Uri.parse('$baseUrl/disputes')
        .replace(queryParameters: queryParams);

    final response = await http.get(uri, headers: await getHeaders());

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['disputes']);
    } else {
      throw Exception('Failed to load disputes');
    }
  }

  Future<Map<String, dynamic>> createDispute({
    required int shiftId,
    required String disputeType,
    required String description,
    String? evidencePath,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/disputes'),
    );
    request.headers.addAll(await getHeaders());
    request.fields['shift_id'] = shiftId.toString();
    request.fields['dispute_type'] = disputeType;
    request.fields['description'] = description;

    if (evidencePath != null) {
      request.files
          .add(await http.MultipartFile.fromPath('evidence', evidencePath));
    }

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to create dispute');
    }
  }

  // ===========================
  // SHIFT BOOSTING & STRIPE
  // ===========================

  Future<Map<String, dynamic>> createBoostPaymentIntent({
    required int shiftId,
    required int amount,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/payments/boost'),
      headers: await getHeaders(),
      body: jsonEncode({
        'shift_id': shiftId,
        'amount': amount,
      }),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to create payment intent');
    }
  }

  Future<Map<String, dynamic>> activateShiftBoost(int shiftId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/shifts/$shiftId/boost'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to activate boost');
    }
  }

  // ===========================
  // MULTI-VENUE MANAGEMENT
  // ===========================

  Future<List<Map<String, dynamic>>> getVenues() async {
    final response = await http.get(
      Uri.parse('$baseUrl/venues'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['venues']);
    } else {
      throw Exception('Failed to load venues');
    }
  }

  Future<Map<String, dynamic>> createVenue({
    required String name,
    required String address,
    String? phone,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/venues'),
      headers: await getHeaders(),
      body: jsonEncode({
        'name': name,
        'address': address,
        'phone': phone,
      }),
    );

    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to create venue');
    }
  }

  Future<List<Map<String, dynamic>>> getTeamMembers() async {
    final response = await http.get(
      Uri.parse('$baseUrl/venues/team'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['team_members']);
    } else {
      throw Exception('Failed to load team members');
    }
  }

  Future<Map<String, dynamic>> inviteTeamMember({
    required String name,
    required String email,
    required String role,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/venues/team/invite'),
      headers: await getHeaders(),
      body: jsonEncode({
        'name': name,
        'email': email,
        'role': role,
      }),
    );

    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to invite team member');
    }
  }

  // ===========================
  // SMART MATCHING
  // ===========================

  Future<List<Map<String, dynamic>>> getSmartMatches(int shiftId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/shifts/$shiftId/matches'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['matches']);
    } else {
      throw Exception('Failed to load matches');
    }
  }

  Future<Map<String, dynamic>> inviteWorkerToShift(
      int shiftId, int workerId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/shifts/$shiftId/invite'),
      headers: await getHeaders(),
      body: jsonEncode({'worker_id': workerId}),
    );

    if (response.statusCode == 200 || response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to invite worker');
    }
  }

  // ===========================
  // RATINGS & RELIABILITY
  // ===========================

  Future<Map<String, dynamic>> rateUser({
    required int shiftId,
    required int ratedUserId,
    required double stars,
    String? comment,
    List<String>? tags,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/ratings'),
      headers: await getHeaders(),
      body: jsonEncode({
        'shift_id': shiftId,
        'rated_user_id': ratedUserId,
        'stars': stars,
        'comment': comment,
        'tags': tags,
      }),
    );

    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to submit rating');
    }
  }

  Future<List<Map<String, dynamic>>> getUserRatings(int userId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/users/$userId/ratings'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return List<Map<String, dynamic>>.from(data['ratings']);
    } else {
      throw Exception('Failed to load ratings');
    }
  }

  Future<void> updateEmail(String newEmail) async {
    final response = await http.put(
      Uri.parse('$baseUrl/user/email'),
      headers: await getHeaders(),
      body: jsonEncode({'email': newEmail}),
    );
    if (response.statusCode != 200) {
      final data = jsonDecode(response.body);
      throw Exception(data['error'] ?? 'Failed to update email');
    }
  }

  // Venue Profile Methods
  Future<Map<String, dynamic>> getVenueProfile() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/venue/profile'),
      headers: await getHeaders(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else if (response.statusCode == 401) {
      throw Exception('Authentication failed. Please login again.');
    } else {
      try {
        final data = jsonDecode(response.body);
        throw Exception(data['error'] ?? data['msg'] ?? 'Failed to load venue profile');
      } catch (e) {
        throw Exception('Failed to load venue profile');
      }
    }
  }

  Future<void> updateVenueProfile({
    String? venueName,
    String? businessAddress,
    String? industryType,
    String? contactEmail,
    String? contactPhone,
  }) async {
    final response = await http.put(
      Uri.parse('$baseUrl/api/venue/profile'),
      headers: await getHeaders(),
      body: jsonEncode({
        if (venueName != null) 'venue_name': venueName,
        if (businessAddress != null) 'business_address': businessAddress,
        if (industryType != null) 'industry_type': industryType,
        if (contactEmail != null) 'contact_email': contactEmail,
        if (contactPhone != null) 'contact_phone': contactPhone,
      }),
    );

    if (response.statusCode == 401) {
      throw Exception('Authentication failed. Please login again.');
    } else if (response.statusCode != 200) {
      try {
        final data = jsonDecode(response.body);
        throw Exception(data['error'] ?? data['msg'] ?? 'Failed to update profile');
      } catch (e) {
        throw Exception('Failed to update profile');
      }
    }
  }
}
