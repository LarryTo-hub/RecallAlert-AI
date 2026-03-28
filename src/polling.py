"""Background polling loop — periodically fetches recalls and alerts matched users."""

from __future__ import annotations

import logging
import os

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
from src.notifier import send_email_smtp

logger = logging.getLogger(__name__)

FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))


async def broadcast_alert(user_id: int, alert_message: dict):
    """Broadcast alert to user via WebSocket if connected.
    
    This will be called by polling loop when alerts match user's pantry.
    If user is connected via WebSocket, they'll receive the alert in real-time.
    """
    try:
        from src.api import broadcast_alert as api_broadcast
        await api_broadcast(user_id, alert_message)
    except Exception as e:
        logger.exception("Failed to broadcast alert to user %d: %s", user_id, e)


async def poll_and_alert() -> None:
    """One polling cycle: fetch recalls, match pantries, send alerts via WebSocket."""
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

    alert_count = 0
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

            # 4. Broadcast via WebSocket (if user is connected)
            alert_payload = {
                "type": "recall_alert",
                "alert_id": alert.id,
                "recall_number": recall_number or "N/A",
                "message": alert_text,
                "products": parsed.get("products", []),
                "severity": parsed.get("severity", "unknown"),
            }
            await broadcast_alert(user.id, alert_payload)

            # 5. Send email alert if user has an email registered
            if user.email:
                try:
                    subject = (
                        f"[RecallAlert] {parsed.get('severity', 'unknown').title()} Severity"
                        f" — {recall_record.get('product_description', 'Food Recall')}"
                    )
                    send_email_smtp(subject=subject, body=alert_text, to_email=user.email)
                except Exception:
                    logger.exception("Failed to send email alert to %s", user.email)

            alert_count += 1

            logger.info(
                "Alert #%d created for user %d for recall %s",
                alert.id, user.id, recall_number or "N/A",
            )

    logger.info("Polling cycle complete. Created %d alerts.", alert_count)
