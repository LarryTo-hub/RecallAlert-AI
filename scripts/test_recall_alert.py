"""Test: summarize a sample recall with Gemini, then send an email.

1. Copy .env.example to .env and fill in GOOGLE_API_KEY, SMTP_USER, SMTP_PASS.
2. Set TEST_EMAIL in .env to the address you want to receive the test alert.
3. Set ALLOW_SEND=true in .env when you are ready to actually send email
   (leave as false to see a dry-run log instead).
4. Run from the project root:
       python scripts/test_recall_alert.py
"""

import json
import logging
import os
import sys

# Allow imports from the project root (src/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.agent import parse_recall
from src.notifier import send_email_smtp

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


SAMPLE_RECALL = {
    "product_description": "Jif Peanut Butter (various sizes, creamy and crunchy)",
    "reason_for_recall": "Potential Salmonella contamination",
    "company_name": "J.M. Smucker Co.",
    "brand_name": "Jif",
    "recall_initiation_date": "May 20, 2022",
    "distribution_pattern": "Nationwide (United States)",
}

def main():
    print("=" * 60)
    print("Step 1 — Gemini recall parsing")
    print("=" * 60)

    result = parse_recall(SAMPLE_RECALL)

    print("\nStructured JSON from Gemini:")
    print(json.dumps(result, indent=2))

    # Build a human-readable email body from the structured output
    products = ", ".join(result.get("products", [])) or "N/A"
    brands   = ", ".join(result.get("brands", [])) or "N/A"
    lot_codes = ", ".join(result.get("lot_codes", [])) or "N/A"
    body = f"""\
SafePantry / RecallAlert — Food Recall Alert

Products:       {products}
Brands:         {brands}
Severity:       {result.get('severity', 'N/A')}
Lot codes:      {lot_codes}
Reason:         {result.get('reason_summary', 'N/A')}

---
This is an automated alert from RecallAlert AI.
"""

    print("\n" + "=" * 60)
    print("Step 2 — Send email via Gmail SMTP")
    print("=" * 60)

    to_email = os.getenv("TEST_EMAIL", "").strip()
    if not to_email:
        print("\nTIP: Set TEST_EMAIL in your .env to receive the alert email.")
        to_email = os.getenv("SMTP_USER", "test@example.com")

    subject = f"[RecallAlert] {result.get('severity', 'unknown').title()} Severity — Food Recall Notice"

    send_email_smtp(subject=subject, body=body, to_email=to_email)

    print("\nDone.")


if __name__ == "__main__":
    main()
