"""Background polling loop — periodically fetches recalls and alerts matched users."""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.fetcher import fetch_fda_recalls, fetch_usda_recalls
from src.store import init_db, save_if_new
from src.models import (
    init_models_db,
    get_all_users,
    get_pantry,
    create_alert,
)
from src.agent import parse_recall, match_pantry, generate_alert

logger = logging.getLogger(__name__)

FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))

# Will be set by run.py so the polling loop can push Telegram messages.
_telegram_app = None


def set_telegram_app(app) -> None:
    """Register the running Telegram Application so alerts can be sent."""
    global _telegram_app
    _telegram_app = app


async def _send_telegram_alert(telegram_id: int, text: str, alert_id: int) -> None:
    """Send an alert message via Telegram with feedback buttons."""
    if _telegram_app is None:
        logger.warning("Telegram app not set; cannot send alert to %s", telegram_id)
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Disposed", callback_data=f"feedback:disposed:{alert_id}"),
            InlineKeyboardButton("❌ Ignored", callback_data=f"feedback:ignored:{alert_id}"),
        ]
    ])

    try:
        await _telegram_app.bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("Failed to send Telegram alert to %s", telegram_id)


async def poll_and_alert() -> None:
    """One polling cycle: fetch recalls, match pantries, send alerts."""
    logger.info("Polling for new recalls…")

    init_db()
    init_models_db()

    # 1. Fetch latest recalls from both sources
    fda_items = fetch_fda_recalls(limit=10)
    usda_items = fetch_usda_recalls(limit=10)
    all_items = fda_items + usda_items
    logger.info("Fetched %d FDA + %d USDA recalls", len(fda_items), len(usda_items))

    new_recalls = []
    for item in all_items:
        saved = save_if_new(item)
        if saved:
            new_recalls.append((item, saved))

    if not new_recalls:
        logger.info("No new recalls this cycle.")
        return

    logger.info("%d new recall(s) found — checking user pantries", len(new_recalls))

    # 2. For each new recall, parse with Gemini and match all users' pantries
    users = get_all_users()
    if not users:
        logger.info("No registered users yet.")
        return

    for recall_record, saved_obj in new_recalls:
        parsed = parse_recall(recall_record)

        for user in users:
            pantry = get_pantry(user.id)
            if not pantry:
                continue

            pantry_dicts = [
                {"product_name": p.product_name, "brand": p.brand, "lot_code": p.lot_code}
                for p in pantry
            ]

            matched = match_pantry(parsed, pantry_dicts)
            if not matched:
                continue

            # 3. Generate a personalized alert in the user's language
            alert_text = generate_alert(recall_record, matched, user.language)

            recall_number = recall_record.get("recall_number")
            saved_id = getattr(saved_obj, "id", None)
            alert = create_alert(
                user_id=user.id,
                recall_number=recall_number,
                message=alert_text,
                recall_id=saved_id,
            )

            # 4. Send via Telegram
            await _send_telegram_alert(user.telegram_id, alert_text, alert.id)
            logger.info(
                "Alert #%d sent to user %d (telegram %d) for recall %s",
                alert.id, user.id, user.telegram_id,
                recall_number or "N/A",
            )


def create_scheduler() -> AsyncIOScheduler:
    """Create an APScheduler instance with the polling job."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_and_alert,
        trigger="interval",
        minutes=FETCH_INTERVAL,
        id="recall_poll",
        replace_existing=True,
    )
    return scheduler
