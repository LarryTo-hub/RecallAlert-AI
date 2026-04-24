"""Background polling loop — periodically fetches recalls and alerts matched users."""

from __future__ import annotations

import logging
import os

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.fetcher import fetch_fda_recalls, fetch_usda_recalls, iter_fda_recalls_pages
from src.store import init_db, save_if_new, get_recall_count
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


async def _full_historical_usda_fetch() -> None:
    """Fetch all USDA records, saving to DB. Runs concurrently with FDA fetch."""
    import asyncio
    import functools

    loop = asyncio.get_event_loop()
    logger.info("Historical USDA fetch started…")
    try:
        usda_items = await loop.run_in_executor(None, functools.partial(fetch_usda_recalls, limit=None))
        for item in usda_items:
            save_if_new(item)
        logger.info("Historical USDA fetch complete — %d USDA recalls saved, %d total in DB", len(usda_items), get_recall_count())
    except Exception as exc:
        logger.warning("Historical USDA fetch failed: %s", exc)


async def _full_historical_fetch() -> None:
    """Fetch all FDA + USDA records back to 2014, saving to DB page-by-page.

    Runs in the background after the initial seed so the website has data
    immediately while the full history loads progressively.
    FDA and USDA are fetched concurrently so USDA doesn't wait for FDA to finish.
    """
    import asyncio
    import functools

    loop = asyncio.get_event_loop()
    logger.info("Full historical fetch started — FDA + USDA running concurrently…")

    # Launch USDA concurrently so it doesn't wait for all FDA pages to complete
    usda_task = asyncio.create_task(_full_historical_usda_fetch())

    # FDA: iterate page-by-page via the generator so records are saved
    # progressively and the website shows data after the very first page.
    gen = iter_fda_recalls_pages()
    page_num = 0

    def _next_page(g):
        try:
            return next(g)
        except StopIteration:
            return None

    while True:
        try:
            page = await loop.run_in_executor(None, _next_page, gen)
        except Exception as exc:
            logger.warning("Historical fetch page error: %s", exc)
            break
        if page is None:
            break
        for item in page:
            save_if_new(item)
        page_num += 1
        if page_num % 10 == 0:
            logger.info("Historical fetch: %d pages processed (%d total recalls in DB)", page_num, get_recall_count())

    logger.info("Full historical FDA fetch complete — %d recalls in DB", get_recall_count())
    await usda_task


async def poll_and_alert() -> None:
    """One polling cycle: fetch recalls, match pantries, send alerts via WebSocket."""
    import asyncio
    import functools

    logger.info("Polling for new recalls…")

    init_db()
    init_models_db()

    loop = asyncio.get_event_loop()

    # On the very first run the store is empty: immediately seed with the most
    # recent 200 FDA records so the website has data right away, then launch
    # a background task to fetch all historical records (back to 2014) page by
    # page.  On subsequent runs only a recent batch is fetched.
    # All blocking HTTP fetches run in a thread pool so the event loop stays free.
    store_count = get_recall_count()
    if store_count == 0:
        logger.info("Empty store — seeding with recent records so the website loads immediately…")
        # Fetch recent FDA and USDA concurrently for fast initial seed
        recent_fda_task = loop.run_in_executor(None, functools.partial(fetch_fda_recalls, limit=200))
        recent_usda_task = loop.run_in_executor(None, functools.partial(fetch_usda_recalls, limit=50))
        recent_fda, recent_usda = await asyncio.gather(recent_fda_task, recent_usda_task)
        for item in recent_fda:
            save_if_new(item)
        for item in recent_usda:
            save_if_new(item)
        logger.info("Seeded %d FDA + %d USDA recalls — launching full historical fetch in background…", len(recent_fda), len(recent_usda))
        # Full historical fetch (2014→now) runs in the background — no awaiting
        asyncio.create_task(_full_historical_fetch())
        fda_items = recent_fda
        usda_items = recent_usda
    else:
        fda_items = await loop.run_in_executor(None, functools.partial(fetch_fda_recalls, limit=200))
        usda_items = await loop.run_in_executor(None, functools.partial(fetch_usda_recalls, limit=50))

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

    import time as _time
    alert_count = 0
    for recall_record, saved_obj in new_recalls:
        parsed = parse_recall(recall_record)
        _time.sleep(4)  # 15 req/min free-tier limit → space calls 4s apart

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
