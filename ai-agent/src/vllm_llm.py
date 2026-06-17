import logging
import re

from openai import AsyncOpenAI
from livekit.agents import llm
from livekit.agents.llm import ChatChunk, ChoiceDelta
from livekit.agents.types import APIConnectOptions

logger = logging.getLogger(__name__)

# Appended to the system message on every LLM fallback call to hard-lock output language.
_LANG_SUFFIX = {
    "gu-IN": "\nFAQT GUJARATIMA JAVAB APO. Gujarati only. No English sentences.",
    "hi-IN": "\nSIRF HINDI MEIN JAWAB DO. Hindi only. No English sentences.",
    "en-IN": "\nRespond in English only.",
}

# Standalone system prompt for LLM fallback — no 19121 redirect, fully agentic
_LLM_FALLBACK_SYSTEM = {
    "gu-IN": (
        "Tame UGVCL electricity AI customer care assistant chho. "
        "Caller na saval no short, helpful jawab Gujaratima apo (1-2 sentence). "
        "UGVCL: Payment: mpay.guvnl.in. Complaint: aamaari system ma register thashe. "
        "New connection: SDN office ma Aadhaar + index copy. "
        "Agar jaavab na khavdate to kaho: 'Tmaari request note thayi chhe, aamaaro team 2 kalas ma sampark karshe.' "
        "KABHI 'website visit karo', 'click karo', 'screenshot' na kaho. "
        "FAQT GUJARATIMA JAVAB APO."
    ),
    "hi-IN": (
        "Aap UGVCL electricity AI customer care assistant hain. "
        "Caller ke sawal ka short, helpful jawab Hindi mein dijiye (1-2 sentence). "
        "UGVCL: Payment: mpay.guvnl.in. Complaint: hamare system mein register hogi. "
        "New connection: SDN office mein Aadhaar + index copy. "
        "Agar jawab na pata ho to kahein: 'Aapki request note ho gayi hai, hamari team 2 ghante mein sampark karegi.' "
        "KABHI 'website visit karein', 'click karein', 'screenshot' mat kahein. "
        "SIRF HINDI MEIN JAWAB DO."
    ),
    "en-IN": (
        "You are the UGVCL electricity AI customer care assistant. "
        "Give a short, helpful answer to the caller's question (1-2 sentences). "
        "UGVCL: Payment: mpay.guvnl.in. Complaints: registered in our system. "
        "New connection: SDN office with Aadhaar and index copy. "
        "If unsure, say: 'Your request has been noted, our team will contact you within 2 hours.' "
        "NEVER say 'visit website', 'click', or 'screenshot'. "
        "Respond in English only."
    ),
}


_19121_REDIRECT_PATTERN = re.compile(
    r'19121\s*(upar|par|pe|on|number)?\s*(complaint\s*karo|call\s*karo|call\s*karein|complaint\s*karein|par\s*call)?'
    r'|call\s*(karo|karein|karein)?\s*19121'
    r'|19121\s*pe\s*call',
    re.IGNORECASE
)
_19121_REPLACE = {
    "gu-IN": "aamaari system ma complaint register thayi chhe",
    "hi-IN": "hamare system mein complaint register ho gayi hai",
    "en-IN": "your complaint is registered in our system",
}


def _strip_19121(text: str, lang: str = "en-IN") -> str:
    """Replace any '19121 par call karo' style phrases with agentic text."""
    replacement = _19121_REPLACE.get(lang, _19121_REPLACE["en-IN"])
    return _19121_REDIRECT_PATTERN.sub(replacement, text)


def _tts_fix(text: str) -> str:
    """Normalize text so TTS speaks URLs and codes correctly."""
    return (text
        .replace("www.ugvcl.com", "ugvcl dot com")
        .replace("ugvcl.com", "ugvcl dot com")
        .replace("mpay.guvnl.in", "mpay dot guvnl dot in")
        .replace("IFSC BARB0ALKAPU", "IFSC BARB zero ALKAPU")
    )


def _detect_language(text: str) -> str:
    """Detect primary language from script character counts."""
    gu = sum(1 for c in text if "઀" <= c <= "૿")
    hi = sum(1 for c in text if "ऀ" <= c <= "ॿ")
    if gu > 2:
        return "gu-IN"
    if hi > 2:
        return "hi-IN"
    return "en-IN"


def _script_confidence(text: str) -> tuple[str, int]:
    """Return (detected_lang, script_char_count) — high count = high confidence."""
    gu = sum(1 for c in text if "઀" <= c <= "૿")
    hi = sum(1 for c in text if "ऀ" <= c <= "ॿ")
    if gu >= hi and gu > 0:
        return "gu-IN", gu
    if hi > 0:
        return "hi-IN", hi
    return "en-IN", 0


