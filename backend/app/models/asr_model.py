from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def _get_pipeline_or_pipe():
    from transformers import pipeline
    import torch
    return pipeline, torch


class NATLASASRModel:
    """Lazy-loaded wrapper around the N-ATLaS ASR models."""

    MODEL_IDS: Dict[str, str] = {
        "en": "NCAIR1/NigerianAccentedEnglish",
        "yo": "NCAIR1/Yoruba-ASR",
        "ha": "NCAIR1/Hausa-ASR",
        "ig": "NCAIR1/Igbo-ASR",
    }

    def __init__(self) -> None:
        self._pipelines: Dict[str, object] = {}
        self._device = None

    def transcribe(self, audio_path: str, language: str) -> str:
        pipeline, torch = _get_pipeline_or_pipe()
        if self._device is None:
            self._device = 0 if torch.cuda.is_available() else -1
        
        model_id = self.MODEL_IDS.get(language, self.MODEL_IDS["en"])
        asr_pipeline = self._get_pipeline(model_id, pipeline)

        result = asr_pipeline(str(Path(audio_path)))
        if isinstance(result, dict):
            text = result.get("text", "")
        else:
            text = str(result)

        return text.strip()

    def _get_pipeline(self, model_id: str, pipeline_fn):
        if model_id not in self._pipelines:
            self._pipelines[model_id] = pipeline_fn(
                "automatic-speech-recognition",
                model=model_id,
                device=self._device,
            )

        return self._pipelines[model_id]