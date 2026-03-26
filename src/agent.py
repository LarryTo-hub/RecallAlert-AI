"""Gemini-powered agent for recall parsing, pantry matching, OCR, and alerts."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from pathlib import Path
from dotenv import load_dotenv
import langchain
import langgraph

# Ensure .env is loaded from the project root regardless of cwd
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

from google import genai

logger = logging.getLogger(__name__)

# ── Gemini setup ──────────────────────────────────────────────────────────

_client: genai.Client | None = None
_MODEL = "gemini-2.0-flash"


def _get_client() -> genai.Client:
    """Lazy-init the Gemini client so imports succeed without an API key."""
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set in .env")
        _client = genai.Client(api_key=api_key)
    return _client


# ── Recall parsing ────────────────────────────────────────────────────────

def parse_recall(recall: Dict[str, Any]) -> Dict[str, Any]:
    """Use Gemini to extract structured fields from a raw recall record.

    Returns dict with: products, brands, severity, lot_codes, reason_summary
    """
    prompt = (
        "You are a food-safety analyst. Given the following recall record, "
        "extract structured information. Return ONLY a valid JSON object with "
        "these keys:\n"
        '  "products": list of product name strings,\n'
        '  "brands": list of brand name strings,\n'
        '  "severity": "high" | "medium" | "low",\n'
        '  "lot_codes": list of lot/batch code strings (empty list if none),\n'
        '  "reason_summary": one-sentence plain-English summary of the recall reason\n\n'
        f"Recall record:\n{json.dumps(recall, default=str, indent=2)}"
    )

    try:
        resp = _get_client().models.generate_content(model=_MODEL, contents=prompt)
        text = resp.text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        return json.loads(text)
    except Exception:
        logger.exception("Gemini parse_recall failed; returning fallback")
        return {
            "products": [recall.get("product_description", "")],
            "brands": [b for b in [recall.get("brand_name")] if b],
            "severity": "medium",
            "lot_codes": [],
            "reason_summary": recall.get("reason_for_recall", ""),
        }


# ── Pantry matching ───────────────────────────────────────────────────────

def match_pantry(parsed_recall: Dict[str, Any],
                 pantry_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use Gemini to find which pantry items match a parsed recall.

    pantry_items: list of dicts with keys product_name, brand, lot_code.
    Returns list of matched pantry item dicts.
    """
    if not pantry_items:
        return []

    prompt = (
        "You are a food-safety matching engine. Given a recall and a user's "
        "pantry list, determine which pantry items are likely affected.\n\n"
        "Return ONLY a valid JSON array of indices (0-based) of the pantry "
        "items that match. If none match, return an empty array [].\n\n"
        "Consider partial name matches, brand matches, and lot code matches. "
        "Err on the side of caution — if a pantry item COULD be affected, "
        "include it.\n\n"
        f"Recall:\n{json.dumps(parsed_recall, default=str, indent=2)}\n\n"
        f"Pantry items:\n{json.dumps(pantry_items, default=str, indent=2)}"
    )

    try:
        resp = _get_client().models.generate_content(model=_MODEL, contents=prompt)
        text = resp.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        indices = json.loads(text)
        return [pantry_items[i] for i in indices if 0 <= i < len(pantry_items)]
    except Exception:
        logger.exception("Gemini match_pantry failed; falling back to keyword match")
        # Simple keyword fallback
        recall_words = set()
        for p in parsed_recall.get("products", []):
            recall_words.update(w.lower() for w in p.split() if len(w) > 2)
        for b in parsed_recall.get("brands", []):
            recall_words.update(w.lower() for w in b.split() if len(w) > 2)

        matched = []
        for item in pantry_items:
            item_words = set(w.lower() for w in item.get("product_name", "").split() if len(w) > 2)
            if item.get("brand"):
                item_words.update(w.lower() for w in item["brand"].split() if len(w) > 2)
            if recall_words & item_words:
                matched.append(item)
        return matched


# ── Multilingual alert generation ─────────────────────────────────────────

def generate_alert(recall: Dict[str, Any],
                   matched_items: List[Dict[str, Any]],
                   language: str = "en") -> str:
    """Generate a personalized multilingual alert message for a user."""
    lang_names = {"en": "English", "es": "Spanish", "vi": "Vietnamese",
                  "zh": "Chinese", "ko": "Korean", "fr": "French"}
    lang_label = lang_names.get(language, language)

    item_names = ", ".join(m.get("product_name", "?") for m in matched_items)

    prompt = (
        f"Write a concise food recall alert in {lang_label}. "
        "Include:\n"
        "1. What is being recalled and why (one sentence)\n"
        "2. The user's affected pantry items\n"
        "3. Disposal instructions (throw away or return to store)\n"
        "4. A note that they may be eligible for a refund — contact the store\n\n"
        f"Recall info:\n"
        f"  Product: {recall.get('product_description', 'N/A')}\n"
        f"  Brand: {recall.get('brand_name', 'N/A')}\n"
        f"  Reason: {recall.get('reason_for_recall', 'N/A')}\n"
        f"  Company: {recall.get('company_name', 'N/A')}\n"
        f"  URL: {recall.get('url', '')}\n\n"
        f"User's affected items: {item_names}\n\n"
        "Keep the message under 300 words. Use a warning emoji at the start."
    )

    try:
        resp = _get_client().models.generate_content(model=_MODEL, contents=prompt)
        return resp.text.strip()
    except Exception:
        logger.exception("Gemini generate_alert failed; using fallback")
        return (
            f"⚠️ RECALL ALERT: {recall.get('product_description', 'Unknown product')} "
            f"has been recalled. Reason: {recall.get('reason_for_recall', 'N/A')}. "
            f"Your affected items: {item_names}. "
            "Please dispose of these items or return them to the store for a refund."
        )


# ── Receipt OCR ───────────────────────────────────────────────────────────

def ocr_receipt(image_bytes: bytes) -> List[Dict[str, str]]:
    """Use Gemini Vision to extract product names and lot codes from a receipt photo.

    Returns list of dicts: {"product_name": ..., "brand": ..., "lot_code": ...}
    """
    prompt = (
        "You are an OCR assistant that reads grocery receipts. "
        "Extract every food/grocery product from this receipt image. "
        "Return ONLY a valid JSON array of objects, each with:\n"
        '  "product_name": the item name,\n'
        '  "brand": brand if visible (null otherwise),\n'
        '  "lot_code": lot or batch code if visible (null otherwise)\n\n'
        "If you cannot read the receipt, return an empty array []."
    )

    try:
        from google.genai import types

        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        resp = _get_client().models.generate_content(model=_MODEL, contents=[prompt, image_part])
        text = resp.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        items = json.loads(text)
        # Ensure it's a list of dicts
        if isinstance(items, list):
            return [
                {
                    "product_name": it.get("product_name", "Unknown"),
                    "brand": it.get("brand"),
                    "lot_code": it.get("lot_code"),
                }
                for it in items
                if isinstance(it, dict)
            ]
        return []
    except Exception:
        logger.exception("Gemini OCR failed")
        return []
