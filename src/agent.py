"""Gemini-powered agent for recall parsing, pantry matching, OCR, and alerts."""

from __future__ import annotations

import json
import logging
import os
import re as _re
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
    # Pre-strip ingredient lists from product_description so Gemini
    # cannot accidentally extract ingredient words as product names.
    raw_desc = recall.get("product_description") or ""
    clean_desc = _extract_product_name(raw_desc)
    clean_recall = {**recall, "product_description": clean_desc}

    prompt = (
        "You are a food-safety analyst. Given the following recall record, "
        "extract structured information. Return ONLY a valid JSON object with "
        "these keys:\n"
        '  "products": list of SHORT commercial product name strings — the brand '
        'and product name ONLY (e.g., "Junebar Peanut Chocolate Chip All Natural '
        'Snack Bar"). Do NOT include ingredients, allergen warnings, UPC codes, '
        'net weight, or any supplementary text as separate product entries.\n'
        '  "brands": list of brand name strings,\n'
        '  "severity": "high" | "medium" | "low",\n'
        '  "lot_codes": list of lot/batch code strings (empty list if none),\n'
        '  "reason_summary": one-sentence plain-English summary of the recall reason\n\n'
        f"Recall record:\n{json.dumps(clean_recall, default=str, indent=2)}"
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
            # Use the CLEAN description (no ingredient list) in the fallback
            "products": [clean_desc] if clean_desc else [],
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


def _stem(word: str) -> str:
    """Very light stem: strip trailing 's' so 'meals' matches 'meal'."""
    return word.rstrip("s") if len(word) > 3 else word


def _tokenize(text: str) -> set:
    """Lowercase-split a string, strip punctuation, remove stopwords & short tokens.

    Also adds stemmed variants (trailing 's' stripped) so 'meals' matches 'meal'.
    """
    result = set()
    for w in (text or "").split():
        tok = w.lower().strip(".,;:'\"()[]")
        if not tok or len(tok) <= 2 or tok in _MATCH_STOPWORDS:
            continue
        result.add(tok)
        stemmed = _stem(tok)
        if stemmed != tok and len(stemmed) > 2:
            result.add(stemmed)
    return result


def _normalize_name(text: str) -> str:
    """Return a fully-collapsed, stemmed, stopword-free comparison string.

    e.g. 'Ready Meals' → 'readymeal'
         'readymeal'   → 'readymeal'
         'ReadyMeals'  → 'readymeal'
    Used to detect near-identical product names regardless of spacing/casing.
    """
    # Split CamelCase so 'ReadyMeals' → 'Ready Meals' before tokenizing
    spaced = _re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    tokens = sorted(_tokenize(spaced))
    return "".join(_stem(t) for t in tokens)


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
    recall_norms: set = set()  # collapsed normalized forms for fuzzy matching
    for p in parsed_recall.get("products", []):
        clean = _extract_product_name(p)
        recall_tokens |= _tokenize(clean)
        recall_norms.add(_normalize_name(clean))
    for b in parsed_recall.get("brands", []):
        recall_tokens |= _tokenize(b)
        recall_norms.add(_normalize_name(b))

    recall_brands = {b.lower().strip() for b in parsed_recall.get("brands", []) if b}
    recall_lots = {lc.lower().strip() for lc in parsed_recall.get("lot_codes", []) if lc}

    candidates = []
    for idx, item in enumerate(pantry_items):
        item_name = item.get("product_name", "")
        item_tokens = _tokenize(item_name)
        item_norm = _normalize_name(item_name)
        if item.get("brand"):
            item_tokens |= _tokenize(item["brand"])
        item_brand = (item.get("brand") or "").lower().strip()
        item_lot = (item.get("lot_code") or "").lower().strip()

        brand_match = item_brand and item_brand in recall_brands
        lot_match = item_lot and item_lot in recall_lots

        if lot_match or brand_match:
            candidates.append(idx)
            continue

        # Fuzzy collapsed-name check: "Ready Meals", "Ready Meal", "readymeal",
        # "ReadyMeals" all collapse to a spaceless lowercase string for comparison.
        item_spaceless = _re.sub(r"[^a-z0-9]", "", item_name.lower())
        if item_spaceless and len(item_spaceless) >= 4:
            for rn in recall_norms:
                rn_spaceless = _re.sub(r"[^a-z0-9]", "", rn)
                if item_spaceless in rn_spaceless or rn_spaceless.startswith(item_spaceless) or rn_spaceless.endswith(item_spaceless):
                    candidates.append(idx)
                    break
            else:
                pass  # fall through to token overlap check below
            if idx in candidates:
                continue

        token_overlap = recall_tokens & item_tokens
        if not token_overlap:
            continue

        # Single-token pantry items require overlap with a recall token.
        item_is_single_word = len(item_tokens) == 1
        item_coverage = len(token_overlap) / len(item_tokens) if item_tokens else 0.0

        if item_is_single_word:
            if item_tokens & recall_tokens:
                candidates.append(idx)
        elif item_coverage >= 0.5:
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
        "  - A raw/generic ingredient does NOT match a recall of a manufactured product "
        "that merely CONTAINS, is FLAVORED WITH, or is NAMED AFTER that ingredient.\n"
        "    e.g. EGGS ≠ a product that contains eggs as an ingredient\n"
        "    e.g. MILK ≠ a dairy product made with milk\n"
        "    e.g. FLOUR ≠ a baked good that lists flour as an ingredient\n"
        "  - A generic ingredient only matches if the recalled product IS that ingredient "
        "as a standalone item — for example a specific branded package of that ingredient, "
        "or a supplement form of it.\n\n"
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
        recall_brands: set = {b.lower().strip() for b in parsed_recall.get("brands", []) if b}
        for p in parsed_recall.get("products", []):
            recall_tokens |= _tokenize(p)
        for b in parsed_recall.get("brands", []):
            recall_tokens |= _tokenize(b)
        matched = []
        for item in candidates:
            item_tokens = _tokenize(item.get("product_name", ""))
            if item.get("brand"):
                item_tokens |= _tokenize(item["brand"])
            item_brand = (item.get("brand") or "").lower().strip()
            # Single-word pantry entries pass if they match a recall brand.
            # Multi-word entries require >=2 token overlap to avoid incidental matches.
            if len(item_tokens) == 1:
                if item_tokens & recall_brands:
                    matched.append(item)
            elif len(recall_tokens & item_tokens) >= 2:
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


# ── Chatbot ───────────────────────────────────────────────────────────────

def chat_with_agent(
    message: str,
    pantry_items: List[Dict[str, Any]],
    recent_recalls: List[Dict[str, Any]],
) -> str:
    """Answer a user's food-safety question using Gemini with recall + pantry context.

    Args:
        message: The user's chat message.
        pantry_items: List of the user's current pantry items.
        recent_recalls: A sample of recent recalls for context.

    Returns:
        A plain-text reply string.
    """
    pantry_summary = (
        "\n".join(
            f"- {item.get('product_name', 'Unknown')}"
            + (f" (brand: {item['brand']})" if item.get("brand") else "")
            for item in pantry_items
        )
        if pantry_items
        else "No items in pantry."
    )

    recall_summary = (
        "\n".join(
            f"- {r.get('product_description', 'Unknown')} | Reason: {r.get('reason_for_recall', 'N/A')} | Status: {r.get('status', 'N/A')}"
            for r in recent_recalls[:15]
        )
        if recent_recalls
        else "No recent recalls available."
    )

    prompt = (
        "You are RecallAlert AI, a helpful food safety assistant. "
        "You help users understand food recalls and whether their pantry items are affected.\n\n"
        "Be concise and friendly. Use plain text (no markdown). "
        "If the user asks about their pantry, use the pantry context below. "
        "If they ask to list recalls, summarize the recent recalls context below.\n\n"
        f"User's pantry:\n{pantry_summary}\n\n"
        f"Recent recalls:\n{recall_summary}\n\n"
        f"User message: {message}"
    )

    try:
        resp = _get_client().models.generate_content(model=_MODEL, contents=prompt)
        return resp.text.strip()
    except Exception:
        logger.exception("Gemini chat failed")
        return "I'm having trouble connecting to my AI backend right now. Please try again in a moment."
