import base64
import tempfile
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import torch
from pydub import AudioSegment
from ..models.asr_model import NATLASASRModel
from ..models.translation_model import NLLBTranslationModel
from ..models.tts_model import ConfigurableTTSModel


class AudioProcessor:
    def __init__(self):
        self.asr_model = NATLASASRModel()
        self.translation_model = NLLBTranslationModel()
        self.tts_model = ConfigurableTTSModel()
        self._executor = ThreadPoolExecutor(max_workers=4)
        print("🎤 NaijaTalk Audio Processor Initialized")

    def warmup_models(self):
        print("🔄 Skipping preload - models load on first request")

    async def transcribe_and_translate(self, audio_bytes: bytes, source_lang: str, target_lang: str):
        print(f"Processing audio: {source_lang} → {target_lang}")

        wav_path = None
        tmp_path = None
        try:
            tmp_path, wav_path = self._prepare_wav(audio_bytes)
            transcribed_text = await self.speech_to_text(wav_path, source_lang)
            translated_text = await self.translate_text(transcribed_text, source_lang, target_lang)
            print(f"📝 Transcribed: {transcribed_text}")
            print(f"🔄 Translated: {translated_text}")

            return {
                "text": translated_text,
                "original_text": transcribed_text,
            }
        finally:
            self._cleanup_temp_files(tmp_path, wav_path)

    async def synthesize_translation_audio(
        self,
        text: str,
        language: str,
        tts_provider: str | None = None,
    ) -> str:
        audio_output = await self.text_to_speech(text, language, tts_provider)
        print(f"🔊 TTS bytes: {len(audio_output)}")
        return base64.b64encode(audio_output).decode("utf-8")

    def _detect_audio_format(self, audio_bytes: bytes):
        if audio_bytes.startswith(b"RIFF") and audio_bytes[8:12] == b"WAVE":
            return ".wav", "wav"
        return ".webm", "webm"

    def _prepare_wav(self, audio_bytes: bytes):
        file_suffix, input_format = self._detect_audio_format(audio_bytes)

        with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        audio = AudioSegment.from_file(tmp_path, format=input_format)
        wav_path = f"{tmp_path}.wav"
        audio.export(wav_path, format="wav")
        return tmp_path, wav_path

    def _cleanup_temp_files(self, tmp_path, wav_path):
        try:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
            if wav_path:
                Path(wav_path).unlink(missing_ok=True)
        except Exception:
            pass

    async def speech_to_text(self, audio_path: str, language: str) -> str:
        return await asyncio.to_thread(
            self.asr_model.transcribe,
            audio_path,
            language,
        )

    async def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        return await asyncio.to_thread(
            self.translation_model.translate,
            text,
            source_lang,
            target_lang,
        )

    async def text_to_speech(
        self,
        text: str,
        language: str,
        tts_provider: str | None = None,
    ) -> bytes:
        return await asyncio.to_thread(
            self.tts_model.synthesize,
            text,
            language,
            tts_provider,
        )
