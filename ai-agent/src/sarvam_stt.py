import io
import logging
import re
import struct
import wave
from typing import Optional

import httpx
from livekit.agents import stt
from livekit.agents.stt import (
    SpeechData, SpeechEvent, SpeechEventType, STTCapabilities,
)
from livekit.agents.types import APIConnectOptions
from livekit.agents.utils import AudioBuffer

logger = logging.getLogger(__name__)

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_STT_MODEL = "saaras:v3"
SARVAM_STT_MODE = "codemix"

# Billing context words — only apply homophone correction when present
_BILLING_CONTEXT_RE = re.compile(
    r'(बारे\s*में|देखना|दिखाना|चाहिए|डिटेल|जानकारी|जानना|पेमेंट|बकाया|'
    r'invoice|payment|details|information|show|check)'
)
# "possessive + दिल/दिन/मिल/मिल्क" → replace with "बिल"
# Only fires when _BILLING_CONTEXT_RE matches the full sentence
_BILLING_HOMOPHONE_RE = re.compile(
    r'\b(मेरे?|अपने?|आपके?|हमारे?|मेरा|अपना|आपका)\s+(दिल|दिन|मिल|मिल्क)\b'
)


def _fix_billing_homophones(text: str) -> str:
    """Correct STT homophones that are acoustically similar to 'बिल' in billing context."""
    if not _BILLING_CONTEXT_RE.search(text):
        return text
    corrected = _BILLING_HOMOPHONE_RE.sub(lambda m: m.group(1) + ' बिल', text)
    if corrected != text:
        logger.info("STT homophone correction: %r → %r", text, corrected)
    return corrected


class SarvamSTT(stt.STT):
    def __init__(self, *, api_key: str, language: str = "unknown"):
        super().__init__(capabilities=STTCapabilities(
            streaming=False,
            interim_results=False,
        ))
        self._api_key = api_key
        self._language = language

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: Optional[str] = None,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> SpeechEvent:
        lang = language or self._language

        # Build WAV from PCM frames (buffer may be a single frame or a list)
        frames = buffer if isinstance(buffer, list) else [buffer]
        pcm_data = b"".join(bytes(frame.data) for frame in frames)
        if not pcm_data:
            return SpeechEvent(
                type=SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[SpeechData(text="", language=lang)],
            )

        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)
            wf.writeframes(pcm_data)
        wav_bytes = wav_buf.getvalue()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                SARVAM_STT_URL,
                headers={"api-subscription-key": self._api_key},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"language_code": lang, "model": SARVAM_STT_MODEL, "mode": SARVAM_STT_MODE},
            )

        if resp.status_code != 200:
            logger.warning("Sarvam STT error %s: %s", resp.status_code, resp.text[:200])
            text = ""
        else:
            text = resp.json().get("transcript", "").strip()
            text = _fix_billing_homophones(text)

        logger.info("Sarvam STT lang=%s transcript=%r", lang, text)
        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[SpeechData(text=text, language=lang, confidence=1.0)],
        )
