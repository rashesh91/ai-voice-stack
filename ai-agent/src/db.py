import os
import asyncpg
import logging

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool
    if _pool is not None:
        return
    dsn = (
        f"postgresql://{os.environ.get('POSTGRES_USER', 'aivoice')}"
        f":{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST', 'postgres')}"
        f":{os.environ.get('POSTGRES_PORT', '5432')}"
        f"/{os.environ.get('POSTGRES_DB', 'aivoice')}"
    )
    _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    await _create_tables()
    logger.info("Database pool initialized")


async def _create_tables():
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS call_events (
                id BIGSERIAL PRIMARY KEY,
                room_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                content TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_call_events_room ON call_events(room_name);
        """)


async def log_call_event(room_name: str, event_type: str, content: str = ""):
    if _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO call_events (room_name, event_type, content) VALUES ($1, $2, $3)",
                room_name, event_type, content,
            )
    except Exception as e:
        logger.warning("Failed to log call event: %s", e)
