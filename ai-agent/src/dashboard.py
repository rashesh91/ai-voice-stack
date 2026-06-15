"""Lightweight web dashboard — shows live STT, TTS, and latency metrics."""
import asyncio
import datetime
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse


def _serialize(rows) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        d = {}
        for k, v in dict(row).items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                d[k] = v.isoformat()
            else:
                d[k] = v
        result.append(d)
    return result

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    dsn = (
        f"postgresql://{os.environ.get('POSTGRES_USER', 'aivoice')}"
        f":{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST', 'postgres')}"
        f":{os.environ.get('POSTGRES_PORT', '5432')}"
        f"/{os.environ.get('POSTGRES_DB', 'aivoice')}"
    )
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return _pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await _get_pool()
    except Exception:
        logger.exception("Dashboard DB connect failed")
    yield
    if _pool:
        await _pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/api/calls")
async def api_calls():
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT room_name,
                   MIN(created_at) AS started_at,
                   MAX(created_at) AS last_event,
                   COUNT(*) FILTER (WHERE event_type = 'user_speech') AS turns
            FROM call_events
            GROUP BY room_name
            ORDER BY started_at DESC
            LIMIT 20
        """)
    return JSONResponse(_serialize(rows))


@app.get("/api/transcripts")
async def api_transcripts(room: str = "", limit: int = 50):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        if room:
            rows = await conn.fetch(
                "SELECT event_type, content, created_at FROM call_events "
                "WHERE room_name = $1 ORDER BY created_at DESC LIMIT $2",
                room, limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT room_name, event_type, content, created_at FROM call_events "
                "ORDER BY created_at DESC LIMIT $1",
                limit,
            )
    return JSONResponse(_serialize(rows))


@app.get("/api/latency")
async def api_latency():
    """Read latency stats from the last 50 call_started events."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT room_name, created_at
            FROM call_events
            WHERE event_type = 'call_started'
            ORDER BY created_at DESC
            LIMIT 50
        """)
    return JSONResponse(_serialize(rows))


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Voice Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
  header { background: #1e293b; padding: 16px 24px; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.25rem; font-weight: 600; }
  .badge { background: #22c55e; color: #fff; font-size: 0.7rem; padding: 2px 8px; border-radius: 9999px; }
  .grid { display: grid; grid-template-columns: 320px 1fr; gap: 16px; padding: 16px; height: calc(100vh - 57px); }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; }
  .card-header { padding: 12px 16px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }
  .card-body { overflow-y: auto; flex: 1; }
  .call-item { padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #1e293b; transition: background 0.1s; }
  .call-item:hover, .call-item.active { background: #0f172a; }
  .call-item .room { font-size: 0.8rem; color: #60a5fa; font-family: monospace; }
  .call-item .meta { font-size: 0.7rem; color: #64748b; margin-top: 2px; }
  .evt { padding: 8px 16px; border-bottom: 1px solid #1e293b; display: flex; gap: 12px; align-items: flex-start; }
  .evt-time { font-size: 0.68rem; color: #64748b; white-space: nowrap; padding-top: 2px; min-width: 60px; }
  .evt-badge { font-size: 0.65rem; padding: 1px 6px; border-radius: 4px; white-space: nowrap; margin-top: 2px; }
  .badge-speech { background: #1d4ed8; color: #bfdbfe; }
  .badge-started { background: #14532d; color: #bbf7d0; }
  .badge-ended { background: #7f1d1d; color: #fecaca; }
  .evt-content { font-size: 0.82rem; line-height: 1.4; flex: 1; }
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 12px; }
  .stat { background: #0f172a; border-radius: 6px; padding: 10px 14px; text-align: center; }
  .stat-val { font-size: 1.5rem; font-weight: 700; color: #60a5fa; }
  .stat-lbl { font-size: 0.65rem; color: #64748b; margin-top: 2px; text-transform: uppercase; }
  .pulse { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .hint { font-size: 0.7rem; color: #475569; padding: 12px 16px; }
</style>
</head>
<body>
<header>
  <div class="pulse"></div>
  <h1>AI Voice Call Dashboard</h1>
  <span class="badge">LIVE</span>
  <span id="refresh-indicator" style="font-size:0.7rem;color:#64748b;margin-left:auto"></span>
</header>
<div class="grid">
  <div class="card">
    <div class="card-header">Recent Calls <span id="call-count" style="color:#60a5fa">0</span></div>
    <div class="stats">
      <div class="stat"><div class="stat-val" id="total-calls">0</div><div class="stat-lbl">Total Calls</div></div>
      <div class="stat"><div class="stat-val" id="total-turns">0</div><div class="stat-lbl">Turns</div></div>
      <div class="stat"><div class="stat-val" id="avg-turns">0</div><div class="stat-lbl">Avg Turns</div></div>
    </div>
    <div class="card-body" id="call-list"></div>
  </div>
  <div class="card">
    <div class="card-header" id="transcript-header">Transcripts <span id="selected-room" style="color:#60a5fa;font-size:0.7rem;font-family:monospace;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></span></div>
    <div class="card-body" id="transcript-list">
      <div class="hint">← Select a call to see its transcript, or view all recent events</div>
    </div>
  </div>
</div>
<script>
let selectedRoom = '';
let calls = [];

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
function fmtRoomShort(room) {
  const parts = room.split('_');
  return parts.length >= 3 ? parts.slice(0,3).join('_') + '...' : room;
}

async function loadCalls() {
  try {
    const r = await fetch('/api/calls'); calls = await r.json();
    document.getElementById('call-count').textContent = calls.length;
    document.getElementById('total-calls').textContent = calls.length;
    const totalTurns = calls.reduce((s,c) => s + (c.turns||0), 0);
    document.getElementById('total-turns').textContent = totalTurns;
    document.getElementById('avg-turns').textContent = calls.length ? (totalTurns/calls.length).toFixed(1) : '0';
    const list = document.getElementById('call-list');
    list.innerHTML = calls.map(c => {
      const active = c.room_name === selectedRoom ? ' active' : '';
      const duration = c.last_event && c.started_at
        ? Math.round((new Date(c.last_event) - new Date(c.started_at))/1000) + 's'
        : '';
      return `<div class="call-item${active}" onclick="selectRoom('${c.room_name}')">
        <div class="room">${fmtRoomShort(c.room_name)}</div>
        <div class="meta">${fmtTime(c.started_at)} · ${c.turns} turns · ${duration}</div>
      </div>`;
    }).join('');
  } catch(e) { console.error('loadCalls:', e); }
}

async function loadTranscripts() {
  try {
    const url = selectedRoom ? `/api/transcripts?room=${encodeURIComponent(selectedRoom)}&limit=100` : '/api/transcripts?limit=50';
    const r = await fetch(url);
    const rows = await r.json();
    const list = document.getElementById('transcript-list');
    if (!rows.length) { list.innerHTML = '<div class="hint">No events yet</div>'; return; }
    list.innerHTML = rows.map(e => {
      const badge = e.event_type === 'user_speech'
        ? '<span class="evt-badge badge-speech">STT</span>'
        : e.event_type === 'call_started'
        ? '<span class="evt-badge badge-started">START</span>'
        : '<span class="evt-badge badge-ended">END</span>';
      const room = e.room_name ? `<span style="font-size:0.65rem;color:#475569;display:block">${fmtRoomShort(e.room_name)}</span>` : '';
      return `<div class="evt">
        <span class="evt-time">${fmtTime(e.created_at)}</span>
        ${badge}
        <span class="evt-content">${room}${e.content || ''}</span>
      </div>`;
    }).join('');
  } catch(e) { console.error('loadTranscripts:', e); }
}

function selectRoom(room) {
  selectedRoom = room;
  document.getElementById('selected-room').textContent = room ? fmtRoomShort(room) : '';
  loadTranscripts();
}

async function refresh() {
  await Promise.all([loadCalls(), loadTranscripts()]);
  document.getElementById('refresh-indicator').textContent = 'Updated ' + new Date().toLocaleTimeString();
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(_DASHBOARD_HTML)
