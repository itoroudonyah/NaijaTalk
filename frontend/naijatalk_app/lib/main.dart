import 'package:flutter/material.dart';
import 'screens/splash_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NaijaTalkApp());
}

class NaijaTalkApp extends StatelessWidget {
  const NaijaTalkApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NaijaTalk',
      theme: ThemeData(
        primaryColor: const Color(0xFF008753), // Nigerian green
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF008753),
          secondary: const Color(0xFF001F3F), // Deep blue
        ),
        useMaterial3: true,
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF008753),
          foregroundColor: Colors.white,
          elevation: 0,
        ),
        fontFamily: 'Poppins', // Add custom font if available
      ),
      home: const SplashScreen(),
      debugShowCheckedModeBanner: false,
    );
  }
}
