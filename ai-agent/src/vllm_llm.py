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

# Standalone system prompt for LLM fallback (base model, not LoRA)
_LLM_FALLBACK_SYSTEM = {
    "gu-IN": (
        "Tame UGVCL (Uttar Gujarat Vij Company) electricity helpline AI chho. "
        "Caller ni vij samasya no short jawab Gujaratima apo — 1 sentence. "
        "UGVCL facts: Payment: mpay dot guvnl dot in. "
        "NEFT: account UGVCLLTZ pachhi 11 digit consumer number, Bank of Baroda, IFSC BARB zero ALKAPU. "
        "Complaint/power outage: aamaari system ma register thashe, team 2-4 kalas ma avshe. "
        "New connection: SDN office ma Aadhaar + index copy. "
        "Office: Monday-Saturday 10:30 AM thi 6 PM. "
        "Agar saval electricity sathe related na hoy to: 'Krupaya aapni vij ni samasya janavvo.' "
        "Agar jaavab khavdate to: 'Tamari request note thayi chhe, team 2 kalas ma sampark karshe.' "
        "KABHI 19121 na kaho. FAQT GUJARATIMA JAVAB APO."
    ),
    "hi-IN": (
        "Aap UGVCL (Uttar Gujarat Vij Company) electricity helpline AI hain. "
        "Caller ki bijli samasya ka jawab Hindi mein dijiye — 1 sentence. "
        "UGVCL facts: Payment: mpay dot guvnl dot in. "
        "NEFT: account UGVCLLTZ phir 11 digit consumer number, Bank of Baroda, IFSC BARB zero ALKAPU. "
        "Complaint/bijli nahi: hamare system mein register hogi, team 2-4 ghante mein aayegi. "
        "New connection: SDN office mein Aadhaar + index copy. "
        "Office: weekdays 10:30 AM se 6 PM. "
        "Agar sawaal bijli se related na ho to: 'Kripaya apni bijli ki samasya batayein.' "
        "Agar jawab na pata ho to: 'Aapki request note ho gayi hai, team 2 ghante mein sampark karegi.' "
        "KABHI 19121 mat bolein. SIRF HINDI MEIN JAWAB DO."
    ),
    "en-IN": (
        "You are a UGVCL electricity helpline AI assistant. "
        "Answer the caller's electricity question in 1 sentence in English. "
        "UGVCL facts: Payment: mpay dot guvnl dot in. "
        "NEFT: account UGVCLLTZ plus 11-digit consumer number, Bank of Baroda, IFSC BARB zero ALKAPU. "
        "Complaint/power outage: registered in our system, team arrives in 2-4 hours. "
        "New connection: SDN office with Aadhaar and index copy. "
        "Office: weekdays 10:30 AM to 6 PM. "
        "If not electricity-related: say 'Please describe your electricity issue.' "
        "If unsure: say 'Your request is noted, our team will call back within 2 hours.' "
        "NEVER say 19121. Respond in English only."
    ),
}

# Electricity-related words — if NONE present in user text, it's noise/off-topic
_ELECTRICITY_WORDS = {
    # Gujarati romanized
    "vij", "light", "bill", "meter", "bijli", "payment", "connection", "solar",
    "transformer", "recharge", "ugvcl", "mpay", "sdn", "current", "supply",
    "fuse", "complaint", "reading", "voltage", "disconnect", "reconnect",
    "prepaid", "neft", "ifsc", "consumer", "account",
    # Hindi Unicode
    "बिजली", "बिल", "मीटर", "भुगतान", "कनेक्शन", "ट्रांसफार्मर", "रीचार्ज",
    "शिकायत", "वोल्टेज", "सप्लाई", "उपभोक्ता",
    # English
    "electricity", "power", "outage", "pay", "invoice", "wiring", "wire",
    "pole", "fault", "mcb", "trip",
}

_OFF_TOPIC_RESPONSE = {
    "gu-IN": "Maafi mangu chu, mane samjayun nahi. Krupaya aapni vij ni samasya janavvo.",
    "hi-IN": "Maafi chahti hoon, baat samajh nahi aayi. Kripaya apni bijli ki samasya batayein.",
    "en-IN": "I'm sorry, I didn't catch that. Could you please describe your electricity issue?",
}


def _has_electricity_context(text: str) -> bool:
    """Return True if text contains at least one electricity-related word."""
    lower = text.lower()
    return any(w in lower for w in _ELECTRICITY_WORDS)


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


