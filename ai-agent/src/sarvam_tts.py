import asyncio
import base64
import io
import logging
import re
import wave
from typing import Optional

import httpx
from livekit.agents import tts, utils
from livekit.agents.tts import TTSCapabilities, SynthesizedAudio
from livekit.agents.types import APIConnectOptions

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

logger = logging.getLogger(__name__)

LANGUAGE_TO_SPEAKER = {
    "gu-IN": "vidya",
    "hi-IN": "manisha",
    "en-IN": "ritu",
    "ta-IN": "ritu",
    "te-IN": "ritu",
    "kn-IN": "ritu",
    "ml-IN": "ritu",
    "bn-IN": "ritu",
    "mr-IN": "ritu",
}

_EMOTION_PARAMS: dict[str, dict[str, float]] = {
    "normal":     {"pace": 0.9,  "pitch": 0},
    "empathy":    {"pace": 0.78, "pitch": -0.05},
    "urgent":     {"pace": 1.05, "pitch": 0.05},
    "positive":   {"pace": 0.88, "pitch": 0.03},
    "frustrated": {"pace": 0.80, "pitch": -0.03},
}

_SENTENCE_END = re.compile(r'(?<=[.?!।॥])\s+')


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_END.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _wav_to_pcm(wav_bytes: bytes) -> bytes:
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        return wf.readframes(wf.getnframes())


class SarvamTTS(tts.TTS):
    def __init__(self, *, api_key: str, language: str = "hi-IN"):
        super().__init__(
            capabilities=TTSCapabilities(streaming=True),
            sample_rate=16000,
            num_channels=1,
        )
        self._api_key = api_key
        self._language = language
        self._speaker = LANGUAGE_TO_SPEAKER.get(language, "ritu")
        self._pace: float = 0.9
        self._pitch: float = 0.0
        self._pcm_cache: dict[str, bytes] = {}
        self._warmup_tasks: list[asyncio.Task] = []

    def set_emotion(self, emotion: str) -> None:
        params = _EMOTION_PARAMS.get(emotion, _EMOTION_PARAMS["normal"])
        self._pace = params["pace"]
        self._pitch = params["pitch"]
        logger.debug("emotion=%s pace=%.2f pitch=%.2f", emotion, self._pace, self._pitch)

    def start_prewarm(self, text: str) -> None:
        """Start background TTS generation for text sentences; results go to cache."""
        sentences = _split_sentences(text) or [text]
        for s in sentences:
            if s not in self._pcm_cache:
                task = asyncio.create_task(self._fetch_and_cache(s))
                self._warmup_tasks.append(task)

    async def await_prewarm(self) -> None:
        """Wait for all pre-warming tasks to complete."""
        if self._warmup_tasks:
            await asyncio.gather(*self._warmup_tasks, return_exceptions=True)
            self._warmup_tasks.clear()

    async def _fetch_and_cache(self, sentence: str) -> None:
        try:
            await self._fetch_tts(sentence)  # _fetch_tts writes to _pcm_cache
        except Exception:
            logger.exception("TTS prewarm failed for %r", sentence[:40])

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> "SarvamChunkedStream":
        return SarvamChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )

    def stream(
        self,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> "SarvamSynthesizeStream":
        return SarvamSynthesizeStream(tts=self, conn_options=conn_options)

    async def _tts_sentence(self, sentence: str) -> bytes:
        if sentence in self._pcm_cache:
            logger.debug("TTS cache hit: %r", sentence[:40])
            return self._pcm_cache[sentence]
        return await self._fetch_tts(sentence)

    async def _fetch_tts(self, sentence: str) -> bytes:
        payload = {
            "inputs": [sentence],
            "target_language_code": self._language,
            "speaker": self._speaker,
            "pace": self._pace,
            "pitch": self._pitch,
            "speech_sample_rate": 16000,
            "model": "bulbul:v3",
            "pronunciation_dict_id": "p_6c46665c",
        }
        headers = {
            "api-subscription-key": self._api_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(SARVAM_TTS_URL, json=payload, headers=headers)
        resp.raise_for_status()
        wav_bytes = base64.b64decode(resp.json()["audios"][0])
        pcm = _wav_to_pcm(wav_bytes)
        self._pcm_cache[sentence] = pcm
        return pcm


class SarvamChunkedStream(tts.ChunkedStream):
    """Non-streaming: convert full text to speech (sentence-parallel)."""

    def __init__(self, *, tts: SarvamTTS, input_text: str,
                 conn_options: APIConnectOptions):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._sarvam = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        sentences = _split_sentences(self._input_text)
        if not sentences:
            return

        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=16000,
            num_channels=1,
            mime_type="audio/pcm",
            stream=True,
        )

        # Synthesize all sentences in parallel, then emit as ONE segment
        tasks = [asyncio.create_task(self._sarvam._tts_sentence(s)) for s in sentences]
        output_emitter.start_segment(segment_id="response")
        for i, task in enumerate(tasks):
            try:
                pcm = await task
                output_emitter.push(pcm)
            except Exception:
                logger.exception("TTS sentence %d failed", i)
        output_emitter.end_segment()


class SarvamSynthesizeStream(tts.SynthesizeStream):
    """Streaming: split LLM tokens at sentence boundaries, TTS each sentence immediately."""

    def __init__(self, *, tts: SarvamTTS, conn_options: APIConnectOptions):
        super().__init__(tts=tts, conn_options=conn_options)
        self._sarvam = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=16000,
            num_channels=1,
            mime_type="audio/pcm",
            stream=True,
        )
        buf = ""
        output_emitter.start_segment(segment_id="stream_response")

        async for token in self._input_ch:
            if isinstance(token, tts.SynthesizeStream._FlushSentinel):
                if buf.strip():
                    try:
                        pcm = await self._sarvam._tts_sentence(buf.strip())
                        output_emitter.push(pcm)
                    except Exception:
                        logger.exception("TTS flush failed")
                    buf = ""
                continue

            buf += token
            # Fire TTS as soon as we have a complete sentence
            sentences = _split_sentences(buf)
            if len(sentences) > 1:
                for sentence in sentences[:-1]:
                    try:
                        pcm = await self._sarvam._tts_sentence(sentence)
                        output_emitter.push(pcm)
                    except Exception:
                        logger.exception("TTS stream sentence failed")
                buf = sentences[-1]

        # Synthesize any remaining text
        if buf.strip():
            try:
                pcm = await self._sarvam._tts_sentence(buf.strip())
                output_emitter.push(pcm)
            except Exception:
                logger.exception("TTS final failed")
        output_emitter.end_segment()
