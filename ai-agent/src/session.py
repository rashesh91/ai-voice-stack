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
    def __init__(self, room_name: str):
        self._key = f"session:{room_name}"
        self._history_key = f"history:{room_name}"

    async def create(self):
        r = await _get_redis()
        await r.hset(self._key, mapping={"language": "hi-IN", "status": "active"})
        await r.expire(self._key, 3600)

    async def get_language(self) -> str:
        r = await _get_redis()
        lang = await r.hget(self._key, "language")
        return lang or "hi-IN"

    async def set_language(self, language: str):
        r = await _get_redis()
        await r.hset(self._key, "language", language)

    async def append_turn(self, role: str, text: str):
        r = await _get_redis()
        entry = json.dumps({"role": role, "text": text})
        await r.rpush(self._history_key, entry)
        await r.expire(self._history_key, 3600)
