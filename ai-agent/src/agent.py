import asyncio
import logging
import os
import time

from livekit.agents import Agent, AgentSession, JobContext, RoomInputOptions, WorkerOptions, cli
from livekit.plugins import silero, noise_cancellation

from .sarvam_stt import SarvamSTT
from .sarvam_tts import SarvamTTS
from .vllm_llm import VLLMChat
from .session import SessionManager
from .db import init_db, log_call_event, get_mock_accounts

logger = logging.getLogger(__name__)

# Greeting asks for consumer / mobile number to start FSM identification
GREETING = (
    "નમસ્તે! UGVCL ગ્રાહક સેવામાં સ્વાગત. "
    "Consumer number અથવા registered mobile number આપો."
)

_SYSTEM_PROMPT_BASE = (
    "You are a voice assistant for U.G.V.C.L. (Uttar Gujarat Vij Company Limited) electricity helpline. "
    "STRICT RULES:\n"
    "1. Match the caller's language exactly — Gujarati, Hindi, or English. Never switch languages mid-reply.\n"
    "2. Response must be 1-2 short spoken sentences only. No lists, no bullet points.\n"
    "3. NEVER say 'screenshot', 'click', 'see attachment', or 'fill the form online'.\n"
    "4. NEVER invent URLs, phone numbers, or procedures not listed below.\n"
    "5. If you do not know the exact answer, say our team will look into it and assist shortly.\n\n"
    "UGVCL FACTS (use only these):\n"
    "- Payment: mpay.guvnl.in OR NEFT UGVCLLTZ + 11-digit consumer number, Bank of Baroda, IFSC BARB0ALKAPU.\n"
    "- Complaint / Power outage: Register in this system — field team dispatched within 2-4 hours.\n"
    "- Solar bill: Import units minus Export units = net billed units. Excess export credited to bank every June.\n"
    "- Smart meter complaint: Register in this system — technician visits within 2-3 working days.\n"
    "- Prepaid: balance zero disconnects supply. Recharge at mpay.guvnl.in. 3% rebate.\n"
    "- Reconnection: pay bill, 2-3 working days.\n"
    "- New connection: visit SDN office with Aadhaar and index copy.\n"
    "- Mobile registration: ugvcl.com Consumer Online Service — link mobile option.\n"
    "- High bill/wrong reading: within 5 days of bill date, visit SDN office with meter photo.\n"
    "- Smart meter billing: monthly only — bi-monthly/quarterly not available.\n"
    "- Office hours: weekdays 10:30 AM to 6:00 PM at nearest UGVCL SDN office.\n"
)


def _build_system_prompt(accounts: list[dict]) -> str:
    if not accounts:
        return _SYSTEM_PROMPT_BASE
    lines = [
        "\n\nDemo account data — use this when callers give their consumer number or mobile:",
        "| Mobile     | Name             | Bill     | Due Date    | Plan                  | Account No  | Notes |",
        "|------------|------------------|----------|-------------|------------------------|-------------|-------|",
    ]
    for a in accounts:
        notes = (a.get("notes") or "")[:50]
        lines.append(
            f"| {a['mobile']} | {a['name']:<16} | {a.get('bill_amount','₹0'):<8} | "
            f"{a.get('due_date','—'):<11} | {a.get('plan',''):<22} | "
            f"{a.get('account_no',''):<11} | {notes} |"
        )
    lines.append(
        "\nIf caller's number matches, give their exact bill and due date. "
        "If not found, say account not found and offer 19121."
    )
    return _SYSTEM_PROMPT_BASE + "\n".join(lines)


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

    # Pre-warm TTS for greeting in parallel with room setup
    tts_instance = SarvamTTS(api_key=sarvam_api_key, language="gu-IN")
    tts_instance.start_prewarm(GREETING)

    await ctx.connect()

    session_mgr = SessionManager(room_name)
    await session_mgr.create()          # sets state=IDENTIFYING, language=gu-IN
    await log_call_event(room_name, "call_started")

    await tts_instance.await_prewarm()

    try:
        accounts = await get_mock_accounts()
        prompt = _build_system_prompt(accounts)
    except Exception:
        logger.warning("Failed to load mock accounts — using base prompt")
        prompt = _SYSTEM_PROMPT_BASE

    session = AgentSession(
        stt=SarvamSTT(api_key=sarvam_api_key, language="unknown"),
        llm=VLLMChat(
            base_url=os.environ.get("VLLM_BASE_URL", "http://vllm:8000/v1"),
            model=os.environ.get("VLLM_MODEL", "voice-agent"),
            session_manager=session_mgr,
            tts=tts_instance,
            temperature=0.7,
            max_tokens=150,
        ),
        tts=tts_instance,
        vad=silero.VAD.load(
            min_silence_duration=0.5,   # longer pause needed to end turn (noise tolerance)
            min_speech_duration=0.25,   # ignore noise bursts < 250ms
            prefix_padding_duration=0.3,
            activation_threshold=0.6,   # higher threshold — less sensitive to background noise
        ),
        allow_interruptions=True,
        min_endpointing_delay=0.5,
        max_endpointing_delay=2.5,      # wait longer for speech in noisy environments
    )

    _first_speech = True

    # Supported Unicode script ranges: Gujarati, Devanagari (Hindi), Basic Latin (English)
    _SUPPORTED_SCRIPTS = (
        ('઀', '૿'),  # Gujarati
        ('ऀ', 'ॿ'),  # Devanagari (Hindi)
        (' ', ''),  # Basic Latin (English + digits)
    )

    def _is_valid_transcript(text: str) -> bool:
        """Filter out STT noise artifacts: too short, or foreign-script hallucinations."""
        text = text.strip()
        if len(text) < 2:
            return False
        # Check if any char is from a non-supported script (noise artifact from background)
        foreign = sum(
            1 for c in text
            if c.isalpha() and not any(lo <= c <= hi for lo, hi in _SUPPORTED_SCRIPTS)
        )
        total_alpha = sum(1 for c in text if c.isalpha())
        # Reject if >40% of alphabetic chars are from unsupported scripts
        if total_alpha > 0 and foreign / total_alpha > 0.4:
            logger.info("noise_filtered transcript=%r (foreign=%.0f%%)", text[:40], 100 * foreign / total_alpha)
            return False
        return True

    def on_transcript(event):
        text = getattr(event, "transcript", "") or getattr(event, "text", "")
        if text and _is_valid_transcript(text):
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
    await session.start(
        agent,
        room=ctx.room,
        capture_run=True,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
