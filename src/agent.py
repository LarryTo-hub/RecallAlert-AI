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
        '  "products": list of SHORT commercial product name strings — extract ONLY the product name (e.g., '
        '"Junebar Peanut Chocolate Chip All Natural Snack Bar"), NOT the ingredient list, UPC codes, '
        'allergen statements, or supplementary text. Stop at the first occurrence of \'INGREDIENTS:\', '
        '\'UPC\', \'Net Wt\', \'ALLERGEN\', or a semicolon followed by ingredient content.\n'
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

# Tokens to ignore during overlap comparisons
_MATCH_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "are", "has",
    "have", "due", "may", "can", "its", "not", "all", "any", "inc",
    "llc", "ltd", "corp", "co", "company", "foods", "products", "brand",
    "item", "items", "units", "pack", "packs", "size", "oz", "lb", "lbs",
}


def _tokenize(text: str) -> set:
    """Lowercase-split a string, strip punctuation, remove stopwords & short tokens."""
    return {
        w.lower().strip(".,;:'\"()[]")
        for w in (text or "").split()
        if len(w) > 2 and w.lower().strip(".,;:'\"()[]") not in _MATCH_STOPWORDS
    }


_INGREDIENT_MARKERS = (
    "INGREDIENTS:", "Ingredients:", "ingredients:",
    "; INGREDIENTS", "; Ingredients",
    "CONTAINS LESS THAN", "Contains less than",
    "; UPC", " UPC:", "UPC ", "UPC-",
    " Net Wt", " NET WT", " Net wt", " NET WEIGHT", " Net Weight",
    "SHELF LIFE", "Shelf Life",
    "Manufacturer:", "MANUFACTURER",
    "KEEP REFRIGERATED", "Keep Refrigerated", "KEEP FROZEN", "Keep Frozen",
    "ALLERGEN WARNING", "Allergen Warning", "ALLERGY WARNING",
    # Marketing description separators — product name ends before these
    " - A Chinese", " - A Japanese", " - A ",
    ". Net Wt", ". Net wt",
)


def _extract_product_name(text: str) -> str:
    """Strip ingredient lists and supplementary info, returning only the primary product name."""
    result = text
    for marker in _INGREDIENT_MARKERS:
        idx = result.find(marker)
        if 0 < idx < len(result):
            result = result[:idx]
    return result.strip(" ;,")


def _candidate_filter(
    parsed_recall: Dict[str, Any],
    pantry_items: List[Dict[str, Any]],
) -> List[int]:
    """Deterministic pre-filter: return 0-based indices of pantry items that share
    at least one meaningful token with the recall products/brands, have a matching
    brand name, or share a lot code.  Eliminates obvious misses before calling Gemini.
    """
    # Use only the primary product name portion — strip ingredient lists before tokenizing
    recall_tokens: set = set()
    for p in parsed_recall.get("products", []):
        recall_tokens |= _tokenize(_extract_product_name(p))
    for b in parsed_recall.get("brands", []):
        recall_tokens |= _tokenize(b)

    recall_brands = {b.lower().strip() for b in parsed_recall.get("brands", []) if b}
    recall_lots = {lc.lower().strip() for lc in parsed_recall.get("lot_codes", []) if lc}

    candidates = []
    for idx, item in enumerate(pantry_items):
        item_name = item.get("product_name", "")
        item_tokens = _tokenize(item_name)
        if item.get("brand"):
            item_tokens |= _tokenize(item["brand"])
        item_brand = (item.get("brand") or "").lower().strip()
        item_lot = (item.get("lot_code") or "").lower().strip()

        # For single-token pantry items (e.g. GARLIC, POTATOES) require a brand
        # match or lot code match — a lone generic word overlapping a product name
        # is not enough to be a candidate.
        item_is_single_word = len(item_tokens) == 1
        token_overlap = recall_tokens & item_tokens
        brand_match = item_brand and item_brand in recall_brands
        lot_match = item_lot and item_lot in recall_lots

        if lot_match or brand_match:
            candidates.append(idx)
        elif token_overlap and not item_is_single_word:
            candidates.append(idx)
        elif token_overlap and item_is_single_word and brand_match:
            candidates.append(idx)

    return candidates


