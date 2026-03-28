"""API entry point for RecallAlert-AI.

Runs FastAPI server + background polling loop.

Deploy to Cloud Run with:
  gcloud run deploy recall-alert-api \
    --source . \
    --set-env-vars ENVIRONMENT=production,STORE_BACKEND=firebase
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("recall-agent")


@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown logic for FastAPI app."""
    logger.info("🚀 Starting RecallAlert-AI API + polling loop…")

    # Initialize databases
    from src.models import init_models_db
    from src.store import init_db

    init_db()
    init_models_db()

    # Start background polling task
    from src.polling import poll_and_alert

    polling_task = asyncio.create_task(run_polling_loop())
    logger.info("✅ Polling loop started in background")

    yield

    logger.info("⏹️  Shutting down…")
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

    from src.store import cleanup

    cleanup()
    logger.info("✅ Cleanup complete")


async def run_polling_loop():
    """Run polling loop every N minutes."""
    import time

    from src.polling import poll_and_alert

    interval_minutes = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))
    interval_seconds = interval_minutes * 60

    # Run first poll immediately
    logger.info("Running initial poll…")
    try:
        await poll_and_alert()
    except Exception as e:
        logger.exception("Initial poll failed: %s", e)

    # Then run on schedule
    while True:
        try:
            logger.info("Sleeping for %d minutes until next poll…", interval_minutes)
            await asyncio.sleep(interval_seconds)
            logger.info("Running scheduled poll…")
            await poll_and_alert()
        except asyncio.CancelledError:
            logger.info("Polling loop cancelled")
            break
        except Exception as e:
            logger.exception("Polling error (will retry): %s", e)
            await asyncio.sleep(60)  # Wait 1 min before retry


# Create FastAPI app with lifespan
from src.api import app
from fastapi.staticfiles import StaticFiles

# Serve React app static files
web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="static")
    logger.info("📁 Mounted React static files from %s", web_dist)

app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") != "production",
    )
