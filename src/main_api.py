"""API entry point for RecallAlert-AI.

Runs FastAPI server + background polling loop.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("recall-agent")


# ──────────────────────────────────────────────────────────────────────────────
# Lifespan (startup + shutdown)
# ──────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    logger.info("🚀 Starting RecallAlert-AI API + polling loop…")

    # Initialize databases
    from src.models import init_models_db
    from src.store import init_db

    init_db()
    init_models_db()

    # Start background polling
    polling_task = asyncio.create_task(run_polling_loop())
    logger.info("✅ Polling loop started in background")

    yield

    logger.info("⏹️ Shutting down…")
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

    from src.store import cleanup
    cleanup()
    logger.info("✅ Cleanup complete")


async def run_polling_loop():
    from src.polling import poll_and_alert

    interval_minutes = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))
    interval_seconds = interval_minutes * 60

    # Run immediately
    logger.info("Running initial poll…")
    try:
        await poll_and_alert()
    except Exception as e:
        logger.exception("Initial poll failed: %s", e)

    # Loop
    while True:
        try:
            logger.info("Sleeping for %d minutes…", interval_minutes)
            await asyncio.sleep(interval_seconds)
            logger.info("Running scheduled poll…")
            await poll_and_alert()
        except asyncio.CancelledError:
            logger.info("Polling loop cancelled")
            break
        except Exception as e:
            logger.exception("Polling error: %s", e)
            await asyncio.sleep(60)


# ──────────────────────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────────────────────

from src.api import app

# Attach lifespan
app.router.lifespan_context = lifespan


# ──────────────────────────────────────────────────────────────────────────────
# Serve React frontend
# ──────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "web" / "dist"   # change to "build" if needed

if FRONTEND_DIR.exists():
    # Serve static assets (JS, CSS, etc.)
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Serve React app for all non-API routes
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(FRONTEND_DIR / "index.html")

    logger.info("📁 Serving React frontend from %s", FRONTEND_DIR)
else:
    logger.warning("⚠️ Frontend build folder not found at %s", FRONTEND_DIR)


# ──────────────────────────────────────────────────────────────────────────────
# Local run (optional)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "src.main_api:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") != "production",
    )