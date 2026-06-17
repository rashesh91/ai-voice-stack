import asyncio
import json
import os
import redis.asyncio as aioredis

_redis: aioredis.Redis | None = None
_redis_lock = asyncio.Lock()


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is not None:
        return _redis
    async with _redis_lock:
        if _redis is None:
            _redis = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    return _redis


class SessionManager:
    """
    Redis-backed session state for one call.

    Hash key  : session:{room_name}
    Fields    : language, language_locked, state, identify_retries,
                unknown_count, consumer_* (name/mobile/bill_amount/due_date/plan/account_no/notes)
    List key  : history:{room_name}
    """

    # Conversation states
    IDENTIFYING = "IDENTIFYING"
    HANDLING = "HANDLING"
    CLOSED = "CLOSED"

    def __init__(self, room_name: str):
        self._key = f"session:{room_name}"
        self._history_key = f"history:{room_name}"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def create(self):
        r = await _get_redis()
        await r.hset(self._key, mapping={
            "language":        "gu-IN",
            "language_locked": "0",
            "state":           self.IDENTIFYING,
            "identify_retries": "0",
            "unknown_count":   "0",
            "status":          "active",
        })
        await r.expire(self._key, 3600)

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    async def get_language(self) -> str:
        r = await _get_redis()
        lang = await r.hget(self._key, "language")
        return lang or "gu-IN"

    async def is_language_locked(self) -> bool:
        r = await _get_redis()
        val = await r.hget(self._key, "language_locked")
        return val == "1"

    async def lock_language(self, lang: str):
        r = await _get_redis()
        await r.hset(self._key, mapping={"language": lang, "language_locked": "1"})

    # kept for backward compat
    async def set_language(self, language: str):
        await self.lock_language(language)

    async def get_pending_lang_switch(self) -> str | None:
        r = await _get_redis()
        val = await r.hget(self._key, "pending_lang_switch")
        return val or None

    async def set_pending_lang_switch(self, lang: str):
        r = await _get_redis()
        await r.hset(self._key, "pending_lang_switch", lang)

    async def clear_pending_lang_switch(self):
        r = await _get_redis()
        await r.hdel(self._key, "pending_lang_switch")

    # ------------------------------------------------------------------
    # Conversation state (FSM)
    # ------------------------------------------------------------------

    async def get_state(self) -> str:
        r = await _get_redis()
        state = await r.hget(self._key, "state")
        return state or self.IDENTIFYING

    async def set_state(self, state: str):
        r = await _get_redis()
        await r.hset(self._key, "state", state)

    # ------------------------------------------------------------------
    # Consumer identification
    # ------------------------------------------------------------------

    async def increment_identify_retry(self) -> int:
        r = await _get_redis()
        return int(await r.hincrby(self._key, "identify_retries", 1))

    async def set_consumer(self, account: dict):
        r = await _get_redis()
        await r.hset(self._key, mapping={
            "consumer_name":    account.get("name", ""),
            "consumer_mobile":  account.get("mobile", ""),
            "consumer_account": account.get("account_no", ""),
            "consumer_bill":    account.get("bill_amount", ""),
            "consumer_due":     account.get("due_date", ""),
            "consumer_plan":    account.get("plan", ""),
            "consumer_notes":   account.get("notes", ""),
        })

    async def get_consumer(self) -> dict | None:
        r = await _get_redis()
        name = await r.hget(self._key, "consumer_name")
        if not name:
            return None
        return {
            "name":       name,
            "mobile":     await r.hget(self._key, "consumer_mobile") or "",
            "account_no": await r.hget(self._key, "consumer_account") or "",
            "bill_amount": await r.hget(self._key, "consumer_bill") or "",
            "due_date":   await r.hget(self._key, "consumer_due") or "",
            "plan":       await r.hget(self._key, "consumer_plan") or "",
            "notes":      await r.hget(self._key, "consumer_notes") or "",
        }

    # ------------------------------------------------------------------
    # Partial digit accumulation (consumer number spoken in parts)
    # ------------------------------------------------------------------

    async def get_partial_digits(self) -> str:
        r = await _get_redis()
        return await r.hget(self._key, "partial_digits") or ""

    async def set_partial_digits(self, digits: str):
        r = await _get_redis()
        await r.hset(self._key, "partial_digits", digits)

    # ------------------------------------------------------------------
    # Escalation counter
    # ------------------------------------------------------------------

    async def increment_unknown(self) -> int:
        r = await _get_redis()
        return int(await r.hincrby(self._key, "unknown_count", 1))

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    async def append_turn(self, role: str, text: str):
        r = await _get_redis()
        entry = json.dumps({"role": role, "text": text})
        await r.rpush(self._history_key, entry)
        await r.expire(self._history_key, 3600)
