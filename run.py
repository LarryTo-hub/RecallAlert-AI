"""Entry point — starts the background polling loop."""

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("recall-agent")


async def main() -> None:
    from src.models import init_models_db
    from src.store import init_db
    from src.polling import poll_and_alert
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    # Ensure all DB tables exist
    init_db()
    init_models_db()

    # Run one poll immediately on startup
    logger.info("Running initial poll…")
    await poll_and_alert()

    # Start the scheduler (background polling)
    interval = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))
    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_and_alert, "interval", minutes=interval, id="recall_poll")
    scheduler.start()
    logger.info("Scheduler started — polling every %s min", interval)

    # Keep running until interrupted
    try:
        stop_event = asyncio.Event()
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down…")
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