_FRUSTRATION_KEYWORDS = {
    # Gujarati romanised
    "keti vaar", "keti vaaro", "kitli vaar", "kitli vaaro", "keti vakhat",
    "kem nathi", "haju nathi", "chhe kem", "baar baar",
    "kharab", "bekaar", "galat", "bekar",
    # Hindi romanised
    "kitni baar", "kab se", "bahut baar", "kab tak", "abhi tak nahi",
    "bakwaas", "bekar", "bahut bura",
    # English
    "how many times", "already told", "told you", "not working",
    "useless", "pathetic", "very bad", "terrible",
    "very frustrated", "frustrated", "angry",
    # Urgency (treated as heightened emotion)
    "emergency", "hospital", "jaldi", "turant", "abhi abhi",
}

_EMPATHY_INTENTS = {"POWER_OUTAGE", "HIGH_BILL", "SMART_METER", "RECONNECTION", "REFUND"}


def _detect_frustration(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _FRUSTRATION_KEYWORDS)


_WORD_TO_DIGIT = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "oh": "0",  # "oh" used instead of zero in phone numbers
}


def _words_to_digits(text: str) -> str:
    """Replace English digit-words with numerals."""
    lower = text.lower()
    for word, digit in _WORD_TO_DIGIT.items():
        lower = re.sub(r'\b' + word + r'\b', digit, lower)
    return lower


def _extract_raw_digits(text: str) -> str:
    """Return all digit characters from text (after word conversion), any length."""
    return re.sub(r"\D", "", _words_to_digits(text))


def _extract_digits(text: str) -> str | None:
    """Extract a 10-digit (mobile) or 11-digit (consumer no.) sequence from text.
    Handles word-spelled digits (three nine...) and space-separated digits."""
    digits_only = _extract_raw_digits(text)
    if len(digits_only) in (10, 11):
        return digits_only
    # Try finding a run within a longer string
    for match in re.finditer(r"\d{10,11}", digits_only):
        val = match.group()
        if len(val) in (10, 11):
            return val
    return None


class VLLMChat(llm.LLM):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        session_manager=None,
        tts=None,
        temperature: float = 0.7,
        max_tokens: int = 150,
        repetition_penalty: float = 1.3,
    ):
        super().__init__()
        self._client = AsyncOpenAI(base_url=base_url, api_key="not-needed")
        self._model = model
        self._session_manager = session_manager
        self._tts = tts
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._repetition_penalty = repetition_penalty

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list | None = None,
        conn_options: APIConnectOptions = APIConnectOptions(),
        **kwargs,
    ) -> "VLLMStream":
        return VLLMStream(
            llm=self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )


class VLLMStream(llm.LLMStream):

    def _emit(self, text: str) -> None:
        self._event_ch.send_nowait(ChatChunk(
            id="fsm-0",
            delta=ChoiceDelta(role="assistant", content=_tts_fix(text)),
        ))

    async def _call_vllm(self, messages: list, lang: str = "en-IN") -> None:
        stream = await self._llm._client.chat.completions.create(
            model=self._llm._model,
            messages=messages,
            temperature=self._llm._temperature,
            max_tokens=self._llm._max_tokens,
            extra_body={"repetition_penalty": self._llm._repetition_penalty},
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                clean = _strip_19121(_tts_fix(delta.content), lang)
                self._event_ch.send_nowait(ChatChunk(
                    id=chunk.id,
                    delta=ChoiceDelta(role="assistant", content=clean),
                ))

    async def _run(self) -> None:
        from .intent import classify_intent, build_reply, t as fsm_t
        from .db import get_account_by_number
        from .session import SessionManager

        # Build message list and extract last user text
        messages: list[dict] = []
        last_user_text = ""
        for msg in self._chat_ctx.messages():
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            content = _extract_text(msg.content)
            if content:
                messages.append({"role": role, "content": content})
                if role == "user":
                    last_user_text = content

        session = self._llm._session_manager
        if session is None or not last_user_text:
            await self._call_vllm(messages)
            return

        # --- Auto language detection (every turn, script-confidence based) ---
        stripped = last_user_text.strip()
        is_digit_only = bool(re.match(r'^[\d\s\-\+,.]+$', stripped))
        if len(stripped) >= 4 and not is_digit_only:
            detected, script_chars = _script_confidence(last_user_text)
            current_lang = await session.get_language()
            if script_chars >= 3:
                # High confidence — clear script detected (Gujarati or Hindi unicode chars)
                if detected != current_lang:
                    logger.info("auto_lang_switch %s → %s (script_chars=%d)", current_lang, detected, script_chars)
                    await session.lock_language(detected)
            elif not await session.is_language_locked() and script_chars == 0 and len(stripped) >= 8:
                # Romanized text, no lock yet — use heuristic detect for initial lock only
                lang_guess = _detect_language(last_user_text)
                await session.lock_language(lang_guess)
        lang = await session.get_language()

        state = await session.get_state()
        logger.info("fsm state=%s lang=%s user=%r", state, lang, last_user_text[:60])

        # ==============================================================
        # STATE: CLOSED — drop the message, do not generate any reply
        # ==============================================================
        if state == SessionManager.CLOSED:
            logger.info("message received in CLOSED state — ignoring")
            return

        # ==============================================================
        # STATE: IDENTIFYING
        # ==============================================================
        if state == SessionManager.IDENTIFYING:
            digits = _extract_digits(last_user_text)

            if digits is None:
                # Check for partial digits (user speaking number in parts)
                raw = _extract_raw_digits(last_user_text)
                if raw:
                    prev = await session.get_partial_digits()
                    combined = prev + raw
                    await session.set_partial_digits(combined)
                    logger.info("partial_digits accumulated=%s", combined)
                    if len(combined) >= 10:
                        digits = combined[:11] if len(combined) >= 11 else combined
                        await session.set_partial_digits("")
                    else:
                        self._emit(fsm_t("ask_more_digits", lang))
                        return

            if digits:
                await session.set_partial_digits("")
                account = await get_account_by_number(digits)
                if account:
                    await session.set_consumer(account)
                    await session.set_state(SessionManager.HANDLING)
                    reply = fsm_t("identified", lang,
                                  name=account["name"], plan=account["plan"])
                    logger.info("consumer_identified name=%s", account["name"])
                    self._emit(reply)
                    return
                else:
                    retry = await session.increment_identify_retry()
                    if retry <= 1:
                        self._emit(fsm_t("account_not_found_retry", lang))
                        return
                    # 2nd failed attempt — continue without account
                    await session.set_state(SessionManager.HANDLING)
                    self._emit(fsm_t("continue_without", lang))
                    return
            else:
                # No digits at all — count as retry
                retry = await session.increment_identify_retry()
                if retry <= 1:
                    self._emit(fsm_t("ask_consumer_number", lang))
                    return
                # User not giving a number — move to HANDLING and treat as query
                await session.set_state(SessionManager.HANDLING)
                # Fall through to HANDLING below

        # ==============================================================
        # STATE: HANDLING
        # ==============================================================
        if state in (SessionManager.HANDLING, SessionManager.IDENTIFYING):
            from .knowledge import lookup as knowledge_lookup
            intent, confidence = classify_intent(last_user_text)
            logger.info("intent=%s confidence=%d lang=%s", intent, confidence, lang)

            frustrated = _detect_frustration(last_user_text)
            if frustrated:
                logger.info("frustration_detected text=%r", last_user_text[:50])
            tts = self._llm._tts
            if tts is not None:
                if frustrated:
                    tts.set_emotion("frustrated")
                elif intent in _EMPATHY_INTENTS:
                    tts.set_emotion("empathy")
                else:
                    tts.set_emotion("normal")

            if intent != "UNKNOWN":
                consumer = await session.get_consumer()
                # Try specific sub-topic answer first; fall back to generic intent reply
                specific = knowledge_lookup(intent, last_user_text, lang)
                if specific:
                    logger.info("knowledge_hit intent=%s lang=%s", intent, lang)
                    # Prepend empathy/frustrated prefix for complaint intents
                    from .intent import _EMPATHY_PREFIX, _FRUSTRATED_PREFIX
                    if frustrated:
                        prefix = _FRUSTRATED_PREFIX.get(lang, "")
                    else:
                        prefix = _EMPATHY_PREFIX.get(intent, {}).get(lang, "")
                    reply = prefix + specific
                else:
                    reply = build_reply(intent, consumer, lang, frustrated=frustrated)
                # Stay in HANDLING — allow follow-up questions
                follow_up = fsm_t("follow_up", lang)
                self._emit(reply + follow_up)
                return
            else:
                # Try knowledge lookup across all intents before hitting LLM
                from .knowledge import _KB
                kb_answer = None
                for kb_intent, entries in _KB.items():
                    kb_answer = knowledge_lookup(kb_intent, last_user_text, lang)
                    if kb_answer:
                        logger.info("knowledge_fallback_hit intent=%s lang=%s", kb_intent, lang)
                        break
                if kb_answer:
                    follow_up = fsm_t("follow_up", lang)
                    self._emit(kb_answer + follow_up)
                    return

                # No knowledge hit — call trained vLLM with agentic system prompt (no 19121 redirect)
                logger.info("unknown_intent — calling trained vLLM (lang=%s)", lang)
                lm = [m for m in messages if m["role"] != "system"]
                lm.insert(0, {"role": "system", "content": _LLM_FALLBACK_SYSTEM.get(lang, _LLM_FALLBACK_SYSTEM["en-IN"])})
                await self._call_vllm(lm, lang=lang)
                # Stay in HANDLING after LLM reply — user can ask more
                return


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(item.text)
        return "".join(parts)
    return str(content) if content else ""