# Confirmation messages when locked language changes
_LANG_SWITCH_CONFIRM: dict[str, dict[str, str]] = {
    "gu-IN": {
        "hi-IN": "Tamne Hindi ma vaat karavani chhe? Ha ke Na bolsho.",
        "en-IN": "Would you like to switch to English? Please say Yes or No.",
    },
    "hi-IN": {
        "gu-IN": "Kya aap Gujarati mein baat karna chahenge? Haan ya Na bolein.",
        "en-IN": "Would you like to switch to English? Please say Yes or No.",
    },
    "en-IN": {
        "gu-IN": "Gujaratima switch karavu chhe? Ha ke Na bolsho.",
        "hi-IN": "Kya Hindi mein switch karna hai? Haan ya Na bolein.",
    },
}
_LANG_SWITCH_DONE: dict[tuple, str] = {
    ("gu-IN", "hi-IN"): "Ji, ab Hindi mein baat karte hain.",
    ("gu-IN", "en-IN"): "Sure, switching to English now.",
    ("hi-IN", "gu-IN"): "Ji, hu have Gujaratima vaat karishu.",
    ("hi-IN", "en-IN"): "Sure, switching to English now.",
    ("en-IN", "gu-IN"): "Ji, Gujaratima continue kariye.",
    ("en-IN", "hi-IN"): "Ji, ab Hindi mein baat karte hain.",
}
_LANG_SWITCH_CANCELLED: dict[str, str] = {
    "gu-IN": "Thik chhe ji, Gujaratima j continue kariye.",
    "hi-IN": "Thik hai ji, Hindi mein hi continue karte hain.",
    "en-IN": "Alright, let's continue in English.",
}

# Words that confirm "yes" across all three languages
_AFFIRMATIVES = {"ha", "haa", "haan", "han", "yes", "yep", "ya", "ji", "bilkul",
                 "zarur", "okay", "ok", "thik", "theek", "sure", "correct", "right"}
# Words that confirm "no"
_NEGATIVES = {"na", "nahi", "naa", "no", "nope", "nathi", "mat", "band", "nai"}


def _is_affirmative(text: str) -> bool:
    words = set(text.lower().split())
    return bool(words & _AFFIRMATIVES) and not bool(words & _NEGATIVES)


def _is_negative(text: str) -> bool:
    words = set(text.lower().split())
    return bool(words & _NEGATIVES)


