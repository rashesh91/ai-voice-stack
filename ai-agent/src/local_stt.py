"""
Local STT using sarvamai/sarvam-2b-v0.5 (Sarvam Edge).
Drop-in replacement for SarvamSTT — same LiveKit STT interface.
Loaded lazily on first use; inference offloaded to executor.
"""
import asyncio
import io
import logging
import struct
import threading
import wave
from typing import Optional

from livekit.agents import stt
from livekit.agents.stt import SpeechData, SpeechEvent, SpeechEventType, STTCapabilities
from livekit.agents.types import APIConnectOptions
from livekit.agents.utils import AudioBuffer

logger = logging.getLogger(__name__)

_MODEL_ID = "sarvamai/sarvam-2b-v0.5"
_SAMPLE_RATE = 16000

# Map session language codes → model language tags
_LANG_TO_TAG = {
    "gu-IN":   "gu",
    "hi-IN":   "hi",
    "en-IN":   "en",
    "unknown": None,   # let model auto-detect
}

_lock = threading.Lock()
_pipe = None   # transformers ASR pipeline, loaded once


def _load_model():
    global _pipe
    if _pipe is not None:
        return _pipe
    with _lock:
        if _pipe is not None:
            return _pipe
        import torch
        from transformers import pipeline

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        logger.info("loading %s on %s …", _MODEL_ID, device)
        _pipe = pipeline(
            "automatic-speech-recognition",
            model=_MODEL_ID,
            torch_dtype=dtype,
            device=device,
            chunk_length_s=30,
            stride_length_s=5,
        )
        logger.info("local STT ready — %s", _MODEL_ID)
    return _pipe


def _run_inference(wav_bytes: bytes, language: str | None) -> str:
    pipe = _load_model()
    import numpy as np

    # Decode WAV → float32 numpy
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        n_ch = wf.getnchannels()
        sr = wf.getframerate()
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_ch > 1:
        samples = samples.reshape(-1, n_ch).mean(axis=1)

    gen_kwargs = {}
    if language:
        gen_kwargs["language"] = language
        gen_kwargs["task"] = "transcribe"

    result = pipe(
        {"raw": samples, "sampling_rate": sr},
        generate_kwargs=gen_kwargs if gen_kwargs else None,
        return_timestamps=False,
    )
    return result.get("text", "").strip()


class LocalSarvamSTT(stt.STT):
    """Wraps sarvamai/sarvam-2b-v0.5 as a LiveKit STT service."""

    def __init__(self, language: str = "unknown"):
        super().__init__(capabilities=STTCapabilities(
            streaming=False,
            interim_results=False,
        ))
        self._language = language

    def update_language(self, lang: str) -> None:
        self._language = lang
        logger.info("local_stt language → %s", lang)

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: Optional[str] = None,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> SpeechEvent:
        lang_code = language or self._language
        model_lang = _LANG_TO_TAG.get(lang_code)

        frames = buffer if isinstance(buffer, list) else [buffer]
        pcm_data = b"".join(bytes(f.data) for f in frames)
        if not pcm_data:
            return SpeechEvent(
                type=SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[SpeechData(text="", language=lang_code)],
            )

        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(_SAMPLE_RATE)
            wf.writeframes(pcm_data)
        wav_bytes = wav_buf.getvalue()

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _run_inference, wav_bytes, model_lang)

        logger.info("local_stt lang=%s transcript=%r", lang_code, text)
        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[SpeechData(text=text, language=lang_code, confidence=1.0)],
        )
