"""
Local TTS using ai4bharat/indic-parler-tts (Parler-TTS architecture).
Drop-in replacement for SarvamTTS — same LiveKit TTS interface.
Loaded lazily on first use; inference offloaded to executor.
"""
import asyncio
import io
import logging
import threading
from typing import AsyncGenerator

from livekit.agents import tts
from livekit.agents.tts import TTSCapabilities
from livekit.agents.types import APIConnectOptions

logger = logging.getLogger(__name__)

_MODEL_ID = "ai4bharat/indic-parler-tts"
_SAMPLE_RATE = 16000   # we resample model output to match LiveKit expectation

# Voice description prompts — same "character" in each language, different accent hints.
# These shape the voice style; spin vocabulary so each reads naturally to the model.
_VOICE_PROMPTS: dict[str, str] = {
    "gu-IN": (
        "Ritu speaks at a calm, moderate pace with a warm and professional tone. "
        "Her voice has a clear Gujarati accent with natural Indian cadence. "
        "She sounds like a knowledgeable customer service agent — reassuring, helpful, and polite."
    ),
    "hi-IN": (
        "Ritu baat karti hai ek sahaj, shant andaaz mein. "
        "Uski awaaz mein Hindi ki natural laya hai — madadgaar, thandhi aur professional. "
        "Ritu speaks with a gentle Hindi accent, steady rhythm, and a helpful customer care tone."
    ),
    "en-IN": (
        "Ritu speaks in a clear, confident voice with a formal Indian English accent. "
        "Her pace is steady and easy to follow, with a professional customer service warmth. "
        "She sounds articulate, polite, and reassuring."
    ),
}
_DEFAULT_PROMPT = _VOICE_PROMPTS["en-IN"]

_lock = threading.Lock()
_model = None
_tokenizer = None
_device = None


def _load_model():
    global _model, _tokenizer, _device
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        _device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        logger.info("loading %s on %s …", _MODEL_ID, _device)
        _model = ParlerTTSForConditionalGeneration.from_pretrained(
            _MODEL_ID, torch_dtype=dtype
        ).to(_device)
        _tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
        logger.info("local TTS ready — %s (sr=%d)", _MODEL_ID, _model.config.sampling_rate)


def _run_synthesis(text: str, prompt: str) -> bytes:
    """Return raw PCM bytes at _SAMPLE_RATE (16 kHz, mono, int16)."""
    import numpy as np
    import torch

    _load_model()

    input_ids = _tokenizer(prompt, return_tensors="pt").input_ids.to(_device)
    prompt_ids = _tokenizer(text, return_tensors="pt").input_ids.to(_device)

    with torch.no_grad():
        generation = _model.generate(
            input_ids=input_ids,
            prompt_input_ids=prompt_ids,
            do_sample=True,
            temperature=0.9,
        )

    audio_arr = generation.cpu().numpy().squeeze()
    model_sr = _model.config.sampling_rate   # usually 24000 or 44100

    # Resample to _SAMPLE_RATE if needed
    if model_sr != _SAMPLE_RATE:
        try:
            import resampy
            audio_arr = resampy.resample(audio_arr, model_sr, _SAMPLE_RATE)
        except ImportError:
            # fallback: simple decimation (lower quality but no extra dep)
            ratio = model_sr // _SAMPLE_RATE
            audio_arr = audio_arr[::ratio]

    # Convert float32 → int16 PCM
    audio_int16 = (np.clip(audio_arr, -1.0, 1.0) * 32767).astype(np.int16)
    return audio_int16.tobytes()


class LocalIndicTTS(tts.TTS):
    """Wraps ai4bharat/indic-parler-tts as a LiveKit TTS service."""

    def __init__(self, language: str = "en-IN"):
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=_SAMPLE_RATE,
            num_channels=1,
        )
        self._language = language

    def update_language(self, lang: str) -> None:
        self._language = lang
        logger.info("local_tts language → %s", lang)

    def set_emotion(self, emotion: str) -> None:
        # Parler-TTS controls voice via prompt text — emotion is baked into prompt
        # For now, no dynamic emotion change; voice prompt already conveys warmth
        pass

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> "LocalIndicTTSStream":
        return LocalIndicTTSStream(tts=self, input_text=text)


class LocalIndicTTSStream(tts.ChunkedStream):

    def __init__(self, *, tts: "LocalIndicTTS", input_text: str):
        super().__init__(tts=tts, input_text=input_text)
        self._tts_obj = tts

    async def _run(self, max_retry: int = 3) -> None:
        from livekit.agents.tts import SynthesizedAudio

        text = self._input_text.strip()
        if not text:
            return

        prompt = _VOICE_PROMPTS.get(self._tts_obj._language, _DEFAULT_PROMPT)

        loop = asyncio.get_event_loop()
        pcm_bytes = await loop.run_in_executor(None, _run_synthesis, text, prompt)

        self._event_ch.send_nowait(
            SynthesizedAudio(
                request_id=self._request_id,
                frame=tts.AudioFrame(
                    data=pcm_bytes,
                    sample_rate=_SAMPLE_RATE,
                    num_channels=1,
                    samples_per_channel=len(pcm_bytes) // 2,
                ),
            )
        )