def match_pantry(
    parsed_recall: Dict[str, Any],
    pantry_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Two-stage pantry matching: deterministic filter → strict Gemini verifier.

    Stage 1: Token-overlap candidate filter eliminates obvious misses with no LLM cost.
    Stage 2: Gemini returns structured evidence + confidence for each candidate.
             Only items with confidence >= 0.6 AND at least one concrete evidence
             field (matched_brand, matched_lot_code, matched_allergen, or
             matched_product_tokens) are kept.
    """
    if not pantry_items:
        return []

    # Stage 1 — deterministic pre-filter
    candidate_indices = _candidate_filter(parsed_recall, pantry_items)
    if not candidate_indices:
        return []

    candidates = [pantry_items[i] for i in candidate_indices]

    prompt = (
        "You are a strict food-safety verification engine. Your job is to "
        "confirm or deny whether each candidate pantry item is genuinely "
        "affected by the given recall.\n\n"
        "CRITICAL RULE — the pantry item must BE the recalled product:\n"
        "A pantry item matches ONLY if the user's pantry item IS the actual recalled "
        "product (or a specific branded variant of it). Reject all other cases.\n\n"
        "REJECT these common false positive patterns:\n"
        "  - A raw/generic ingredient (GARLIC, POTATOES, EGGS, MILK, SESAME SEED, "
        "SOY SAUCE, ONION, SALT) does NOT match a recall of a product that merely "
        "CONTAINS or is FLAVORED WITH that ingredient.\n"
        "    e.g. GARLIC ≠ 'Garlic Dill Pickles' (pickles contain garlic)\n"
        "    e.g. GARLIC ≠ 'Garlic Flavor Roasted Peanuts' (peanuts flavored with garlic)\n"
        "    e.g. GARLIC ≠ 'Garlic & Herb Cream Cheese' (cream cheese flavored with garlic)\n"
        "    e.g. GARLIC ≠ 'Garlic Salt' (seasoning, not raw garlic)\n"
        "    e.g. POTATOES ≠ 'Tater Tots shaped potatoes' (processed frozen product)\n"
        "    e.g. POTATOES ≠ 'Breakfast Burrito with Potatoes' (burrito that contains potatoes)\n"
        "    e.g. SOY SAUCE ≠ 'Fried Rice with Sweet Soy Sauce' (rice dish containing soy sauce)\n"
        "    e.g. SESAME SEED ≠ 'Hamburger Bun with undeclared sesame' (the bun is recalled, not sesame seeds)\n"
        "  - A generic pantry ingredient only matches a recall if the recalled product "
        "IS primarily that ingredient (e.g., branded fresh garlic, a garlic supplement, "
        "a specific brand of frozen potatoes the user owns).\n\n"
        "ACCEPT only when:\n"
        "- The pantry item and the recalled product are the same type of product AND "
        "share the same brand, OR\n"
        "- The lot code matches exactly, OR\n"
        "- The pantry item is a specific branded product clearly described by the recall\n\n"
        "- Assign a confidence score 0.0–1.0 based on strength of evidence.\n\n"
        "Return ONLY a valid JSON array. Each element must be:\n"
        '  { "index": <int, 0-based position in the candidates list>,\n'
        '    "confidence": <float 0.0-1.0>,\n'
        '    "matched_brand": <exact matching brand string, or null>,\n'
        '    "matched_product_tokens": <list of specific shared product tokens>,\n'
        '    "matched_allergen": <shared allergen string, or null>,\n'
        '    "matched_lot_code": <matching lot code string, or null>,\n'
        '    "reason": <one-sentence justification> }\n\n'
        "Include ONLY entries where confidence >= 0.6 AND at least one of "
        "matched_brand, matched_lot_code, matched_allergen, or "
        "matched_product_tokens (non-empty list) is non-null.\n"
        "If no candidates qualify, return an empty array [].\n\n"
        f"Recall:\n{json.dumps(parsed_recall, default=str, indent=2)}\n\n"
        f"Candidate pantry items:\n{json.dumps(candidates, default=str, indent=2)}"
    )

    try:
        resp = _get_client().models.generate_content(model=_MODEL, contents=prompt)
        text = resp.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        results = json.loads(text)
        matched = []
        for r in results:
            if not isinstance(r, dict):
                continue
            conf = float(r.get("confidence", 0))
            idx = r.get("index")
            if not isinstance(idx, int) or not (0 <= idx < len(candidates)):
                continue
            has_evidence = (
                r.get("matched_brand")
                or r.get("matched_lot_code")
                or r.get("matched_allergen")
                or (r.get("matched_product_tokens") or [])
            )
            if conf >= 0.6 and has_evidence:
                matched.append(candidates[idx])
        return matched
    except Exception:
        logger.exception("Gemini match_pantry failed; falling back to deterministic filter")
        # Deterministic fallback: require >=2 token overlap to avoid single-word false positives
        recall_tokens: set = set()
        for p in parsed_recall.get("products", []):
            recall_tokens |= _tokenize(p)
        for b in parsed_recall.get("brands", []):
            recall_tokens |= _tokenize(b)
        matched = []
        for item in candidates:
            item_tokens = _tokenize(item.get("product_name", ""))
            if item.get("brand"):
                item_tokens |= _tokenize(item["brand"])
            if len(recall_tokens & item_tokens) >= 2:
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
