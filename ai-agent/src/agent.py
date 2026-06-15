import asyncio
import logging
import os
import time

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import silero

from .sarvam_stt import SarvamSTT
from .sarvam_tts import SarvamTTS
from .vllm_llm import VLLMChat
from .session import SessionManager
from .db import init_db, log_call_event

logger = logging.getLogger(__name__)

GREETING = "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?"

MOCK_ACCOUNTS = """
Demo account data — use this when callers give their mobile number:
| Mobile       | Name             | Bill Amount | Due Date    | Plan                   | Account No | Last Payment       |
|--------------|------------------|-------------|-------------|------------------------|------------|--------------------|
| 9876543210   | Ramesh Kumar     | ₹450        | 20 Jun 2026 | 99 GB Data Pack        | ACC001     | ₹450 on 15 May     |
| 9876543211   | Priya Sharma     | ₹780        | 25 Jun 2026 | Unlimited Calls        | ACC002     | ₹780 on 10 May     |
| 9123456789   | Amit Patel       | ₹320        | 18 Jun 2026 | Basic 2GB/day          | ACC003     | ₹320 on 18 May     |
| 8800001234   | Sunita Devi      | ₹180        | 30 Jun 2026 | Voice Only Pack        | ACC004     | ₹180 on 1 Jun      |
| 7700123456   | Vijay Singh      | ₹1200       | 15 Jun 2026 | 5G Premium 200GB       | ACC005     | ₹1200 on 15 May    |
| 9988776655   | Kavita Mehta     | ₹650        | 22 Jun 2026 | Fiber Broadband 100Mbps| ACC006     | ₹650 on 22 May     |
| 8877665544   | Suresh Yadav     | ₹0          | —           | Prepaid 28-day ₹199    | ACC007     | Recharged ₹199     |
| 7766554433   | Deepika Joshi    | ₹3500       | 10 Jun 2026 | Enterprise 1Gbps       | ACC008     | ₹3500 on 10 May    |
| 9900112233   | Mohammed Rafiq   | ₹550        | 28 Jun 2026 | Unlimited 5G           | ACC009     | ₹550 on 28 May     |
| 8811223344   | Lakshmi Nair     | ₹230        | 5 Jul 2026  | Student Pack 3GB/day   | ACC010     | ₹230 on 5 Jun      |

Additional account details:
- ACC001 (Ramesh Kumar): Internet speed: 40Mbps, Data used: 67GB of 99GB, Complaints: None
- ACC002 (Priya Sharma): Has EMI of ₹199/month for device, next due 25 Jun 2026
- ACC003 (Amit Patel): Account blocked due to non-payment, needs ₹320 to unblock
- ACC005 (Vijay Singh): Bill overdue by 2 days, late fee ₹50 will apply after 20 Jun
- ACC007 (Suresh Yadav): Prepaid — current balance ₹45, validity expires 8 Jul 2026
- ACC008 (Deepika Joshi): Business account, GST registered, GSTIN: 24AABCS1429B1ZB

If the caller's number is not listed, say their account was not found and ask them to verify the number.
When giving bill information, always mention: amount, due date, and whether it is overdue.
"""

SYSTEM_PROMPT = (
    "You are a helpful AI voice assistant for a telecom and billing customer support helpline in India. "
    "You assist callers with: billing queries (बिल/bill), internet and broadband issues, mobile recharges, "
    "EMI and payment problems, KYC verification, account issues, complaints, and service requests. "
    "Respond concisely — your responses will be spoken aloud. Keep answers to 1-2 sentences. "
    "Detect the caller's language and always respond in that same language. "
    "You support Hindi, English, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Marathi, and Hinglish. "
    "IMPORTANT: Voice transcription may have minor errors in a telecom context. "
    "If you see 'दिल', 'दिन', 'मिल', or 'मिल्क' in a billing query, it likely means 'बिल' (bill). "
    "Always interpret ambiguous words in the context of telecom and billing support.\n\n"
    + MOCK_ACCOUNTS
)


class VoiceAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=SYSTEM_PROMPT,
            allow_interruptions=True,
        )

    async def on_enter(self) -> None:
        await self.session.say(GREETING, allow_interruptions=True)


async def entrypoint(ctx: JobContext) -> None:
    call_start = time.monotonic()
    room_name = ctx.room.name
    logger.info("agent joining room=%s", room_name)

    await init_db()

    sarvam_api_key = os.environ["SARVAM_API_KEY"]

    # Start pre-warming greeting TTS immediately — runs in parallel with room setup
    tts_instance = SarvamTTS(api_key=sarvam_api_key, language="hi-IN")
    tts_instance.start_prewarm(GREETING)

    await ctx.connect()

    session_mgr = SessionManager(room_name)
    await session_mgr.create()
    await log_call_event(room_name, "call_started")

    language = await session_mgr.get_language()

    # If session language differs from hi-IN, create a new TTS for it
    if language != "hi-IN":
        tts_instance = SarvamTTS(api_key=sarvam_api_key, language=language)

    # Wait for pre-warm to finish before starting session (greeting is already cached)
    await tts_instance.await_prewarm()

    session = AgentSession(
        stt=SarvamSTT(api_key=sarvam_api_key, language="unknown"),
        llm=VLLMChat(
            base_url=os.environ.get("VLLM_BASE_URL", "http://vllm:8000/v1"),
            model=os.environ.get("VLLM_MODEL", "bartowski/Llama-3.2-3B-Instruct-AWQ"),
            temperature=0.7,
            max_tokens=200,
        ),
        tts=tts_instance,
        vad=silero.VAD.load(
            min_silence_duration=0.3,
            min_speech_duration=0.1,
            prefix_padding_duration=0.2,
        ),
        allow_interruptions=True,
        min_endpointing_delay=0.3,
        max_endpointing_delay=1.2,
    )

    _first_speech = True

    def on_transcript(event):
        text = getattr(event, "transcript", "") or getattr(event, "text", "")
        if text:
            asyncio.create_task(session_mgr.append_turn("user", text))
            asyncio.create_task(log_call_event(room_name, "user_speech", text))

    def on_agent_state(event):
        nonlocal _first_speech
        if event.new_state == "speaking" and _first_speech:
            _first_speech = False
            ms = (time.monotonic() - call_start) * 1000
            logger.info("latency_ms=%.0f room=%s", ms, room_name)

    session.on("user_input_transcribed", on_transcript)
    session.on("agent_state_changed", on_agent_state)

    agent = VoiceAgent()
    await session.start(agent, room=ctx.room, capture_run=True)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
