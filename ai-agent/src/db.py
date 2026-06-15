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

            CREATE TABLE IF NOT EXISTS mock_accounts (
                mobile      TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                bill_amount TEXT DEFAULT '₹0',
                due_date    TEXT DEFAULT '—',
                plan        TEXT DEFAULT 'Unknown',
                account_no  TEXT DEFAULT '',
                last_payment TEXT DEFAULT '—',
                notes       TEXT DEFAULT '',
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    await _seed_accounts()


_DEFAULT_ACCOUNTS = [
    ("9876543210", "Ramesh Kumar",  "₹450",  "20 Jun 2026", "99 GB Data Pack",          "ACC001", "₹450 on 15 May",  ""),
    ("9876543211", "Priya Sharma",  "₹780",  "25 Jun 2026", "Unlimited Calls",           "ACC002", "₹780 on 10 May",  "Has EMI of ₹199/month for device, next due 25 Jun"),
    ("9123456789", "Amit Patel",    "₹320",  "18 Jun 2026", "Basic 2GB/day",             "ACC003", "₹320 on 18 May",  "Account blocked due to non-payment, needs ₹320 to unblock"),
    ("8800001234", "Sunita Devi",   "₹180",  "30 Jun 2026", "Voice Only Pack",           "ACC004", "₹180 on 1 Jun",   ""),
    ("7700123456", "Vijay Singh",   "₹1200", "15 Jun 2026", "5G Premium 200GB",          "ACC005", "₹1200 on 15 May", "Bill overdue by 2 days, late fee ₹50 will apply after 20 Jun"),
    ("9988776655", "Kavita Mehta",  "₹650",  "22 Jun 2026", "Fiber Broadband 100Mbps",   "ACC006", "₹650 on 22 May",  ""),
    ("8877665544", "Suresh Yadav",  "₹0",    "—",           "Prepaid 28-day ₹199",       "ACC007", "Recharged ₹199",  "Prepaid — current balance ₹45, validity expires 8 Jul 2026"),
    ("7766554433", "Deepika Joshi", "₹3500", "10 Jun 2026", "Enterprise 1Gbps",          "ACC008", "₹3500 on 10 May", "Business account, GST: 24AABCS1429B1ZB"),
    ("9900112233", "Mohammed Rafiq","₹550",  "28 Jun 2026", "Unlimited 5G",              "ACC009", "₹550 on 28 May",  ""),
    ("8811223344", "Lakshmi Nair",  "₹230",  "5 Jul 2026",  "Student Pack 3GB/day",      "ACC010", "₹230 on 5 Jun",   ""),
]


async def _seed_accounts():
    async with _pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM mock_accounts")
        if count == 0:
            await conn.executemany(
                """INSERT INTO mock_accounts
                   (mobile, name, bill_amount, due_date, plan, account_no, last_payment, notes)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                   ON CONFLICT (mobile) DO NOTHING""",
                _DEFAULT_ACCOUNTS,
            )
            logger.info("Seeded %d demo accounts", len(_DEFAULT_ACCOUNTS))


async def seed_dummy_calls():
    """Insert realistic demo call events so the dashboard has data out of the box."""
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM call_events")
        if count > 0:
            return
        rows = [
            ("demo_room_001", "call_started",  ""),
            ("demo_room_001", "user_speech",   "नमस्ते, मेरा बिल कितना है?"),
            ("demo_room_001", "agent_speech",  "नमस्ते! आपका इस महीने का बिल ₹450 है, जो 20 जून 2026 तक देय है।"),
            ("demo_room_001", "user_speech",   "क्या मैं ऑनलाइन पेमेंट कर सकता हूँ?"),
            ("demo_room_001", "agent_speech",  "जी हाँ, आप हमारी वेबसाइट या मोबाइल ऐप से आसानी से पेमेंट कर सकते हैं।"),
            ("demo_room_001", "call_ended",    ""),
            ("demo_room_002", "call_started",  ""),
            ("demo_room_002", "user_speech",   "My account is blocked, please help me."),
            ("demo_room_002", "agent_speech",  "I can see your account ACC003 is blocked due to a pending payment of ₹320. Would you like to pay now to restore service?"),
            ("demo_room_002", "user_speech",   "Yes, how do I pay?"),
            ("demo_room_002", "agent_speech",  "You can pay via UPI, net banking, or credit card on our app. Once paid, your service will be restored within 30 minutes."),
            ("demo_room_002", "user_speech",   "Okay, thank you."),
            ("demo_room_002", "agent_speech",  "You're welcome! Is there anything else I can help you with?"),
            ("demo_room_002", "call_ended",    ""),
            ("demo_room_003", "call_started",  ""),
            ("demo_room_003", "user_speech",   "मेरे प्लान की वैलिडिटी कब खत्म होगी?"),
            ("demo_room_003", "agent_speech",  "आपका प्रीपेड प्लान 8 जुलाई 2026 को समाप्त होगा। अभी आपके अकाउंट में ₹45 बैलेंस है।"),
            ("demo_room_003", "user_speech",   "ठीक है, धन्यवाद।"),
            ("demo_room_003", "agent_speech",  "आपका स्वागत है! क्या कोई और सहायता चाहिए?"),
            ("demo_room_003", "call_ended",    ""),
        ]
        for room, etype, content in rows:
            await conn.execute(
                "INSERT INTO call_events (room_name, event_type, content, created_at) "
                "VALUES ($1, $2, $3, NOW() - (random()*interval '10 minutes'))",
                room, etype, content,
            )
        logger.info("Seeded %d dummy call events", len(rows))


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


async def get_mock_accounts() -> list[dict]:
    if _pool is None:
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT mobile, name, bill_amount, due_date, plan, account_no, last_payment, notes "
            "FROM mock_accounts ORDER BY account_no"
        )
    return [dict(r) for r in rows]


async def upsert_mock_account(data: dict) -> None:
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO mock_accounts
               (mobile, name, bill_amount, due_date, plan, account_no, last_payment, notes, updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8, NOW())
               ON CONFLICT (mobile) DO UPDATE SET
                 name=$2, bill_amount=$3, due_date=$4, plan=$5,
                 account_no=$6, last_payment=$7, notes=$8, updated_at=NOW()""",
            data["mobile"], data["name"], data.get("bill_amount", "₹0"),
            data.get("due_date", "—"), data.get("plan", ""),
            data.get("account_no", ""), data.get("last_payment", "—"),
            data.get("notes", ""),
        )


async def delete_mock_account(mobile: str) -> bool:
    async with _pool.acquire() as conn:
        result = await conn.execute("DELETE FROM mock_accounts WHERE mobile=$1", mobile)
    return result == "DELETE 1"
