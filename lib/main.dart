import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/api_service.dart';
import 'screens/auth/login_screen.dart';
import 'screens/worker/worker_home.dart';
import 'screens/venue/venue_home.dart';

void main() {
  runApp(const DiiscoApp());
}

class DiiscoApp extends StatelessWidget {
  const DiiscoApp({super.key});

  @override
  Widget build(BuildContext context) {
    return Provider(
      create: (_) => ApiService(),
      child: MaterialApp(
        title: 'Diisco',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
  useMaterial3: true,
  brightness: Brightness.light,

  // 1. Background Color (Light)
  scaffoldBackgroundColor: const Color(0xFFF1F8F4),

  // 2. Primary & Accent Colors (Light Green)
  colorScheme: ColorScheme.fromSeed(
    seedColor: const Color(0xFF4CAF50),
    brightness: Brightness.light,
    primary: const Color(0xFF4CAF50),     // Light Green
    secondary: const Color(0xFF66BB6A),   // Lighter Green
    surface: Colors.white,                // Card Background
    onPrimary: Colors.white,              // Text on green
    onSurface: Colors.black87,            // Text on white
  ),

  // 3. Premium Rounded Buttons
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: const Color(0xFF4CAF50), // Light Green Button
      foregroundColor: Colors.white,             // White Text
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
    ),
  ),

  // 4. Input Fields
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: Colors.white,
    labelStyle: const TextStyle(color: Colors.black54),
    hintStyle: const TextStyle(color: Colors.black38),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFE0E0E0)),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFE0E0E0)),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFF4CAF50), width: 2),
    ),
  ),

  // 5. Text Theme
  textTheme: const TextTheme(
    bodyLarge: TextStyle(color: Colors.black87),
    bodyMedium: TextStyle(color: Colors.black87),
    titleLarge: TextStyle(color: Colors.black87, fontWeight: FontWeight.bold),
  ),
),
        home: const SplashScreen(),
      ),
    );
  }
}

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    final api = Provider.of<ApiService>(context, listen: false);
    final token = await api.getToken();

    await Future.delayed(const Duration(seconds: 2));

    if (!mounted) return;

    if (token != null) {
      try {
        final user = await api.getCurrentUser();
        if (!mounted) return;
        
        if (user['role'] == 'worker') {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(builder: (_) => const WorkerHomeScreen()),
          );
        } else if (user['role'] == 'venue') {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(builder: (_) => const VenueHomeScreen()),
          );
        }
      } catch (e) {
        await api.clearToken();
        if (!mounted) return;
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const LoginScreen()),
        );
      }
    } else {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.work_outline,
              size: 100,
              color: Theme.of(context).primaryColor,
            ),
            const SizedBox(height: 24),
            Text(
              'Diisco',
              style: TextStyle(
                fontSize: 48,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).primaryColor,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Hospitality Gigs Made Easy',
              style: TextStyle(fontSize: 16, color: Colors.black54),
            ),
            const SizedBox(height: 48),
            CircularProgressIndicator(
              color: Theme.of(context).primaryColor,
            ),
          ],
        ),
      ),
    );
  }
}