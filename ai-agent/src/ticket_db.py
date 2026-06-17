"""
SQLite-backed ticket store for UGVCL voice agent.
Thread-safe, synchronous — called from async context via run_in_executor.
"""
import logging
import os
import random
import sqlite3
import string
import threading

logger = logging.getLogger(__name__)

_DB_PATH = os.environ.get("TICKET_DB_PATH", "/data/ugvcl_tickets.db")
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_ticket_db() -> None:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id          TEXT PRIMARY KEY,
                account_no  TEXT NOT NULL,
                intent      TEXT NOT NULL,
                description TEXT DEFAULT '',
                status      TEXT DEFAULT 'open',
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_account
            ON tickets(account_no)
        """)
    logger.info("ticket_db initialised at %s", _DB_PATH)


def create_ticket(account_no: str, intent: str, description: str = "") -> str:
    """Insert a new ticket and return its ID like UGVCL-2026-84291."""
    suffix = "".join(random.choices(string.digits, k=5))
    ticket_id = f"UGVCL-2026-{suffix}"
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO tickets (id, account_no, intent, description) VALUES (?, ?, ?, ?)",
            (ticket_id, account_no, intent, description[:200]),
        )
    logger.info("ticket_created id=%s account=%s intent=%s", ticket_id, account_no, intent)
    return ticket_id


def get_tickets(account_no: str) -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT id, intent, status, created_at FROM tickets WHERE account_no=? ORDER BY created_at DESC LIMIT 5",
            (account_no,),
        ).fetchall()
    return [dict(r) for r in rows]
