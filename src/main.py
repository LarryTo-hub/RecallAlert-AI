"""Small runner: fetch FDA recalls once and persist any new ones."""
import logging
from src.fetcher import fetch_fda_recalls
from src.store import init_db, save_if_new
from src.notifier import notify_stub


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recall-agent")


def run_once():
    init_db()
    items = fetch_fda_recalls(10)
    logger.info("Fetched %d items", len(items))
    new_count = 0
    for it in items:
        saved = save_if_new(it)
        if saved:
            new_count += 1
            notify_stub(f"Recall: {saved.recall_number}", saved.product_description or "", [])
    logger.info("New records saved: %d", new_count)


if __name__ == "__main__":
    run_once()
