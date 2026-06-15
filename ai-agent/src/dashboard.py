"""Web dashboard — live calls, transcripts, and demo account management."""
import asyncio
import datetime
import json
import logging
import os
import random
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)
_pool: asyncpg.Pool | None = None


def _serialize(rows) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        d = {}
        for k, v in dict(row).items():
            d[k] = v.isoformat() if isinstance(v, (datetime.datetime, datetime.date)) else v
        out.append(d)
    return out


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    dsn = (
        f"postgresql://{os.environ.get('POSTGRES_USER','aivoice')}"
        f":{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST','postgres')}"
        f":{os.environ.get('POSTGRES_PORT','5432')}"
        f"/{os.environ.get('POSTGRES_DB','aivoice')}"
    )
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return _pool


async def _seed_dummy_calls(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM call_events")
        if count > 0:
            return
        rows = [
            ("demo_room_rajesh_9876543210_001", "call_started",  ""),
            ("demo_room_rajesh_9876543210_001", "user_speech",   "नमस्ते, मेरा बिल कितना है?"),
            ("demo_room_rajesh_9876543210_001", "agent_speech",  "नमस्ते! आपका इस महीने का बिल ₹450 है, जो 20 जून 2026 तक देय है।"),
            ("demo_room_rajesh_9876543210_001", "user_speech",   "क्या मैं ऑनलाइन पेमेंट कर सकता हूँ?"),
            ("demo_room_rajesh_9876543210_001", "agent_speech",  "जी हाँ, आप हमारी वेबसाइट या मोबाइल ऐप से UPI, नेट बैंकिंग या क्रेडिट कार्ड से पेमेंट कर सकते हैं।"),
            ("demo_room_rajesh_9876543210_001", "call_ended",    ""),
            ("demo_room_amit_9123456789_002",   "call_started",  ""),
            ("demo_room_amit_9123456789_002",   "user_speech",   "My account is blocked, please help me."),
            ("demo_room_amit_9123456789_002",   "agent_speech",  "I can see your account ACC003 is blocked due to a pending payment of ₹320. Would you like to pay now to restore service immediately?"),
            ("demo_room_amit_9123456789_002",   "user_speech",   "Yes, how do I pay via UPI?"),
            ("demo_room_amit_9123456789_002",   "agent_speech",  "You can scan our QR code on the app or use UPI ID: aivoice@upi. Once payment is confirmed, your service will restore within 30 minutes."),
            ("demo_room_amit_9123456789_002",   "user_speech",   "Okay done, I paid. Thank you!"),
            ("demo_room_amit_9123456789_002",   "agent_speech",  "Great! Payment received. Your service will be restored shortly. Is there anything else I can help you with?"),
            ("demo_room_amit_9123456789_002",   "call_ended",    ""),
            ("demo_room_suresh_8877665544_003", "call_started",  ""),
            ("demo_room_suresh_8877665544_003", "user_speech",   "मेरे प्रीपेड प्लान की वैलिडिटी कब खत्म होगी?"),
            ("demo_room_suresh_8877665544_003", "agent_speech",  "आपका प्रीपेड 28-दिन वाला ₹199 प्लान 8 जुलाई 2026 को समाप्त होगा। अभी आपके अकाउंट में ₹45 बैलेंस है।"),
            ("demo_room_suresh_8877665544_003", "user_speech",   "रिचार्ज कैसे करूँ?"),
            ("demo_room_suresh_8877665544_003", "agent_speech",  "आप हमारी ऐप, वेबसाइट, या नजदीकी रिटेलर से ₹199 का रिचार्ज करवा सकते हैं।"),
            ("demo_room_suresh_8877665544_003", "call_ended",    ""),
        ]
        offsets = list(range(len(rows), 0, -1))
        for (room, etype, content), offset in zip(rows, offsets):
            await conn.execute(
                "INSERT INTO call_events (room_name, event_type, content, created_at) "
                "VALUES ($1, $2, $3, NOW() - ($4 * interval '30 seconds'))",
                room, etype, content, offset,
            )
        logger.info("Seeded %d dummy call events", len(rows))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pool = await _get_pool()
        await _seed_dummy_calls(pool)
    except Exception:
        logger.exception("Dashboard DB connect failed")
    yield
    if _pool:
        await _pool.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Calls API ─────────────────────────────────────────────────────────────────

@app.get("/api/calls")
async def api_calls():
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT room_name,
                   MIN(created_at) AS started_at,
                   MAX(created_at) AS last_event,
                   COUNT(*) FILTER (WHERE event_type='user_speech') AS turns
            FROM call_events
            GROUP BY room_name
            ORDER BY started_at DESC LIMIT 30
        """)
    return JSONResponse(_serialize(rows))


@app.get("/api/transcripts")
async def api_transcripts(room: str = "", limit: int = 100):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        if room:
            rows = await conn.fetch(
                "SELECT event_type, content, created_at FROM call_events "
                "WHERE room_name=$1 ORDER BY created_at DESC LIMIT $2", room, limit)
        else:
            rows = await conn.fetch(
                "SELECT room_name, event_type, content, created_at FROM call_events "
                "ORDER BY created_at DESC LIMIT $1", limit)
    return JSONResponse(_serialize(rows))


# ── Accounts API ──────────────────────────────────────────────────────────────

class AccountIn(BaseModel):
    mobile: str
    name: str
    bill_amount: str = "₹0"
    due_date: str = "—"
    plan: str = ""
    account_no: str = ""
    last_payment: str = "—"
    notes: str = ""


@app.get("/api/accounts")
async def api_accounts_list():
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT mobile, name, bill_amount, due_date, plan, account_no, last_payment, notes, updated_at "
            "FROM mock_accounts ORDER BY account_no")
    return JSONResponse(_serialize(rows))


@app.post("/api/accounts")
async def api_accounts_upsert(body: AccountIn):
    pool = await _get_pool()
    mobile = body.mobile.strip()
    if not mobile or not body.name.strip():
        raise HTTPException(400, "mobile and name are required")
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO mock_accounts
               (mobile,name,bill_amount,due_date,plan,account_no,last_payment,notes,updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW())
               ON CONFLICT (mobile) DO UPDATE SET
                 name=$2,bill_amount=$3,due_date=$4,plan=$5,
                 account_no=$6,last_payment=$7,notes=$8,updated_at=NOW()""",
            mobile, body.name.strip(), body.bill_amount, body.due_date,
            body.plan, body.account_no, body.last_payment, body.notes)
    return JSONResponse({"ok": True})


