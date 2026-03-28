"""Entry point — starts the background polling loop and the Telegram bot together."""

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
    from src.store import init_db, cleanup
    from src.bot import build_bot
    from src.polling import create_scheduler, set_telegram_app, poll_and_alert

    # Ensure all DB tables exist
    init_db()
    init_models_db()

    # Build the Telegram bot
    app = build_bot()
    set_telegram_app(app)

    # Start the scheduler (background polling)
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Background scheduler started (polling every %s min)", os.getenv("FETCH_INTERVAL_MINUTES", "60"))

    # Run one poll immediately on startup
    logger.info("Running initial poll…")
    await poll_and_alert()

    # Start the Telegram bot (blocking)
    logger.info("Starting Telegram bot…")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Keep running until interrupted
    try:
        stop_event = asyncio.Event()
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received…")
    finally:
        logger.info("Performing cleanup…")
        scheduler.shutdown(wait=False)
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        cleanup()  # Close database connections
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
