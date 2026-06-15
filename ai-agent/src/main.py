import asyncio
import sys
import os
import logging
import threading

import uvicorn
from livekit.agents import WorkerOptions, cli
from .agent import entrypoint
from .db import init_db

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def prewarm(proc) -> None:
    await init_db()


def _start_dashboard():
    """Run the dashboard FastAPI server in a background thread."""
    from .dashboard import app
    port = int(os.environ.get("DASHBOARD_PORT", "8082"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    # Start dashboard server in background thread
    t = threading.Thread(target=_start_dashboard, daemon=True)
    t.start()
    logger.info("Dashboard started on port 8082")

    sys.argv = ["agent", "start"]
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        ws_url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    ))
