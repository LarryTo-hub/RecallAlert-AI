"""Demo script: fetch recent FDA and USDA recalls, save to demo/recalls_demo.json, print a short summary."""
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.fetcher import fetch_fda_recalls, fetch_usda_recalls

OUT_DIR = PROJECT_ROOT / "demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_demo(limit: int = 5):
    fda_items = fetch_fda_recalls(limit=limit, sort_field="report_date")
    try:
        usda_items = fetch_usda_recalls(limit=limit)
    except Exception:
        usda_items = []

    output = {
        "fda": fda_items,
        "usda": usda_items,
    }

    out_file = OUT_DIR / "recalls_demo.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Saved latest {limit} FDA and USDA recalls to {out_file}")

    print("\nFDA:")
    for i, item in enumerate(fda_items, 1):
        status = item.get("status") or "N/A"
        date_value = item.get("report_date") or "N/A"
        brand_name = item.get("brand_name") or item.get("brand_names") or "N/A"
        company_name = item.get("company_name") or "N/A"
        affected_area = item.get("affected_area") or "N/A"
        product_description = (item.get("product_description") or "")[:60]
        print(
            f"{i}. Product: {product_description} | "
            f"Brand(s): {brand_name} | "
            f"Active: {status} | "
            f"Date: {date_value} | "
            f"Company: {company_name} | "
            f"Area: {affected_area}"
        )

    print("\nUSDA:")
    if not usda_items:
        print("USDA feed unavailable or timed out.")
    else:
        for i, item in enumerate(usda_items, 1):
            status = item.get("status") or "N/A"
            date_value = item.get("report_date") or "N/A"
            company_name = item.get("company_name") or "N/A"
            affected_area = item.get("affected_area") or "N/A"
            product_description = (item.get("product_description") or "")[:60]
            print(
                f"{i}. Product: {product_description} | "
                f"Active: {status} | "
                f"Date: {date_value} | "
                f"Company: {company_name} | "
                f"Area: {affected_area}"
            )


if __name__ == "__main__":
    run_demo(5)