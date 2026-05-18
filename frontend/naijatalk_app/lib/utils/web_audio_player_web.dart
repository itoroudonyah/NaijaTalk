import 'dart:html' as html;

html.AudioElement? _audioElement;

Future<void> playWebAudioFromBase64(String base64Audio) async {
  final dataUrl = 'data:audio/wav;base64,$base64Audio';

  _audioElement?.pause();
  _audioElement = html.AudioElement(dataUrl);
  await _audioElement!.play();
}
