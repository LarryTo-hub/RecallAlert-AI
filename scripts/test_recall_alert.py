"""Test: summarize a sample recall with Gemini, then send an email.

1. Copy .env.example to .env and fill in GEMINI_API_KEY, SMTP_USER, SMTP_PASS.
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
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.example"))

from src.agent import summarize_recall
from src.notifier import send_email_smtp

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


SAMPLE_RECALL = """
Product: Jif Peanut Butter (various sizes, creamy and crunchy)
Reason: Potential Salmonella contamination
Company: J.M. Smucker Co.
Recall date: May 20, 2022
Lot codes: 1274425 through 2140425 (any product with "2111" in the code)
Distribution: Nationwide (United States)

Consumers should not eat the recalled products and should throw them away or
return them to the store for a refund. Salmonella can cause serious illness,
especially in young children, the elderly, and people with weakened immune
systems. Symptoms include diarrhea, fever, and stomach cramps.
"""

def main():
    print("=" * 60)
    print("Step 1 — Gemini recall summarization")
    print("=" * 60)

    result = summarize_recall(SAMPLE_RECALL)

    print("\nStructured JSON from Gemini:")
    print(json.dumps(result, indent=2))

    # Build a human-readable email body from the structured output
    action_steps = "\n".join(f"  • {s}" for s in result.get("action_steps", []))
    identifiers  = ", ".join(result.get("key_identifiers", [])) or "N/A"
    body = f"""\
SafePantry / RecallAlert — Food Recall Alert

Summary:        {result.get('summary', 'N/A')}
Risk level:     {result.get('risk_level', 'N/A')}
Who is affected: {result.get('who_is_affected', 'N/A')}
Key identifiers: {identifiers}

What you should do:
{action_steps}

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

    subject = f"[RecallAlert] {result.get('risk_level', 'Unknown')} Risk — Food Recall Notice"

    send_email_smtp(subject=subject, body=body, to_email=to_email)

    print("\nDone.")


if __name__ == "__main__":
    main()
