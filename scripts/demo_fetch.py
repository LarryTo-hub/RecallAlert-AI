"""Demo script: fetch recent FDA recalls, save to demo/recalls_demo.json, print a short summary."""
import os
import json
from pathlib import Path
import sys

# Ensure project root is on sys.path so `src` package imports work when running scripts directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.fetcher import fetch_fda_recalls

OUT_DIR = Path(__file__).resolve().parents[1] / "demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_demo(limit: int = 5):
    items = fetch_fda_recalls(limit=limit)
    out_file = OUT_DIR / "recalls_demo.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    print(f"Fetched {len(items)} recalls. Saved to {out_file}")
    # Print a short table-like summary
    for i, it in enumerate(items, 1):
        rn = it.get("recall_number") or "<no-recall-number>"
        prod = (it.get("product_description") or "")[:80]
        date = it.get("report_date") or it.get("recall_initiation_date") or ""
        print(f"{i:2}. {rn:12} | {date:10} | {prod}")


if __name__ == "__main__":
    run_demo(5)