@app.delete("/api/accounts/{mobile}")
async def api_accounts_delete(mobile: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM mock_accounts WHERE mobile=$1", mobile)
    if result == "DELETE 0":
        raise HTTPException(404, "Account not found")
    return JSONResponse({"ok": True})


@app.post("/api/seed-dummy")
async def api_seed_dummy():
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM call_events")
    await _seed_dummy_calls(pool)
    return JSONResponse({"ok": True})


# ── Dashboard HTML ─────────────────────────────────────────────────────────────

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Voice Stack — Live Dashboard</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#07090f;--surface:#0d1117;--surface2:#111827;--border:#1e2535;
  --blue:#6366f1;--blue-soft:#818cf8;--green:#10b981;--amber:#f59e0b;
  --red:#ef4444;--purple:#a855f7;--cyan:#22d3ee;
  --text:#e2e8f0;--muted:#4b5563;--subtle:#374151;
}
html,body{height:100%;overflow:hidden}
body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);display:flex;flex-direction:column}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#1e2535;border-radius:9999px}

/* ── Header ── */
header{
  flex-shrink:0;height:56px;
  background:linear-gradient(90deg,#0d1117 0%,#0f1729 100%);
  border-bottom:1px solid var(--border);
  padding:0 20px;display:flex;align-items:center;gap:12px;
  position:relative;overflow:hidden;
}
header::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(99,102,241,.06),transparent);
  animation:shimmer 4s linear infinite;
}
@keyframes shimmer{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.logo{display:flex;align-items:center;gap:8px}
.logo-icon{
  width:30px;height:30px;border-radius:8px;
  background:linear-gradient(135deg,#6366f1,#a855f7);
  display:flex;align-items:center;justify-content:center;font-size:.9rem;flex-shrink:0;
}
.logo-text{font-size:.9rem;font-weight:800;letter-spacing:-.02em;
  background:linear-gradient(90deg,#818cf8,#c084fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.live-pill{
  display:flex;align-items:center;gap:5px;
  background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);
  padding:3px 9px;border-radius:9999px;font-size:.62rem;font-weight:700;
  letter-spacing:.08em;color:#34d399;text-transform:uppercase;
}
.live-dot{width:6px;height:6px;border-radius:50%;background:#10b981;animation:pulse-g 1.5s ease-in-out infinite}
@keyframes pulse-g{0%,100%{box-shadow:0 0 0 0 rgba(16,185,129,.5)}50%{box-shadow:0 0 0 5px rgba(16,185,129,0)}}
.hchip{font-size:.62rem;font-weight:600;padding:3px 9px;border-radius:9999px;
  background:rgba(99,102,241,.15);border:1px solid rgba(99,102,241,.25);color:#818cf8}
.refresh-info{margin-left:auto;display:flex;align-items:center;gap:8px}
.ring-wrap{position:relative;width:28px;height:28px}
.ring-wrap svg{position:absolute;top:0;left:0;transform:rotate(-90deg)}
.ring-label{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.5rem;font-weight:700;color:var(--blue-soft)}

/* ── Tabs ── */
.tabs{
  flex-shrink:0;display:flex;
  background:var(--surface);border-bottom:1px solid var(--border);padding:0 20px;gap:2px;
}
.tab{
  padding:10px 18px;font-size:.78rem;font-weight:500;color:var(--muted);cursor:pointer;
  border-bottom:2px solid transparent;transition:all .18s;display:flex;align-items:center;gap:6px;
}
.tab.active{color:var(--blue-soft);border-bottom-color:var(--blue)}
.tab:hover:not(.active){color:#94a3b8}
.tab-badge{
  background:rgba(99,102,241,.2);color:var(--blue-soft);
  font-size:.58rem;font-weight:700;padding:1px 5px;border-radius:9999px;min-width:16px;text-align:center;
}

/* ── Layout ── */
.page{display:none;flex:1;overflow:hidden}
.page.active{display:flex}

/* ── Calls page ── */
.calls-layout{display:grid;grid-template-columns:320px 1fr;width:100%;height:100%}
.panel{display:flex;flex-direction:column;border-right:1px solid var(--border);overflow:hidden}
.panel:last-child{border-right:none}
.panel-hdr{
  padding:10px 16px;font-size:.65rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  color:var(--muted);border-bottom:1px solid var(--border);background:rgba(13,17,23,.8);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;
}
.panel-hdr-val{color:var(--blue-soft);font-size:.7rem;font-family:'Courier New',monospace;font-weight:400;letter-spacing:0}
.panel-body{overflow-y:auto;flex:1}

/* Stats strip */
.stats-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--border);flex-shrink:0}
.stat{
  background:var(--surface);padding:12px 10px;text-align:center;
  position:relative;overflow:hidden;
}
.stat::after{
  content:'';position:absolute;bottom:0;left:50%;transform:translateX(-50%);
  width:40%;height:1px;background:linear-gradient(90deg,transparent,var(--blue),transparent);
}
.stat-v{font-size:1.5rem;font-weight:800;line-height:1;
  background:linear-gradient(135deg,#818cf8,#c084fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-l{font-size:.58rem;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.07em}

/* Call rows */
.call-row{
  padding:10px 14px;cursor:pointer;border-bottom:1px solid rgba(30,37,53,.6);
  transition:background .1s;position:relative;
}
.call-row::before{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:transparent;transition:.15s}
.call-row:hover::before,.call-row.active::before{background:var(--blue)}
.call-row:hover,.call-row.active{background:rgba(99,102,241,.05)}
.cr-room{font-size:.73rem;color:var(--blue-soft);font-family:'Courier New',monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cr-meta{font-size:.62rem;color:var(--subtle);margin-top:3px;display:flex;gap:8px}
.cr-turns{color:var(--green);font-size:.6rem;font-weight:600}

/* Transcript chat */
.chat-wrap{padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.chat-sys{
  display:flex;justify-content:center;margin:4px 0;
}
.chat-sys-pill{
  font-size:.6rem;font-weight:600;padding:3px 10px;border-radius:9999px;letter-spacing:.04em;
}
.pill-start{background:rgba(16,185,129,.12);color:#34d399;border:1px solid rgba(16,185,129,.2)}
.pill-end{background:rgba(239,68,68,.12);color:#f87171;border:1px solid rgba(239,68,68,.2)}
.bubble-row{display:flex;gap:8px;max-width:88%}
.bubble-row.user{align-self:flex-start}
.bubble-row.agent{align-self:flex-end;flex-direction:row-reverse}
.bubble-avatar{
  width:26px;height:26px;border-radius:50%;flex-shrink:0;margin-top:2px;
  display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;
}
.avatar-user{background:linear-gradient(135deg,#1e40af,#2563eb);color:#93c5fd}
.avatar-agent{background:linear-gradient(135deg,#581c87,#7e22ce);color:#d8b4fe}
.bubble{
  padding:8px 12px;border-radius:12px;font-size:.82rem;line-height:1.5;word-break:break-word;
  max-width:100%;position:relative;
}
.bubble-user{
  background:rgba(30,58,138,.35);border:1px solid rgba(59,130,246,.2);
  border-bottom-left-radius:4px;color:#bfdbfe;
}
.bubble-agent{
  background:rgba(88,28,135,.3);border:1px solid rgba(168,85,247,.2);
  border-bottom-right-radius:4px;color:#e9d5ff;
}
.bubble-meta{
  display:flex;align-items:center;gap:5px;margin-bottom:3px;
}
.bubble-row.agent .bubble-meta{flex-direction:row-reverse}
.badge-stt{
  font-size:.52rem;font-weight:700;padding:1px 5px;border-radius:3px;letter-spacing:.04em;
  background:rgba(59,130,246,.2);color:#60a5fa;border:1px solid rgba(59,130,246,.3);
}
.badge-tts{
  font-size:.52rem;font-weight:700;padding:1px 5px;border-radius:3px;letter-spacing:.04em;
  background:rgba(168,85,247,.2);color:#c084fc;border:1px solid rgba(168,85,247,.3);
}
.bubble-time{font-size:.58rem;color:var(--muted)}
.empty-chat{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100%;gap:10px;color:var(--muted);
}
.empty-chat-icon{font-size:2rem;opacity:.3}
.empty-chat-text{font-size:.78rem;opacity:.6}

/* ── Accounts ── */
.accounts-layout{width:100%;height:100%;display:flex;flex-direction:column;overflow:hidden}
.acct-toolbar{
  padding:10px 16px;display:flex;gap:8px;align-items:center;
  border-bottom:1px solid var(--border);flex-shrink:0;background:var(--surface);
}
.btn{padding:6px 14px;border-radius:8px;font-size:.75rem;font-weight:600;cursor:pointer;border:none;transition:all .15s;display:inline-flex;align-items:center;gap:5px}
.btn-primary{background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;box-shadow:0 2px 8px rgba(99,102,241,.3)}
.btn-primary:hover{box-shadow:0 4px 16px rgba(99,102,241,.5);transform:translateY(-1px)}
.btn-danger{background:linear-gradient(135deg,#991b1b,#b91c1c);color:#fff}
.btn-danger:hover{background:linear-gradient(135deg,#b91c1c,#dc2626)}
.btn-sm{padding:3px 9px;font-size:.68rem}
.btn-ghost{background:rgba(255,255,255,.04);border:1px solid var(--border);color:#94a3b8}
.btn-ghost:hover{background:rgba(255,255,255,.08);color:var(--text)}
.search-box{
  margin-left:auto;padding:6px 12px;
  background:rgba(255,255,255,.03);border:1px solid var(--border);
  border-radius:8px;color:var(--text);font-size:.75rem;outline:none;width:220px;
  transition:border-color .15s,box-shadow .15s;
}
.search-box:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(99,102,241,.15)}

.table-wrap{overflow:auto;flex:1}
table{width:100%;border-collapse:collapse;font-size:.78rem}
thead th{
  background:rgba(13,17,23,.95);padding:9px 14px;text-align:left;
  font-size:.6rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);border-bottom:1px solid var(--border);
  white-space:nowrap;position:sticky;top:0;z-index:2;
}
tbody tr{border-bottom:1px solid rgba(30,37,53,.5);transition:background .1s}
tbody tr:hover{background:rgba(99,102,241,.04)}
tbody td{padding:9px 14px;vertical-align:middle;color:#cbd5e1}
.mobile-cell{font-family:'Courier New',monospace;color:var(--blue-soft);font-weight:600;font-size:.8rem}
.notes-cell{color:var(--muted);font-size:.7rem;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.actions-cell{white-space:nowrap;display:flex;gap:5px}
.badge-bill{
  background:rgba(30,58,138,.4);color:#93c5fd;
  padding:2px 8px;border-radius:5px;font-size:.68rem;font-weight:600;
  border:1px solid rgba(59,130,246,.2);
}
.badge-overdue{background:rgba(69,10,10,.5);color:#fca5a5;border-color:rgba(239,68,68,.2)}
.badge-blocked{background:rgba(120,53,15,.5);color:#fcd34d;border-color:rgba(245,158,11,.2)}

/* ── Modal ── */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);backdrop-filter:blur(4px);z-index:100;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{
  background:var(--surface2);border:1px solid var(--border);border-radius:16px;
  width:520px;max-height:90vh;overflow:auto;
  box-shadow:0 25px 60px rgba(0,0,0,.6),0 0 0 1px rgba(99,102,241,.1);
}
.modal-header{padding:18px 20px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.modal-header h2{font-size:.95rem;font-weight:700}
.modal-close{background:none;border:none;color:var(--muted);font-size:1.1rem;cursor:pointer;padding:2px 6px;border-radius:6px;transition:.15s}
.modal-close:hover{background:rgba(255,255,255,.06);color:var(--text)}
.modal-body{padding:20px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.form-full{grid-column:1/-1}
.form-group label{display:block;font-size:.65rem;font-weight:600;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:.06em}
.form-group input,.form-group textarea{
  width:100%;padding:8px 11px;background:rgba(7,9,15,.7);
  border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.82rem;
  outline:none;transition:border-color .15s,box-shadow .15s;
}
.form-group input:focus,.form-group textarea:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(99,102,241,.15)}
.form-group textarea{resize:vertical;min-height:64px;font-family:inherit}
.modal-footer{padding:14px 20px;border-top:1px solid var(--border);display:flex;justify-content:flex-end;gap:8px}

/* ── Toast ── */
.toast{
  position:fixed;bottom:24px;right:24px;padding:10px 18px;border-radius:10px;
  font-size:.8rem;font-weight:600;z-index:200;
  opacity:0;transform:translateY(8px);transition:all .25s;pointer-events:none;
  backdrop-filter:blur(8px);
}
.toast.show{opacity:1;transform:translateY(0)}
.toast-ok{background:rgba(20,83,45,.9);color:#4ade80;border:1px solid rgba(22,101,52,.8)}
.toast-err{background:rgba(69,10,10,.9);color:#fca5a5;border:1px solid rgba(127,29,29,.8)}
</style>
</head>
<body>

<!-- HEADER -->
<header>
  <div class="logo">
    <div class="logo-icon">🎙</div>
    <span class="logo-text">AI Voice Stack</span>
  </div>
  <div class="live-pill"><div class="live-dot"></div>LIVE</div>
  <span class="hchip" id="pod-chip"></span>
  <div class="refresh-info">
    <span style="font-size:.62rem;color:var(--muted)" id="last-updated"></span>
    <div class="ring-wrap">
      <svg width="28" height="28" viewBox="0 0 28 28">
        <circle cx="14" cy="14" r="11" fill="none" stroke="#1e2535" stroke-width="2.5"/>
        <circle id="ring" cx="14" cy="14" r="11" fill="none" stroke="url(#rg)" stroke-width="2.5"
          stroke-dasharray="69.12" stroke-dashoffset="0" stroke-linecap="round"/>
        <defs>
          <linearGradient id="rg" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#6366f1"/>
            <stop offset="100%" stop-color="#a855f7"/>
          </linearGradient>
        </defs>
      </svg>
      <span class="ring-label" id="countdown">1</span>
    </div>
  </div>
</header>

<!-- TABS -->
<div class="tabs">
  <div class="tab active" onclick="switchTab('calls')">
    📞 Live Calls <span class="tab-badge" id="badge-calls">0</span>
  </div>
  <div class="tab" onclick="switchTab('accounts')">
    👥 Demo Accounts <span class="tab-badge" id="badge-accts">0</span>
  </div>
</div>

<!-- CALLS PAGE -->
<div class="page active" id="page-calls">
  <div class="calls-layout">
    <!-- Left: call list -->
    <div class="panel">
      <div class="stats-strip">
        <div class="stat"><div class="stat-v" id="s-calls">0</div><div class="stat-l">Calls</div></div>
        <div class="stat"><div class="stat-v" id="s-turns">0</div><div class="stat-l">STT Turns</div></div>
        <div class="stat"><div class="stat-v" id="s-avg">0</div><div class="stat-l">Avg Turns</div></div>
      </div>
      <div class="panel-hdr">Recent Calls</div>
      <div class="panel-body" id="call-list"></div>
    </div>
    <!-- Right: transcript -->
    <div class="panel">
      <div class="panel-hdr">
        Conversation
        <span class="panel-hdr-val" id="room-label"></span>
      </div>
      <div class="panel-body" id="transcript-list">
        <div class="empty-chat">
          <div class="empty-chat-icon">💬</div>
          <div class="empty-chat-text">Select a call to view its transcript</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ACCOUNTS PAGE -->
<div class="page" id="page-accounts">
  <div class="accounts-layout">
    <div class="acct-toolbar">
      <button class="btn btn-primary" onclick="openModal()">+ Add Account</button>
      <button class="btn btn-ghost" onclick="resetToDefaults()">↺ Reset Defaults</button>
      <button class="btn btn-ghost" onclick="seedDummyCalls()">🔄 Seed Demo Calls</button>
      <input class="search-box" id="search" placeholder="Search by mobile, name, plan…" oninput="filterAccounts()">
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Mobile</th><th>Name</th><th>Bill</th><th>Due Date</th>
            <th>Plan</th><th>Account No</th><th>Last Payment</th><th>Notes</th><th>Actions</th>
          </tr>
        </thead>
        <tbody id="acct-body"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- MODAL -->
<div class="modal-overlay" id="modal-overlay" onclick="closeModalOutside(event)">
  <div class="modal">
    <div class="modal-header">
      <h2 id="modal-title">Add Demo Account</h2>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="form-grid">
        <div class="form-group">
          <label>Mobile Number *</label>
          <input id="f-mobile" placeholder="9876543210" maxlength="15">
        </div>
        <div class="form-group">
          <label>Customer Name *</label>
          <input id="f-name" placeholder="Ramesh Kumar">
        </div>
        <div class="form-group">
          <label>Bill Amount</label>
          <input id="f-bill" placeholder="₹450">
        </div>
        <div class="form-group">
          <label>Due Date</label>
          <input id="f-due" placeholder="20 Jun 2026">
        </div>
        <div class="form-group form-full">
          <label>Plan</label>
          <input id="f-plan" placeholder="99 GB Data Pack">
        </div>
        <div class="form-group">
          <label>Account No</label>
          <input id="f-accno" placeholder="ACC001">
        </div>
        <div class="form-group">
          <label>Last Payment</label>
          <input id="f-lastpay" placeholder="₹450 on 15 May">
        </div>
        <div class="form-group form-full">
          <label>Notes (special scenarios)</label>
          <textarea id="f-notes" placeholder="e.g. Account blocked due to non-payment, needs ₹320 to unblock"></textarea>
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveAccount()">Save Account</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const REFRESH_MS = 1000;
const CIRC = 69.12;
let selectedRoom = '';
let allAccounts = [];
let editingMobile = null;
let ticking = false;

// ── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',['calls','accounts'][i]===name));
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  if (name==='accounts') loadAccounts();
}

// ── Formatting ─────────────────────────────────────────────────────────────
function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
function fmtRoom(room) {
  const p=room.split('_');
  if (p.length>=4) return p.slice(0,3).join('_')+'…';
  return room.length>28 ? room.slice(0,28)+'…' : room;
}
function esc(s){
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Refresh ring (driven by setInterval at 1s, full circle = REFRESH_MS) ──
let ringAnim = REFRESH_MS;
setInterval(()=>{
  ringAnim = Math.max(0,ringAnim-100);
  const pct = ringAnim/REFRESH_MS;
  document.getElementById('ring').style.strokeDashoffset = CIRC*(1-pct);
  document.getElementById('countdown').textContent = Math.ceil(ringAnim/1000)||1;
},100);

// ── Load calls ─────────────────────────────────────────────────────────────
async function loadCalls() {
  const r = await fetch('/api/calls').catch(()=>null);
  if (!r) return;
  const calls = await r.json();
  document.getElementById('s-calls').textContent = calls.length;
  document.getElementById('badge-calls').textContent = calls.length;
  const totalTurns = calls.reduce((s,c)=>s+(c.turns||0),0);
  document.getElementById('s-turns').textContent = totalTurns;
  document.getElementById('s-avg').textContent = calls.length?(totalTurns/calls.length).toFixed(1):'0';
  const list = document.getElementById('call-list');
  if (!calls.length){
    list.innerHTML='<div style="padding:20px 14px;text-align:center;font-size:.72rem;color:var(--muted)">No calls yet</div>';
    return;
  }
  list.innerHTML = calls.map(c=>{
    const active=c.room_name===selectedRoom?' active':'';
    const dur=c.last_event&&c.started_at
      ?Math.round((new Date(c.last_event)-new Date(c.started_at))/1000)+'s':'';
    return `<div class="call-row${active}" onclick="selectRoom('${esc(c.room_name)}')">
      <div class="cr-room">${esc(fmtRoom(c.room_name))}</div>
      <div class="cr-meta">
        <span>${fmtTime(c.started_at)}</span>
        <span class="cr-turns">↕ ${c.turns} turns</span>
        ${dur?`<span>${dur}</span>`:''}
      </div>
    </div>`;
  }).join('');
}

// ── Load transcripts ────────────────────────────────────────────────────────
async function loadTranscripts() {
  const url = selectedRoom
    ? `/api/transcripts?room=${encodeURIComponent(selectedRoom)}&limit=200`
    : '/api/transcripts?limit=60';
  const r = await fetch(url).catch(()=>null);
  if (!r) return;
  const rows = await r.json();
  const list = document.getElementById('transcript-list');
  if (!rows.length){
    list.innerHTML='<div class="empty-chat"><div class="empty-chat-icon">💬</div><div class="empty-chat-text">No events yet</div></div>';
    return;
  }
  // Reverse so oldest first (API returns newest first)
  const ordered = [...rows].reverse();
  list.innerHTML = '<div class="chat-wrap">' + ordered.map(e=>{
    if (e.event_type==='call_started')
      return `<div class="chat-sys"><span class="chat-sys-pill pill-start">📞 Call Started · ${fmtTime(e.created_at)}</span></div>`;
    if (e.event_type==='call_ended')
      return `<div class="chat-sys"><span class="chat-sys-pill pill-end">📵 Call Ended · ${fmtTime(e.created_at)}</span></div>`;
    if (e.event_type==='user_speech')
      return `<div class="bubble-row user">
        <div class="bubble-avatar avatar-user">👤</div>
        <div>
          <div class="bubble-meta">
            <span class="badge-stt">🎙 STT</span>
            <span class="bubble-time">${fmtTime(e.created_at)}</span>
          </div>
          <div class="bubble bubble-user">${esc(e.content||'')}</div>
        </div>
      </div>`;
    if (e.event_type==='agent_speech')
      return `<div class="bubble-row agent">
        <div class="bubble-avatar avatar-agent">🤖</div>
        <div>
          <div class="bubble-meta">
            <span class="badge-tts">🔊 TTS</span>
            <span class="bubble-time">${fmtTime(e.created_at)}</span>
          </div>
          <div class="bubble bubble-agent">${esc(e.content||'')}</div>
        </div>
      </div>`;
    return '';
  }).join('') + '</div>';
  // Auto-scroll to bottom
  list.scrollTop = list.scrollHeight;
}

function selectRoom(room) {
  selectedRoom = room;
  document.getElementById('room-label').textContent = fmtRoom(room);
  loadTranscripts();
}

// ── Load accounts ────────────────────────────────────────────────────────────
async function loadAccounts() {
  const r = await fetch('/api/accounts').catch(()=>null);
  if (!r) return;
  allAccounts = await r.json();
  document.getElementById('badge-accts').textContent = allAccounts.length;
  renderAccounts(allAccounts);
}

function filterAccounts() {
  const q = document.getElementById('search').value.toLowerCase();
  renderAccounts(q ? allAccounts.filter(a=>
    (a.mobile||'').includes(q)||
    (a.name||'').toLowerCase().includes(q)||
    (a.plan||'').toLowerCase().includes(q)||
    (a.notes||'').toLowerCase().includes(q)
  ) : allAccounts);
}

function billBadgeClass(notes) {
  if (!notes) return 'badge-bill';
  const n=notes.toLowerCase();
  if (n.includes('block')) return 'badge-bill badge-blocked';
  if (n.includes('overdue')||n.includes('late fee')) return 'badge-bill badge-overdue';
  return 'badge-bill';
}

function renderAccounts(list) {
  const tbody = document.getElementById('acct-body');
  if (!list.length){
    tbody.innerHTML='<tr><td colspan="9" style="text-align:center;padding:28px;color:var(--muted)">No accounts found</td></tr>';
    return;
  }
  tbody.innerHTML = list.map(a=>`
    <tr>
      <td class="mobile-cell">${esc(a.mobile)}</td>
      <td>${esc(a.name)}</td>
      <td><span class="${billBadgeClass(a.notes)}">${esc(a.bill_amount||'₹0')}</span></td>
      <td style="color:#94a3b8">${esc(a.due_date||'—')}</td>
      <td style="color:#94a3b8;font-size:.73rem">${esc(a.plan||'')}</td>
      <td style="color:var(--muted);font-family:'Courier New',monospace;font-size:.7rem">${esc(a.account_no||'')}</td>
      <td style="color:var(--muted);font-size:.7rem">${esc(a.last_payment||'—')}</td>
      <td class="notes-cell" title="${(a.notes||'').replace(/"/g,'&quot;')}">${esc(a.notes||'')}</td>
      <td class="actions-cell">
        <button class="btn btn-sm btn-ghost" onclick='editAccount(${JSON.stringify(a)})'>Edit</button>
        <button class="btn btn-sm btn-danger" onclick="deleteAccount('${esc(a.mobile)}','${(a.name||'').replace(/'/g,"\\'")}')">Del</button>
      </td>
    </tr>`).join('');
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function openModal(a) {
  editingMobile = a ? a.mobile : null;
  document.getElementById('modal-title').textContent = a ? 'Edit Account' : 'Add Demo Account';
  document.getElementById('f-mobile').value  = a?.mobile     ||'';
  document.getElementById('f-mobile').disabled = !!a;
  document.getElementById('f-name').value    = a?.name       ||'';
  document.getElementById('f-bill').value    = a?.bill_amount||'';
  document.getElementById('f-due').value     = a?.due_date   ||'';
  document.getElementById('f-plan').value    = a?.plan       ||'';
  document.getElementById('f-accno').value   = a?.account_no ||'';
  document.getElementById('f-lastpay').value = a?.last_payment||'';
  document.getElementById('f-notes').value   = a?.notes      ||'';
  document.getElementById('modal-overlay').classList.add('open');
}
function editAccount(a){openModal(a)}
function closeModal(){document.getElementById('modal-overlay').classList.remove('open')}
function closeModalOutside(e){if(e.target===document.getElementById('modal-overlay'))closeModal()}

async function saveAccount() {
  const mobile = document.getElementById('f-mobile').value.trim()||editingMobile;
  const name   = document.getElementById('f-name').value.trim();
  if (!mobile||!name){showToast('Mobile and name are required','err');return}
  const body = {
    mobile, name,
    bill_amount:  document.getElementById('f-bill').value.trim(),
    due_date:     document.getElementById('f-due').value.trim(),
    plan:         document.getElementById('f-plan').value.trim(),
    account_no:   document.getElementById('f-accno').value.trim(),
    last_payment: document.getElementById('f-lastpay').value.trim(),
    notes:        document.getElementById('f-notes').value.trim(),
  };
  const r = await fetch('/api/accounts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (r.ok){closeModal();showToast('Account saved ✓','ok');await loadAccounts()}
  else showToast('Save failed','err');
}

async function deleteAccount(mobile,name) {
  if (!confirm(`Delete account for ${name} (${mobile})?`)) return;
  const r = await fetch(`/api/accounts/${mobile}`,{method:'DELETE'});
  if (r.ok){showToast('Deleted ✓','ok');await loadAccounts()}
  else showToast('Delete failed','err');
}

async function resetToDefaults() {
  if (!confirm('Reset to 10 default demo accounts?')) return;
  const defaults = [
    {mobile:'9876543210',name:'Ramesh Kumar',bill_amount:'₹450',due_date:'20 Jun 2026',plan:'99 GB Data Pack',account_no:'ACC001',last_payment:'₹450 on 15 May',notes:''},
    {mobile:'9876543211',name:'Priya Sharma',bill_amount:'₹780',due_date:'25 Jun 2026',plan:'Unlimited Calls',account_no:'ACC002',last_payment:'₹780 on 10 May',notes:'Has EMI of ₹199/month for device, next due 25 Jun'},
    {mobile:'9123456789',name:'Amit Patel',bill_amount:'₹320',due_date:'18 Jun 2026',plan:'Basic 2GB/day',account_no:'ACC003',last_payment:'₹320 on 18 May',notes:'Account blocked due to non-payment, needs ₹320 to unblock'},
    {mobile:'8800001234',name:'Sunita Devi',bill_amount:'₹180',due_date:'30 Jun 2026',plan:'Voice Only Pack',account_no:'ACC004',last_payment:'₹180 on 1 Jun',notes:''},
    {mobile:'7700123456',name:'Vijay Singh',bill_amount:'₹1200',due_date:'15 Jun 2026',plan:'5G Premium 200GB',account_no:'ACC005',last_payment:'₹1200 on 15 May',notes:'Bill overdue by 2 days, late fee ₹50 will apply after 20 Jun'},
    {mobile:'9988776655',name:'Kavita Mehta',bill_amount:'₹650',due_date:'22 Jun 2026',plan:'Fiber Broadband 100Mbps',account_no:'ACC006',last_payment:'₹650 on 22 May',notes:''},
    {mobile:'8877665544',name:'Suresh Yadav',bill_amount:'₹0',due_date:'—',plan:'Prepaid 28-day ₹199',account_no:'ACC007',last_payment:'Recharged ₹199',notes:'Prepaid — current balance ₹45, validity expires 8 Jul 2026'},
    {mobile:'7766554433',name:'Deepika Joshi',bill_amount:'₹3500',due_date:'10 Jun 2026',plan:'Enterprise 1Gbps',account_no:'ACC008',last_payment:'₹3500 on 10 May',notes:'Business account, GST: 24AABCS1429B1ZB'},
    {mobile:'9900112233',name:'Mohammed Rafiq',bill_amount:'₹550',due_date:'28 Jun 2026',plan:'Unlimited 5G',account_no:'ACC009',last_payment:'₹550 on 28 May',notes:''},
    {mobile:'8811223344',name:'Lakshmi Nair',bill_amount:'₹230',due_date:'5 Jul 2026',plan:'Student Pack 3GB/day',account_no:'ACC010',last_payment:'₹230 on 5 Jun',notes:''},
  ];
  for (const a of defaults)
    await fetch('/api/accounts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(a)});
  showToast('Default accounts restored ✓','ok');
  await loadAccounts();
}

async function seedDummyCalls() {
  if (!confirm('Re-seed demo call events? (existing call events will be replaced)')) return;
  const r = await fetch('/api/seed-dummy',{method:'POST'});
  if (r.ok) showToast('Demo calls seeded ✓','ok');
  else showToast('Seed failed','err');
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg,type='ok') {
  const t=document.getElementById('toast');
  t.textContent=msg;
  t.className=`toast toast-${type} show`;
  setTimeout(()=>t.classList.remove('show'),2500);
}

// ── Auto-refresh every 1s ─────────────────────────────────────────────────────
async function refresh() {
  if (ticking) return;
  ticking = true;
  try {
    const page=document.querySelector('.page.active').id;
    if (page==='page-calls'){
      await Promise.all([loadCalls(), selectedRoom ? loadTranscripts() : Promise.resolve()]);
    } else {
      await loadAccounts();
    }
    const now=new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
    document.getElementById('last-updated').textContent='Updated '+now;
    ringAnim=REFRESH_MS;
  } finally { ticking=false; }
}

refresh();
setInterval(refresh, REFRESH_MS);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(_HTML)
