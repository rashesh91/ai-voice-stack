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
    # (mobile, name, bill_amount, due_date, plan, account_no, last_payment, notes)
    ("9879001234", "Haresh Patel",     "₹1,840", "25 Jun 2026", "LT Domestic SP",     "12345678901", "₹1,200 on 15 May", "Prepaid smart meter — balance ₹320"),
    ("9879001235", "Manish Shah",      "₹5,670", "20 Jun 2026", "LT Commercial",      "12345678903", "₹2,800 on 1 Jun",  "Outstanding ₹2,870 — disconnection risk"),
    ("9879001236", "Priya Desai",      "₹3,200", "22 Jun 2026", "LT Agriculture",     "12345678902", "₹3,200 on 22 May", "Solar net meter — import 420 units, export 180 units"),
    ("9879001237", "Ramesh Trivedi",   "₹720",   "28 Jun 2026", "LT Domestic 3P",     "12345678904", "₹720 on 28 May",   ""),
    ("9879001238", "Bhavna Joshi",     "₹9,500", "15 Jun 2026", "HT Industrial",      "12345678905", "₹9,500 on 15 May", "HT consumer — demand 45 KVA"),
    ("9879001239", "Suresh Prajapati", "₹410",   "30 Jun 2026", "LT Domestic BPL",    "12345678906", "₹410 on 30 May",   "BPL category — 30 units free per month"),
    ("9879001240", "Meena Parmar",     "₹0",     "—",           "LT Domestic Prepaid","12345678907", "₹500 on 10 Jun",   "Prepaid — balance ₹45, low balance alert sent"),
    ("9879001241", "Kiran Shah",       "₹2,100", "18 Jun 2026", "LT Commercial 3P",   "12345678908", "₹2,100 on 18 May", ""),
    ("9879001242", "Dinesh Kumar",     "₹6,800", "12 Jun 2026", "LT Industrial",      "12345678909", "₹6,800 on 12 May", "Bill overdue — disconnection notice issued"),
    ("9879001243", "Anjali Mehta",     "₹1,560", "24 Jun 2026", "LT Domestic Solar",  "12345678910", "₹1,560 on 24 May", "Solar rooftop — excess units credited annually in June"),
]


async def _seed_accounts():
    async with _pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO mock_accounts
               (mobile, name, bill_amount, due_date, plan, account_no, last_payment, notes, updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8, NOW())
               ON CONFLICT (mobile) DO UPDATE SET
                 name=$2, bill_amount=$3, due_date=$4, plan=$5,
                 account_no=$6, last_payment=$7, notes=$8, updated_at=NOW()""",
            _DEFAULT_ACCOUNTS,
        )
        logger.info("Upserted %d UGVCL demo accounts", len(_DEFAULT_ACCOUNTS))


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


async def get_account_by_number(number: str) -> dict | None:
    """Look up a consumer by 10-digit mobile or 11-digit account_no."""
    if _pool is None:
        return None
    number = number.strip()
    async with _pool.acquire() as conn:
        if len(number) == 10:
            row = await conn.fetchrow(
                "SELECT mobile, name, bill_amount, due_date, plan, account_no, last_payment, notes "
                "FROM mock_accounts WHERE mobile=$1",
                number,
            )
        elif len(number) == 11:
            row = await conn.fetchrow(
                "SELECT mobile, name, bill_amount, due_date, plan, account_no, last_payment, notes "
                "FROM mock_accounts WHERE account_no=$1",
                number,
            )
        else:
            return None
    return dict(row) if row else None


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
