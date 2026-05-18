import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:audioplayers/audioplayers.dart';
import 'dart:convert';
import 'dart:typed_data';
import 'dart:async';
import '../utils/web_audio_player.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const RecordConfig _nativeRecordConfig = RecordConfig(
    encoder: AudioEncoder.wav,
    sampleRate: 16000,
    numChannels: 1,
  );
  static const RecordConfig _webRecordConfig = RecordConfig(
    encoder: AudioEncoder.pcm16bits,
    sampleRate: 16000,
    numChannels: 1,
  );

  final AudioRecorder _audioRecorder = AudioRecorder();
  final AudioPlayer _audioPlayer = AudioPlayer();
  WebSocketChannel? _channel;

  bool _isRecording = false;
  bool _isConnected = false;
  bool _isProcessing = false;
  bool _isGeneratingAudio = false;
  String _translatedText = "";
  String _originalText = "";
  String _connectionStatus = "Disconnected";
  String? _latestAudioBase64;

  String _sourceLanguage = "en";
  String _targetLanguage = "yo";
  String _ttsProvider = "yarngpt";

  Timer? _recordingTimer;
  int _recordingDuration = 0;
  StreamSubscription<Uint8List>? _recordingStreamSubscription;
  final BytesBuilder _webRecordingBytes = BytesBuilder(copy: false);

  final Map<String, Map<String, String>> _languages = {
    "en": {"name": "English", "flag": "🇬🇧", "native": "English"},
    "yo": {"name": "Yoruba", "flag": "🇳🇬", "native": "Èdè Yorùbá"},
    "ha": {"name": "Hausa", "flag": "🇳🇬", "native": "Harshen Hausa"},
    "ig": {"name": "Igbo", "flag": "🇳🇬", "native": "Asụsụ Igbo"}
  };

  final Map<String, String> _ttsProviders = {
    "yarngpt": "Nigerian TTS",
    "google": "Google Cloud TTS",
  };

  @override
  void initState() {
    super.initState();
    _connectWebSocket();
    _requestPermissions();
  }

  Future<void> _requestPermissions() async {
    final hasPermission = await _audioRecorder.hasPermission();
    if (hasPermission) {
      print("Microphone permission granted");
    } else {
      print("Microphone permission denied");
    }
  }

  Future<void> _connectWebSocket() async {
    const String wsUrl = "ws://localhost:8000/ws/translate/naijatalk_client";

    setState(() {
      _connectionStatus = "Connecting...";
    });

    try {
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));

      _channel!.stream.listen((message) {
        try {
          var data = jsonDecode(message);
          if (data["type"] == "translation") {
            setState(() {
              _originalText = data["original_text"] ?? "";
              _translatedText = data["translated_text"];
              _isProcessing = false;
              _isGeneratingAudio = true;
              _connectionStatus = "Connected";
            });
          } else if (data["type"] == "translation_audio") {
            final audio = data["audio"];
            if (audio != null && audio.isNotEmpty) {
              setState(() {
                _latestAudioBase64 = audio;
                _isGeneratingAudio = false;
              });
              _playAudio(audio);
            } else {
              setState(() {
                _isGeneratingAudio = false;
              });
            }
          } else if (data["type"] == "error") {
            setState(() {
              _connectionStatus = "Error: ${data["message"]}";
              _isProcessing = false;
              _isGeneratingAudio = false;
            });
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text("Error: ${data["message"]}")),
              );
            }
          }
        } catch (e) {
          print("Error parsing message: $e");
        }
      }, onError: (error) {
        setState(() {
          _connectionStatus = "Disconnected";
          _isConnected = false;
        });
        print("WebSocket error: $error");
      }, onDone: () {
        setState(() {
          _connectionStatus = "Disconnected";
          _isConnected = false;
        });
        print("WebSocket connection closed");
      });

      setState(() {
        _isConnected = true;
        _connectionStatus = "Connected";
      });
    } catch (e) {
      setState(() {
        _connectionStatus = "Connection failed";
      });
      print("Connection error: $e");
    }
  }

  void _playAudio(String base64Audio) {
    try {
      if (kIsWeb) {
        playWebAudioFromBase64(base64Audio);
        return;
      }

      final audioBytes = base64Decode(base64Audio);
      _audioPlayer.play(BytesSource(audioBytes));
    } catch (e) {
      print("Error playing audio: $e");
    }
  }

  Future<void> _startRecording() async {
    if (!_isConnected) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content:
                  Text("Not connected to server. Please check connection.")),
        );
      }
      return;
    }

    if (kIsWeb) {
      await _startWebRecording();
      return;
    }

    if (!await _audioRecorder.hasPermission()) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Microphone permission not granted")),
        );
      }
      return;
    }

    try {
      await _audioRecorder.start(_nativeRecordConfig,
          path: '/tmp/naijatalk_recording.wav');

      setState(() {
        _isRecording = true;
        _recordingDuration = 0;
        _originalText = "";
        _translatedText = "";
      });

      _recordingTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (mounted) {
          setState(() {
            _recordingDuration++;
          });
        }
      });

      // Start sending audio chunks
      _sendAudioChunks();
    } catch (e) {
      print("Error starting recording: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Error starting recording: $e")),
        );
      }
    }
  }

  Future<void> _startWebRecording() async {
    if (!await _audioRecorder.hasPermission()) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Microphone permission not granted")),
        );
      }
      return;
    }

    try {
      _webRecordingBytes.clear();
      final stream = await _audioRecorder.startStream(_webRecordConfig);
      await _recordingStreamSubscription?.cancel();
      _recordingStreamSubscription = stream.listen((chunk) {
        _webRecordingBytes.add(chunk);
      });

      setState(() {
        _isRecording = true;
        _isProcessing = false;
        _isGeneratingAudio = false;
        _recordingDuration = 0;
        _originalText = "";
        _translatedText = "";
        _latestAudioBase64 = null;
      });

      _recordingTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (mounted) {
          setState(() {
            _recordingDuration++;
          });
        }
      });
    } catch (e) {
      print("Error starting web recording: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Error starting recording: $e")),
        );
      }
    }
  }

  Future<void> _sendAudioChunks() async {
    // Real-time chunking is only implemented on native platforms once the
    // recorder output is moved off the local file system dependency.
  }

  Future<void> _stopRecording() async {
    try {
      await _audioRecorder.stop();
      await _recordingStreamSubscription?.cancel();
      _recordingStreamSubscription = null;
      _recordingTimer?.cancel();

      final webAudioBytes =
          kIsWeb ? _buildWavBytes(_webRecordingBytes.takeBytes()) : null;

      setState(() {
        _isRecording = false;
        _isProcessing = webAudioBytes != null && webAudioBytes.isNotEmpty;
        _isGeneratingAudio = false;
      });

      if (webAudioBytes != null && webAudioBytes.isNotEmpty) {
        _channel?.sink.add(jsonEncode({
          "type": "audio",
          "data": base64Encode(webAudioBytes),
          "source_lang": _sourceLanguage,
          "target_lang": _targetLanguage,
          "tts_provider": _ttsProvider,
          "final_chunk": true
        }));
      }
    } catch (e) {
      print("Error stopping recording: $e");
      setState(() {
        _isRecording = false;
        _isProcessing = false;
        _isGeneratingAudio = false;
      });
    }
  }

  void _replayLatestAudio() {
    final audio = _latestAudioBase64;
    if (audio == null || audio.isEmpty) {
      return;
    }
    _playAudio(audio);
  }

  void _swapLanguages() {
    setState(() {
      String temp = _sourceLanguage;
      _sourceLanguage = _targetLanguage;
      _targetLanguage = temp;
      _originalText = "";
      _translatedText = "";
    });
  }

  Uint8List _buildWavBytes(Uint8List pcmBytes) {
    final byteData = ByteData(44 + pcmBytes.length);

    byteData.setUint32(0, 0x52494646, Endian.big); // RIFF
    byteData.setUint32(4, 36 + pcmBytes.length, Endian.little);
    byteData.setUint32(8, 0x57415645, Endian.big); // WAVE
    byteData.setUint32(12, 0x666d7420, Endian.big); // fmt
    byteData.setUint32(16, 16, Endian.little);
    byteData.setUint16(20, 1, Endian.little); // PCM
    byteData.setUint16(22, 1, Endian.little); // mono
    byteData.setUint32(24, 16000, Endian.little);
    byteData.setUint32(28, 16000 * 2, Endian.little); // byte rate
    byteData.setUint16(32, 2, Endian.little); // block align
    byteData.setUint16(34, 16, Endian.little); // bits per sample
    byteData.setUint32(36, 0x64617461, Endian.big); // data
    byteData.setUint32(40, pcmBytes.length, Endian.little);

    final wavBytes = byteData.buffer.asUint8List();
    wavBytes.setRange(44, wavBytes.length, pcmBytes);
    return wavBytes;
  }

  Future<void> _toggleWebRecording() async {
    if (_isRecording) {
      await _stopRecording();
    } else {
      await _startRecording();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("NaijaTalk"),
        centerTitle: true,
        actions: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            margin: const EdgeInsets.only(right: 8),
            decoration: BoxDecoration(
              color: _isConnected ? Colors.green : Colors.red,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  _isConnected ? Icons.wifi : Icons.wifi_off,
                  color: Colors.white,
                  size: 16,
                ),
                const SizedBox(width: 4),
                Text(
                  _connectionStatus,
                  style: const TextStyle(color: Colors.white, fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          children: [
            // Language Selection Row
            Row(
              children: [
                Expanded(
                  child: _buildLanguageCard(
                    _languages[_sourceLanguage]!,
                    "From",
                    _sourceLanguage,
                    (value) => setState(() => _sourceLanguage = value!),
                  ),
                ),
                IconButton(
                  onPressed: _swapLanguages,
                  icon: const Icon(Icons.swap_horiz, size: 30),
                  color: const Color(0xFF008753),
                ),
                Expanded(
                  child: _buildLanguageCard(
                    _languages[_targetLanguage]!,
                    "To",
                    _targetLanguage,
                    (value) => setState(() => _targetLanguage = value!),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 30),

            _buildTtsSelector(),

            const SizedBox(height: 24),

            // Recording Status
            if (_isRecording)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: const BoxDecoration(
                        color: Colors.red,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      "Recording: ${_recordingDuration}s",
                      style: const TextStyle(color: Colors.red),
                    ),
                  ],
                ),
              ),

            const SizedBox(height: 20),

            // Record Button
            GestureDetector(
              onTap: kIsWeb ? _toggleWebRecording : null,
              onLongPressStart: kIsWeb ? null : (_) => _startRecording(),
              onLongPressEnd: kIsWeb ? null : (_) => _stopRecording(),
              child: Container(
                width: 140,
                height: 140,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    colors: _isRecording
                        ? [Colors.red, Colors.red.shade700]
                        : [const Color(0xFF008753), const Color(0xFF004D2E)],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color:
                          (_isRecording ? Colors.red : const Color(0xFF008753))
                              .withOpacity(0.4),
                      spreadRadius: 5,
                      blurRadius: 15,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      _isRecording ? Icons.mic : Icons.mic_none,
                      size: 50,
                      color: Colors.white,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _isRecording
                          ? "Recording..."
                          : (kIsWeb ? "Click to Speak" : "Hold to Speak"),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 20),

            // Processing Indicator
            if (_isProcessing)
              const Padding(
                padding: EdgeInsets.all(16.0),
                child: CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF008753)),
                ),
              ),

            const SizedBox(height: 20),

            // Translation Output
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.grey[100],
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.grey[300]!),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          _languages[_sourceLanguage]!["flag"]!,
                          style: const TextStyle(fontSize: 20),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          "Original (${_languages[_sourceLanguage]!["name"]})",
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Expanded(
                      flex: 1,
                      child: SingleChildScrollView(
                        child: Text(
                          _originalText.isEmpty
                              ? "Your speech will appear here"
                              : _originalText,
                          style: const TextStyle(fontSize: 16),
                        ),
                      ),
                    ),
                    const Divider(height: 20),
                    Row(
                      children: [
                        Text(
                          _languages[_targetLanguage]!["flag"]!,
                          style: const TextStyle(fontSize: 20),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          "Translation (${_languages[_targetLanguage]!["name"]})",
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: const Color(0xFF008753),
                          ),
                        ),
                        const Spacer(),
                        if (_isGeneratingAudio)
                          const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        IconButton(
                          onPressed: _latestAudioBase64 == null
                              ? null
                              : _replayLatestAudio,
                          icon: const Icon(Icons.play_arrow),
                          color: const Color(0xFF008753),
                          tooltip: "Play translation",
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Expanded(
                      flex: 1,
                      child: SingleChildScrollView(
                        child: Text(
                          _translatedText.isEmpty
                              ? "Translation will appear here"
                              : _translatedText,
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLanguageCard(Map<String, String> lang, String label, String code,
      Function(String?) onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            fontSize: 12,
            color: Colors.grey,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey[300]!),
            borderRadius: BorderRadius.circular(12),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: code,
              isExpanded: true,
              items: _languages.entries.map((entry) {
                return DropdownMenuItem(
                  value: entry.key,
                  child: Row(
                    children: [
                      Text(entry.value["flag"]!,
                          style: const TextStyle(fontSize: 20)),
                      const SizedBox(width: 8),
                      Text(entry.value["name"]!),
                    ],
                  ),
                );
              }).toList(),
              onChanged: onChanged,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildTtsSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          "TTS voice",
          style: TextStyle(
            fontWeight: FontWeight.bold,
            fontSize: 12,
            color: Colors.grey,
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: SegmentedButton<String>(
            segments: _ttsProviders.entries.map((entry) {
              return ButtonSegment<String>(
                value: entry.key,
                icon: Icon(
                  entry.key == "google"
                      ? Icons.cloud_outlined
                      : Icons.record_voice_over,
                ),
                label: Text(entry.value),
              );
            }).toList(),
            selected: {_ttsProvider},
            onSelectionChanged: _isRecording
                ? null
                : (selection) {
                    setState(() {
                      _ttsProvider = selection.first;
                      _latestAudioBase64 = null;
                      _isGeneratingAudio = false;
                    });
                  },
            style: ButtonStyle(
              visualDensity: VisualDensity.compact,
              foregroundColor: WidgetStateProperty.resolveWith((states) {
                if (states.contains(WidgetState.selected)) {
                  return Colors.white;
                }
                return const Color(0xFF008753);
              }),
              backgroundColor: WidgetStateProperty.resolveWith((states) {
                if (states.contains(WidgetState.selected)) {
                  return const Color(0xFF008753);
                }
                return Colors.white;
              }),
            ),
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _channel?.sink.close();
    _recordingStreamSubscription?.cancel();
    _audioRecorder.dispose();
    _audioPlayer.dispose();
    _recordingTimer?.cancel();
    super.dispose();
  }
}
