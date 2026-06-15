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
from .db import init_db, log_call_event, get_mock_accounts

logger = logging.getLogger(__name__)

GREETING = "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?"

_SYSTEM_PROMPT_BASE = (
    "You are a helpful AI voice assistant for a telecom and billing customer support helpline in India. "
    "You assist callers with: billing queries (बिल/bill), internet and broadband issues, mobile recharges, "
    "EMI and payment problems, KYC verification, account issues, complaints, and service requests. "
    "Respond concisely — your responses will be spoken aloud. Keep answers to 1-2 sentences. "
    "Detect the caller's language and always respond in that same language. "
    "You support Hindi, English, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Marathi, and Hinglish. "
    "IMPORTANT: Voice transcription may have minor errors in a telecom context. "
    "If you see 'दिल', 'दिन', 'मिल', or 'मिल्क' in a billing query, it likely means 'बिल' (bill). "
    "Always interpret ambiguous words in the context of telecom and billing support."
)


def _build_system_prompt(accounts: list[dict]) -> str:
    if not accounts:
        return _SYSTEM_PROMPT_BASE
    lines = [
        "\n\nDemo account data — use this when callers give their mobile number:",
        "| Mobile     | Name             | Bill   | Due Date    | Plan                   | Account | Last Payment    | Notes |",
        "|------------|------------------|--------|-------------|------------------------|---------|-----------------|-------|",
    ]
    for a in accounts:
        notes = a.get("notes", "") or ""
        lines.append(
            f"| {a['mobile']} | {a['name']:<16} | {a.get('bill_amount','₹0'):<6} | "
            f"{a.get('due_date','—'):<11} | {a.get('plan',''):<22} | "
            f"{a.get('account_no',''):<7} | {a.get('last_payment','—'):<15} | {notes[:40]} |"
        )
    lines.append(
        "\nIf the caller's number is not listed, say their account was not found and ask them to verify."
        "\nWhen giving bill info, always mention: amount, due date, and whether it is overdue."
    )
    return _SYSTEM_PROMPT_BASE + "\n".join(lines)


# Fallback prompt used if DB fetch fails
SYSTEM_PROMPT = _SYSTEM_PROMPT_BASE


class VoiceAgent(Agent):
    def __init__(self, instructions: str):
        super().__init__(instructions=instructions, allow_interruptions=True)

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

    # Load mock accounts from DB and build dynamic system prompt
    try:
        accounts = await get_mock_accounts()
        prompt = _build_system_prompt(accounts)
    except Exception:
        logger.warning("Failed to load mock accounts — using base prompt")
        prompt = _SYSTEM_PROMPT_BASE

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

    def on_conversation_item(event):
        item = event.item
        if getattr(item, "role", "") == "assistant":
            text = getattr(item, "text_content", "") or ""
            if text:
                asyncio.create_task(log_call_event(room_name, "agent_speech", text))

    session.on("user_input_transcribed", on_transcript)
    session.on("agent_state_changed", on_agent_state)
    session.on("conversation_item_added", on_conversation_item)

    agent = VoiceAgent(instructions=prompt)
    await session.start(agent, room=ctx.room, capture_run=True)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
