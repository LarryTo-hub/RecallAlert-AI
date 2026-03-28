"""Background worker for Render: Continuous polling for recalls.

This runs as a separate Render background worker service.
It continuously polls for recalls and broadcasts alerts via WebSocket.

Entry point: python -m src.polling_worker
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("recall-poller-worker")

# Mark as production to force Firestore
os.environ.setdefault("ENVIRONMENT", "production")
os.environ.setdefault("STORE_BACKEND", "firebase")


async def main():
    """Run polling loop continuously."""
    from src.models import init_models_db
    from src.store import init_db, cleanup
    from src.polling import poll_and_alert

    logger.info("🚀 Starting RecallAlert-AI Background Polling Worker…")

    init_db()
    init_models_db()

    interval_minutes = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))
    interval_seconds = interval_minutes * 60

    try:
        # Run first poll immediately
        logger.info("Running initial poll…")
        await poll_and_alert()

        # Then run on schedule
        while True:
            logger.info("Sleeping for %d minutes until next poll…", interval_minutes)
            await asyncio.sleep(interval_seconds)
            logger.info("Running scheduled poll…")
            await poll_and_alert()

    except KeyboardInterrupt:
        logger.info("Polling worker interrupted")
    except Exception as e:
        logger.exception("Fatal error in polling worker: %s", e)
        sys.exit(1)
    finally:
        cleanup()
        logger.info("Polling worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
