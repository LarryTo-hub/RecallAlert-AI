"""Cloud Function: Polling trigger (called by Cloud Scheduler every 60 minutes).

Deploy with:
  gcloud functions deploy poll_recalls \
    --gen2 \
    --runtime python311 \
    --region us-central1 \
    --source functions \
    --entry-point poll_recalls \
    --trigger-topic recall-poll \
    --set-env-vars ENVIRONMENT=production,STORE_BACKEND=firebase
"""

import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mark as production to force Firestore
os.environ.setdefault("ENVIRONMENT", "production")
os.environ.setdefault("STORE_BACKEND", "firebase")

from src.fetcher import fetch_fda_recalls, fetch_usda_recalls
from src.store import init_db, save_if_new, cleanup
from src.models import init_models_db, get_all_users, get_pantry, create_alert
from src.agent import parse_recall, match_pantry, generate_alert
from src.notifier import notify_users


async def send_telegram_alert(telegram_id: int, text: str, alert_id: int) -> None:
    """Send alert via Telegram (requires TELEGRAM_BOT_TOKEN in env)."""
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import Application

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.warning("TELEGRAM_BOT_TOKEN not set; skipping Telegram alert")
            return

        app = Application.builder().token(token).build()

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Disposed", callback_data=f"feedback:disposed:{alert_id}"),
                InlineKeyboardButton("❌ Ignored", callback_data=f"feedback:ignored:{alert_id}"),
            ]
        ])

        await app.bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception("Failed to send Telegram alert to %s", telegram_id)


def poll_recalls(event, context):
    """HTTP Cloud Function triggered by Cloud Scheduler via Cloud Tasks.

    Args:
        event: Cloud Functions event (unused, triggers via HTTP)
        context: Cloud Functions context
    """
    import asyncio

    try:
        logger.info("Starting recall polling cycle…")

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
            return {"status": "ok", "new_recalls": 0}

        logger.info("%d new recall(s) found — checking user pantries", len(new_recalls))

        # 2. For each new recall, parse with Gemini and match all users' pantries
        users = get_all_users()
        if not users:
            logger.info("No registered users yet.")
            return {"status": "ok", "new_recalls": len(new_recalls), "alerted_users": 0}

        alert_count = 0
        for recall_record, saved_obj in new_recalls:
            parsed = parse_recall(recall_record)
            logger.info("Parsed recall: %s", parsed.get("products", [])[:2])

            for user in users:
                pantry = get_pantry(user.id)
                if not pantry:
                    continue

                match_result = match_pantry(parsed, [p.product_name for p in pantry])
                if not match_result.get("matches"):
                    continue

                # Build alert message
                alert_text = generate_alert(parsed, user.language, match_result)
                alert_obj = create_alert(
                    user_id=user.id,
                    recall_number=parsed.get("recall_number"),
                    message=alert_text,
                )

                # Send via Telegram
                try:
                    asyncio.run(send_telegram_alert(user.telegram_id, alert_text, alert_obj.id))
                    alert_count += 1
                    logger.info("Alert sent to user %d", user.telegram_id)
                except Exception:
                    logger.exception("Failed to alert user %d", user.telegram_id)

        logger.info("Polling cycle complete. Alerted %d users.", alert_count)
        cleanup()
        return {
            "status": "ok",
            "new_recalls": len(new_recalls),
            "alerted_users": alert_count,
        }

    except Exception as e:
        logger.exception("Error in polling cycle: %s", e)
        cleanup()
        return {"status": "error", "error": str(e)}, 500


if __name__ == "__main__":
    # Local test
    import asyncio
    poll_recalls({}, None)
