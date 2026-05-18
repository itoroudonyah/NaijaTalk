from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path
from typing import Dict

import gdown
import requests


def _get_torch_deps():
    import torch
    import torchaudio
    from huggingface_hub import hf_hub_download
    from transformers import AutoModelForCausalLM
    return torch, torchaudio, hf_hub_download, AutoModelForCausalLM


class AbenaTTSModel:
    """Abena AI Text-to-Speech adapter."""

    API_URL = os.getenv(
        "ABENA_TTS_API_URL",
        "https://abena.mobobi.com/playground/api/v1/tts/synthesize/",
    )
    VOICE_NAMES: Dict[str, str] = {
        "en": os.getenv("ABENA_TTS_VOICE_EN", "en-ng-chioma"),
        "yo": os.getenv("ABENA_TTS_VOICE_YO", "Folami"),
        "ha": os.getenv("ABENA_TTS_VOICE_HA", "Abubakar"),
    }

    def __init__(self) -> None:
        self._api_key = os.getenv("ABENA_API_KEY")

    def is_available(self, language: str) -> bool:
        return bool(self._api_key) and language in self.VOICE_NAMES

    def synthesize(self, text: str, language: str) -> bytes:
        if not self._api_key:
            raise RuntimeError("ABENA_API_KEY is not configured.")
        if language not in self.VOICE_NAMES:
            raise RuntimeError(f"Abena TTS does not support language '{language}' in this integration.")

        voice_name = self.VOICE_NAMES[language]
        payload = {
            "text": text,
            "language_code": voice_name,
            "voice": voice_name,
        }

        response = requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )

        if not response.ok:
            raise RuntimeError(
                "Abena TTS request failed "
                f"(status={response.status_code}, payload={payload}, body={response.text})"
            )

        content_type = (response.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            return self._extract_audio_from_json(response.json())

        return response.content

    def _extract_audio_from_json(self, payload: dict) -> bytes:
        candidates = [
            payload.get("audio"),
            payload.get("audio_base64"),
            payload.get("audio_url"),
            payload.get("url"),
        ]

        data = payload.get("data")
        if isinstance(data, dict):
            candidates.extend([
                data.get("audio"),
                data.get("audio_base64"),
                data.get("audio_url"),
                data.get("url"),
            ])

        for candidate in candidates:
            audio_bytes = self._resolve_audio_candidate(candidate)
            if audio_bytes is not None:
                return audio_bytes

        raise RuntimeError(
            f"Abena TTS JSON response did not include a supported audio field: {payload}"
        )

    def _resolve_audio_candidate(self, candidate):
        if not candidate or not isinstance(candidate, str):
            return None

        if candidate.startswith("data:"):
            _, encoded = candidate.split(",", 1)
            return base64.b64decode(encoded)

        if candidate.startswith("http://") or candidate.startswith("https://"):
            audio_response = requests.get(candidate, timeout=120)
            audio_response.raise_for_status()
            return audio_response.content

        try:
            return base64.b64decode(candidate, validate=True)
        except Exception:
            return None


class GoogleCloudTTSModel:
    """Google Cloud Text-to-Speech adapter."""

    LANGUAGE_CODES: Dict[str, str] = {
        "en": os.getenv("GOOGLE_TTS_LANG_EN", "en-NG"),
        "yo": os.getenv("GOOGLE_TTS_LANG_YO", "yo-NG"),
        "ha": os.getenv("GOOGLE_TTS_LANG_HA", "ha-NG"),
        "ig": os.getenv("GOOGLE_TTS_LANG_IG", "ig-NG"),
    }

    VOICE_NAMES: Dict[str, str] = {
        "en": os.getenv("GOOGLE_TTS_VOICE_EN", ""),
        "yo": os.getenv("GOOGLE_TTS_VOICE_YO", ""),
        "ha": os.getenv("GOOGLE_TTS_VOICE_HA", ""),
        "ig": os.getenv("GOOGLE_TTS_VOICE_IG", ""),
    }

    def synthesize(self, text: str, language: str) -> bytes:
        if not text.strip():
            return b""

        try:
            from google.cloud import texttospeech
        except ImportError as exc:
            raise RuntimeError(
                "Google Cloud TTS requires google-cloud-texttospeech. "
                "Install backend requirements before selecting Google TTS."
            ) from exc

        language_code = self.LANGUAGE_CODES.get(language, self.LANGUAGE_CODES["en"])
        voice_name = self.VOICE_NAMES.get(language, "")
        client = texttospeech.TextToSpeechClient()

        voice_params = {
            "language_code": language_code,
            "ssml_gender": texttospeech.SsmlVoiceGender.NEUTRAL,
        }
        if voice_name:
            voice_params["name"] = voice_name

        response = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(**voice_params),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            ),
        )
        return response.audio_content