class VLLMChat(llm.LLM):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        session_manager=None,
        tts=None,
        stt=None,
        translator=None,
        temperature: float = 0.7,
        max_tokens: int = 150,
        repetition_penalty: float = 1.3,
    ):
        super().__init__()
        self._client = AsyncOpenAI(base_url=base_url, api_key="not-needed")
        self._model = model
        self._session_manager = session_manager
        self._tts = tts
        self._stt = stt
        self._translator = translator
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

    async def _async_emit(self, text: str, lang: str, translate: bool = False) -> None:
        """Emit text to TTS. Only translate when caller lang differs from text lang (LLM fallback)."""
        if translate and self._llm._translator is not None:
            source = _detect_language(text)
            if source != lang:
                text = await self._llm._translator.to_lang(text, source_lang=source, target_lang=lang)
        self._emit(text)

    async def _call_vllm(self, messages: list, lang: str = "en-IN", model: str | None = None,
                         max_tokens: int | None = None, temperature: float | None = None) -> None:
        use_model = model or self._llm._model
        stream = await self._llm._client.chat.completions.create(
            model=use_model,
            messages=messages,
            temperature=temperature if temperature is not None else self._llm._temperature,
            max_tokens=max_tokens if max_tokens is not None else self._llm._max_tokens,
            extra_body={"repetition_penalty": self._llm._repetition_penalty},
            stream=True,
        )
        # Buffer full LLM response so we can translate before speaking
        full_text = ""
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                full_text += delta.content

        if full_text:
            clean = _strip_19121(_tts_fix(full_text), lang)
            await self._async_emit(clean, lang, translate=True)

    async def _run(self) -> None:
        from .intent import classify_intent, build_reply, t as fsm_t, _pick
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

        # --- Language detection + lock + confirmation gate ---
        stripped = last_user_text.strip()
        is_digit_only = bool(re.match(r'^[\d\s\-\+,.]+$', stripped))
        lang = await session.get_language()
        is_locked = await session.is_language_locked()

        # Check for a pending language-switch confirmation first
        pending_switch = await session.get_pending_lang_switch()
        if pending_switch:
            if _is_affirmative(stripped):
                # Customer confirmed — do the switch
                old_lang = lang
                await session.lock_language(pending_switch)
                await session.clear_pending_lang_switch()
                if self._llm._tts is not None:
                    self._llm._tts.update_language(pending_switch)
                if self._llm._stt is not None:
                    self._llm._stt.update_language(pending_switch)
                lang = pending_switch
                done_msg = _LANG_SWITCH_DONE.get((old_lang, lang), "Language updated.")
                logger.info("lang_switch_confirmed %s → %s", old_lang, lang)
                await self._async_emit(done_msg, lang)
                return
            else:
                # Customer said no (or spoke about something else) — cancel and process normally
                await session.clear_pending_lang_switch()
                if not _is_negative(stripped):
                    # They said something useful — fall through and process the message
                    logger.info("lang_switch_cancelled — processing message in %s", lang)
                else:
                    await self._async_emit(_LANG_SWITCH_CANCELLED.get(lang, "Continuing."), lang)
                    return

        # Normal language detection — only act when text is non-trivial
        if len(stripped) >= 4 and not is_digit_only:
            detected, script_chars = _script_confidence(last_user_text)
            if script_chars >= 3:
                if not is_locked:
                    # First clear detection — lock language and update STT+TTS
                    logger.info("lang_lock %s → %s (script_chars=%d)", lang, detected, script_chars)
                    await session.lock_language(detected)
                    lang = detected
                    if self._llm._tts is not None:
                        self._llm._tts.update_language(detected)
                    if self._llm._stt is not None:
                        self._llm._stt.update_language(detected)
                elif detected != lang and script_chars >= 5:
                    # Language IS locked but caller switched to a clearly different script
                    # Ask for confirmation before changing
                    confirm = _LANG_SWITCH_CONFIRM.get(lang, {}).get(detected)
                    if confirm:
                        logger.info("lang_switch_pending %s → %s, asking confirmation", lang, detected)
                        await session.set_pending_lang_switch(detected)
                        await self._async_emit(confirm, lang)
                        return
            elif not is_locked and script_chars == 0 and len(stripped) >= 8:
                # Romanised text only — heuristic detect for initial lock
                lang_guess = _detect_language(last_user_text)
                await session.lock_language(lang_guess)
                lang = lang_guess
                if self._llm._tts is not None:
                    self._llm._tts.update_language(lang_guess)
                if self._llm._stt is not None:
                    self._llm._stt.update_language(lang_guess)

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
                        await self._async_emit(fsm_t("ask_more_digits", lang), lang)
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
                    await self._async_emit(reply, lang)
                    return
                else:
                    retry = await session.increment_identify_retry()
                    if retry <= 1:
                        await self._async_emit(fsm_t("account_not_found_retry", lang), lang)
                        return
                    # 2nd failed attempt — continue without account
                    await session.set_state(SessionManager.HANDLING)
                    await self._async_emit(fsm_t("continue_without", lang), lang)
                    return
            else:
                # No digits at all — count as retry
                retry = await session.increment_identify_retry()
                if retry <= 1:
                    await self._async_emit(fsm_t("ask_consumer_number", lang), lang)
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

                # Raise a ticket for complaint intents
                ticket_id: str | None = None
                _TICKET_INTENTS = {"POWER_OUTAGE", "SMART_METER", "HIGH_BILL"}
                if intent in _TICKET_INTENTS:
                    import asyncio
                    from .ticket_db import create_ticket
                    account_no = (consumer.get("account_no") or "UNKNOWN") if consumer else "UNKNOWN"
                    ticket_id = await asyncio.get_event_loop().run_in_executor(
                        None, create_ticket, account_no, intent, last_user_text[:200]
                    )

                # Try specific sub-topic answer first; fall back to generic intent reply
                specific = knowledge_lookup(intent, last_user_text, lang)
                if specific:
                    logger.info("knowledge_hit intent=%s lang=%s", intent, lang)
                    from .intent import _EMPATHY_PREFIX, _FRUSTRATED_PREFIX, _TICKET_SUFFIX, _TICKET_INTENTS as _TI
                    if frustrated:
                        prefix = _pick(_FRUSTRATED_PREFIX.get(lang, ""))
                    else:
                        prefix = _pick(_EMPATHY_PREFIX.get(intent, {}).get(lang, ""))
                    reply = prefix + specific
                    if ticket_id and intent in _TI:
                        reply += _TICKET_SUFFIX.get(lang, _TICKET_SUFFIX["en-IN"]).format(ticket_id=ticket_id)
                else:
                    reply = build_reply(intent, consumer, lang, frustrated=frustrated, ticket_id=ticket_id)
                # Stay in HANDLING — allow follow-up questions
                follow_up = fsm_t("follow_up", lang)
                await self._async_emit(reply + follow_up, lang)
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
                    await self._async_emit(kb_answer + follow_up, lang)
                    return

                # No knowledge hit — call trained vLLM with agentic system prompt (no 19121 redirect)
                logger.info("unknown_intent — calling trained vLLM (lang=%s)", lang)
                # Send ONLY system + last user message — full history causes garbage accumulation
                lm = [
                    {"role": "system", "content": _LLM_FALLBACK_SYSTEM.get(lang, _LLM_FALLBACK_SYSTEM["en-IN"])},
                    {"role": "user", "content": last_user_text},
                ]
                await self._call_vllm(lm, lang=lang, max_tokens=80, temperature=0.2)
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
