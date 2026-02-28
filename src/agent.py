# Agent module — LLM-based recall summarization using Google Gemini.

from __future__ import annotations

import json
import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
You are a food-safety analyst. Given raw text from a USDA or FDA recall notice,
extract the key information and return ONLY a JSON object with these exact fields:

{
  "summary": "<2-3 sentence plain-English summary of the recall>",
  "risk_level": "<Low | Medium | High>",
  "action_steps": ["<step 1>", "<step 2>", ...],
  "who_is_affected": "<description of the population at risk>",
  "key_identifiers": ["<brand name>", "<lot number>", "<UPC>", ...]
}

Rules:
- risk_level must be exactly one of: Low, Medium, High
- action_steps must be a JSON array of short imperative sentences
- key_identifiers must be a JSON array (may be empty if none found)
- Return ONLY the JSON object — no markdown fences, no extra text
"""

def summarize_recall(text: str) -> dict:
    """Call Gemini to classify and summarize a recall notice.

    Parameters:
    text : str
        Raw recall notice text (product description, reason, etc.)

    Returns:
    dict
        Structured recall info. On error, returns a dict with an "error" key.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your .env file. "
            "Get a free key at https://aistudio.google.com/app/apikey"
        )

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is not installed. Run: pip install google-genai"
        ) from exc

    client = genai.Client(api_key=api_key)

    prompt = f"Recall notice:\n\n{text.strip()}"
    logger.info("Calling Gemini model=%s ...", model_name)

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
        ),
    )
    raw = response.text.strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON output: %s", raw)
        raise ValueError(f"Could not parse Gemini response as JSON: {exc}\n\nRaw output:\n{raw}") from exc

    if "risk_level" in result:
        result["risk_level"] = result["risk_level"].capitalize()

    logger.info("Gemini summarized recall: risk_level=%s", result.get("risk_level"))
    return result