class YarnGPT2TTSModel:
    """Lazy-loaded wrapper around the YarnGPT2 TTS stack."""

    MODEL_ID = "saheedniyi/YarnGPT2"
    WAVTOKENIZER_REPO_ID = "novateur/WavTokenizer-medium-speech-75token"
    WAVTOKENIZER_CONFIG_FILE = (
        "wavtokenizer_mediumdata_frame75_3s_nq1_code4096_dim512_kmeans200_attn.yaml"
    )
    WAVTOKENIZER_MODEL_FILE_ID = "1-ASeEkrn4HY49yZWHTASgfGFNXdVnLTt"
    SAMPLE_RATE = 24000

    LANGUAGE_NAMES: Dict[str, str] = {
        "en": "english",
        "yo": "yoruba",
        "ig": "igbo",
        "ha": "hausa",
    }

    DEFAULT_SPEAKERS: Dict[str, str] = {
        "en": "idera",
        "yo": "yoruba_male2",
        "ig": "igbo_male2",
        "ha": "hausa_male2",
    }
    GENERATION_CONFIGS: Dict[str, Dict[str, object]] = {
        "en": {"do_sample": False, "repetition_penalty": 1.1, "max_length": 4000},
        "yo": {"do_sample": False, "num_beams": 5, "repetition_penalty": 1.1, "max_length": 4000, "early_stopping": True},
        "ig": {"do_sample": False, "num_beams": 5, "repetition_penalty": 1.1, "max_length": 4000, "early_stopping": True},
        "ha": {"do_sample": False, "num_beams": 5, "repetition_penalty": 1.1, "max_length": 4000, "early_stopping": True},
    }

    def __init__(self) -> None:
        self._audio_tokenizer = None
        self._model = None
        self._device = None
        self._cache_dir = Path(os.getenv("YARNGPT_CACHE_DIR", Path.home() / ".cache" / "naijatalk" / "yarngpt"))

    def synthesize(self, text: str, language: str) -> bytes:
        if not text.strip():
            return b""

        torch, torchaudio, hf_hub_download, AutoModelForCausalLM = _get_torch_deps()
        
        if self._device is None:
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        audio_tokenizer = self._get_audio_tokenizer(hf_hub_download)
        model = self._get_model(AutoModelForCausalLM)
        hf_tokenizer = audio_tokenizer.tokenizer

        prompt = audio_tokenizer.create_prompt(
            text,
            lang=self.LANGUAGE_NAMES.get(language, "english"),
            speaker_name=self.DEFAULT_SPEAKERS.get(language, "idera"),
        )
        input_ids = audio_tokenizer.tokenize_prompt(prompt)
        attention_mask = torch.ones_like(input_ids, device=input_ids.device)
        generation_kwargs = dict(self.GENERATION_CONFIGS.get(language, self.GENERATION_CONFIGS["en"]))

        with torch.no_grad():
            output = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                pad_token_id=hf_tokenizer.eos_token_id,
                **generation_kwargs,
            )

        codes = audio_tokenizer.get_codes(output)
        if not codes:
            raise RuntimeError("YarnGPT2 returned no audio codes.")

        audio = audio_tokenizer.get_audio(codes)

        if audio.dim() == 1:
            audio = audio.unsqueeze(0)
        elif audio.dim() == 3:
            audio = audio.squeeze(0)

        if audio.numel() == 0:
            raise RuntimeError("YarnGPT2 returned an empty audio tensor.")

        buffer = io.BytesIO()
        torchaudio.save(buffer, audio.detach().cpu(), sample_rate=self.SAMPLE_RATE, format="wav")
        return buffer.getvalue()

    def _get_audio_tokenizer(self, hf_hub_download):
        if self._audio_tokenizer is None:
            importlib_util = __import__("importlib.util")
            try:
                from yarngpt.audiotokenizer import AudioTokenizerV2
            except ImportError:
                AudioTokenizerV2 = self._load_local_audio_tokenizer(importlib_util)

            wavtokenizer_model_path = self._ensure_wavtokenizer_model(hf_hub_download)
            wavtokenizer_config_path = self._ensure_wavtokenizer_config(hf_hub_download)

            self._audio_tokenizer = AudioTokenizerV2(
                self.MODEL_ID,
                str(wavtokenizer_model_path),
                str(wavtokenizer_config_path),
            )

        return self._audio_tokenizer

    def _load_local_audio_tokenizer(self, importlib_util):
        import os
        repo_dir = Path(
            os.getenv(
                "YARNGPT_REPO_DIR",
                Path(__file__).resolve().parents[3] / "third_party" / "yarngpt",
            )
        )
        module_path = repo_dir / "audiotokenizer.py"

        if not module_path.exists():
            raise RuntimeError(
                "YarnGPT2 source repo not found. Clone https://github.com/saheedniyi02/yarngpt "
                f"into {repo_dir} or set YARNGPT_REPO_DIR."
            )

        if str(repo_dir) not in sys.path:
            sys.path.insert(0, str(repo_dir))

        spec = importlib_util.spec_from_file_location("yarngpt_local_audiotokenizer", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load YarnGPT2 audio tokenizer from {module_path}")

        module = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module.AudioTokenizerV2

    def _get_model(self, AutoModelForCausalLM):
        if self._model is None:
            import torch
            torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            self._model = AutoModelForCausalLM.from_pretrained(
                self.MODEL_ID,
                torch_dtype=torch_dtype,
            ).to(self._device)
            self._model.eval()

        return self._model

    def _ensure_wavtokenizer_config(self, hf_hub_download) -> Path:
        config_path = hf_hub_download(
            repo_id=self.WAVTOKENIZER_REPO_ID,
            filename=self.WAVTOKENIZER_CONFIG_FILE,
        )
        return Path(config_path)

    def _ensure_wavtokenizer_model(self, hf_hub_download) -> Path:
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        model_path = Path(
            os.getenv(
                "YARNGPT_WAVTOKENIZER_MODEL_PATH",
                self._cache_dir / "wavtokenizer_large_speech_320_24k.ckpt",
            )
        )

        if not model_path.exists():
            gdown.download(
                id=self.WAVTOKENIZER_MODEL_FILE_ID,
                output=str(model_path),
                quiet=False,
            )

        return model_path


class ConfigurableTTSModel:
    """Provider-selectable TTS model."""

    def __init__(self) -> None:
        self.provider = os.getenv("TTS_PROVIDER", "yarngpt").strip().lower()
        self.abena_tts = AbenaTTSModel()
        self.google_tts = GoogleCloudTTSModel()
        self.local_tts = YarnGPT2TTSModel()

    def synthesize(self, text: str, language: str, provider: str | None = None) -> bytes:
        selected_provider = (provider or self.provider).strip().lower()

        if selected_provider == "google":
            return self.google_tts.synthesize(text, language)

        if selected_provider in {"yarngpt", "ncair", "nigerian"}:
            return self.local_tts.synthesize(text, language)

        if selected_provider == "abena":
            if self.abena_tts.is_available(language):
                return self.abena_tts.synthesize(text, language)
            return self.local_tts.synthesize(text, language)

        if self.abena_tts.is_available(language):
            return self.abena_tts.synthesize(text, language)

        return self.local_tts.synthesize(text, language)
