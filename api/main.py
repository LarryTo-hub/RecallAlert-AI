"""FastAPI backend for RecallAlert-AI PWA.

Wraps existing src/ modules — no business logic is reimplemented here.
User identity: callers pass ?telegram_id=<int>; defaults to 0 (anonymous demo user).
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure src/ is importable when running from repo root or api/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from src import agent, fetcher
from src import store as recall_store
from src.models import (
    Alert,
    PantryItem,
    User,
    add_pantry_item,
    clear_pantry,
    create_alert,
    get_all_users,
    get_or_create_user,
    get_pantry,
    get_session,
    init_models_db,
    set_user_language,
    update_alert_feedback,
)

logger = logging.getLogger(__name__)

# ── In-memory recall cache ─────────────────────────────────────────────────
_recalls_cache: List[Dict[str, Any]] = []
_cache_updated_at: Optional[str] = None

DEMO_USER_ID = 0  # telegram_id used when no ID is supplied


# ── Scheduler setup ───────────────────────────────────────────────────────

async def _refresh_recalls() -> None:
    global _recalls_cache, _cache_updated_at
    logger.info("Refreshing recall cache...")
    try:
        records = await asyncio.to_thread(
            fetcher.fetch_all_recalls, 10, 10
        )
        _recalls_cache = records
        _cache_updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("Recall cache updated: %d records", len(records))
    except Exception:
        logger.exception("Failed to refresh recall cache")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init databases
    recall_store.init_db()
    init_models_db()

    # Ensure demo user exists
    try:
        get_or_create_user(DEMO_USER_ID)
    except Exception:
        pass

    # Initial recall fetch
    await _refresh_recalls()

    # Background scheduler
    interval = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_refresh_recalls, "interval", minutes=interval)
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(title="RecallAlert AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        os.getenv("FRONTEND_ORIGIN", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _resolve_user(telegram_id: int) -> User:
    return get_or_create_user(telegram_id)


def _get_alerts_for_user(user_id: int, status: Optional[str] = None) -> List[Alert]:
    with get_session() as sess:
        q = select(Alert).where(Alert.user_id == user_id)
        if status:
            q = q.where(Alert.status == status)
        return list(sess.exec(q.order_by(Alert.created_at.desc())).all())


def _get_pantry_item(item_id: int, user_id: int) -> Optional[PantryItem]:
    with get_session() as sess:
        item = sess.get(PantryItem, item_id)
        if item and item.user_id == user_id:
            return item
        return None


# ── Pydantic schemas ──────────────────────────────────────────────────────

class PantryItemCreate(BaseModel):
    product_name: str
    brand: Optional[str] = None
    lot_code: Optional[str] = None


class AlertFeedback(BaseModel):
    status: str  # "disposed" | "ignored"


class TelegramTestRequest(BaseModel):
    chat_id: int
    language: str = "en"


class NotificationSettings(BaseModel):
    telegram_id: int
    language: str = "en"
    severity_threshold: str = "all"  # all | medium+ | high
    sources: str = "both"  # fda | usda | both


# ── Recalls endpoints ─────────────────────────────────────────────────────

@app.get("/api/recalls")
async def list_recalls(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> Dict[str, Any]:
    results = _recalls_cache

    if source:
        src_lower = source.lower()
        results = [r for r in results if src_lower in (r.get("source") or "").lower()]

    if status:
        results = [r for r in results if (r.get("status") or "").upper() == status.upper()]

    if q:
        q_lower = q.lower()
        results = [
            r for r in results
            if q_lower in (r.get("product_description") or "").lower()
            or q_lower in (r.get("brand_name") or "").lower()
            or q_lower in (r.get("reason_for_recall") or "").lower()
            or q_lower in (r.get("company_name") or "").lower()
        ]

    total = len(results)
    page = results[offset: offset + limit]
    return {"total": total, "recalls": page, "updated_at": _cache_updated_at}


@app.post("/api/fetch")
async def trigger_fetch() -> Dict[str, Any]:
    await _refresh_recalls()
    return {"status": "ok", "count": len(_recalls_cache), "updated_at": _cache_updated_at}


@app.get("/api/recalls/{recall_idx}")
async def get_recall(recall_idx: int) -> Dict[str, Any]:
    if recall_idx < 0 or recall_idx >= len(_recalls_cache):
        raise HTTPException(status_code=404, detail="Recall not found")
    return _recalls_cache[recall_idx]


# ── Pantry endpoints ──────────────────────────────────────────────────────

@app.get("/api/pantry")
async def list_pantry(telegram_id: int = Query(DEMO_USER_ID)) -> Dict[str, Any]:
    user = _resolve_user(telegram_id)
    items = get_pantry(user.id)
    return {"items": [i.model_dump() for i in items]}


@app.post("/api/pantry", status_code=201)
async def add_to_pantry(
    body: PantryItemCreate,
    telegram_id: int = Query(DEMO_USER_ID),
) -> Dict[str, Any]:
    user = _resolve_user(telegram_id)
    item = add_pantry_item(
        user_id=user.id,
        product_name=body.product_name,
        brand=body.brand,
        lot_code=body.lot_code,
        source="manual",
    )
    return item.model_dump()


@app.delete("/api/pantry")
async def clear_all_pantry(telegram_id: int = Query(DEMO_USER_ID)) -> Dict[str, Any]:
    user = _resolve_user(telegram_id)
    count = clear_pantry(user.id)
    return {"deleted": count}


@app.delete("/api/pantry/{item_id}")
async def delete_pantry_item(
    item_id: int,
    telegram_id: int = Query(DEMO_USER_ID),
) -> Dict[str, Any]:
    user = _resolve_user(telegram_id)
    item = _get_pantry_item(item_id, user.id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    with get_session() as sess:
        db_item = sess.get(PantryItem, item_id)
        if db_item:
            sess.delete(db_item)
            sess.commit()
    return {"deleted": item_id}


# ── OCR endpoint ──────────────────────────────────────────────────────────

@app.post("/api/ocr")
async def ocr_receipt(file: UploadFile = File(...)) -> Dict[str, Any]:
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    items = await asyncio.to_thread(agent.ocr_receipt, data)
    return {"items": items}


# ── Match endpoint ────────────────────────────────────────────────────────

@app.post("/api/match")
async def match_pantry(telegram_id: int = Query(DEMO_USER_ID)) -> Dict[str, Any]:
    user = _resolve_user(telegram_id)
    pantry = get_pantry(user.id)
    if not pantry:
        return {"matches": []}

    pantry_dicts = [
        {"product_name": i.product_name, "brand": i.brand, "lot_code": i.lot_code}
        for i in pantry
    ]

    matches = []
    for recall in _recalls_cache:
        parsed = await asyncio.to_thread(agent.parse_recall, recall)
        matched = await asyncio.to_thread(agent.match_pantry, parsed, pantry_dicts)
        if matched:
            matches.append({
                "recall": recall,
                "parsed": parsed,
                "matched_items": matched,
            })

    return {"matches": matches}


# ── Alerts endpoints ──────────────────────────────────────────────────────

@app.get("/api/alerts")
async def list_alerts(
    telegram_id: int = Query(DEMO_USER_ID),
    status: Optional[str] = None,
) -> Dict[str, Any]:
    user = _resolve_user(telegram_id)
    alerts = _get_alerts_for_user(user.id, status)
    return {"alerts": [a.model_dump() for a in alerts]}


@app.patch("/api/alerts/{alert_id}/feedback")
async def alert_feedback(
    alert_id: int,
    body: AlertFeedback,
    telegram_id: int = Query(DEMO_USER_ID),
) -> Dict[str, Any]:
    if body.status not in ("disposed", "ignored"):
        raise HTTPException(status_code=400, detail="status must be 'disposed' or 'ignored'")

    user = _resolve_user(telegram_id)
    alert = update_alert_feedback(alert_id, body.status)
    if not alert or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert.model_dump()


# ── Telegram endpoints ────────────────────────────────────────────────────

@app.post("/api/telegram/test")
async def test_telegram(body: TelegramTestRequest) -> Dict[str, Any]:
    try:
        import telegram
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise HTTPException(status_code=503, detail="TELEGRAM_BOT_TOKEN not configured")

        bot = telegram.Bot(token=token)
        msg = (
            "✅ RecallAlert AI connected!\n\n"
            "You'll receive personalized food recall alerts here whenever "
            "items in your pantry are affected.\n\n"
            "Use the web app to manage your pantry and notification preferences."
        )
        await bot.send_message(chat_id=body.chat_id, text=msg)

        # Ensure user record exists with this telegram_id
        user = get_or_create_user(body.chat_id, body.language)
        if user.language != body.language:
            set_user_language(body.chat_id, body.language)

        return {"status": "sent"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Notification settings endpoint ────────────────────────────────────────

@app.post("/api/notifications/settings")
async def save_notification_settings(body: NotificationSettings) -> Dict[str, Any]:
    user = get_or_create_user(body.telegram_id)
    set_user_language(body.telegram_id, body.language)
    return {
        "status": "saved",
        "telegram_id": body.telegram_id,
        "language": body.language,
        "severity_threshold": body.severity_threshold,
        "sources": body.sources,
    }


# ── Stats endpoint ────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats(telegram_id: int = Query(DEMO_USER_ID)) -> Dict[str, Any]:
    user = _resolve_user(telegram_id)
    alerts = _get_alerts_for_user(user.id)
    pantry = get_pantry(user.id)

    active = sum(1 for r in _recalls_cache if (r.get("status") or "").upper() == "ACTIVE")

    return {
        "total_recalls": len(_recalls_cache),
        "active_recalls": active,
        "pantry_items": len(pantry),
        "total_alerts": len(alerts),
        "disposed": sum(1 for a in alerts if a.status == "disposed"),
        "ignored": sum(1 for a in alerts if a.status == "ignored"),
        "cache_updated_at": _cache_updated_at,
    }


# ── Export endpoint ───────────────────────────────────────────────────────

@app.get("/api/pantry/export")
async def export_pantry(telegram_id: int = Query(DEMO_USER_ID)) -> StreamingResponse:
    user = _resolve_user(telegram_id)
    items = get_pantry(user.id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "product_name", "brand", "lot_code", "source", "added_at"])
    for item in items:
        writer.writerow([
            item.id, item.product_name, item.brand or "",
            item.lot_code or "", item.source, item.added_at,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pantry.csv"},
    )


# ── Chat endpoint ─────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    telegram_id: int = DEMO_USER_ID


@app.post("/api/chat")
async def chat_with_bot(body: ChatMessage) -> Dict[str, Any]:
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Build recall context from in-memory cache (top 5 active recalls)
    active_recalls = [
        r for r in _recalls_cache if (r.get("status") or "").upper() == "ACTIVE"
    ][:5]
    recall_context = ""
    if active_recalls:
        recall_context = "Current active recalls:\n"
        for r in active_recalls:
            recall_context += (
                f"- {r.get('product_description', 'Unknown')} "
                f"[{r.get('source', '')}]: {r.get('reason_for_recall', '')}\n"
            )

    # Build pantry context for the requesting user
    pantry_context = ""
    try:
        user = _resolve_user(body.telegram_id)
        pantry = get_pantry(user.id)
        if pantry:
            pantry_context = "\nUser's pantry items: " + ", ".join(
                i.product_name for i in pantry
            )
    except Exception:
        pass

    prompt = (
        "You are RecallAlert AI, a concise food safety assistant embedded in a web app. "
        "Answer questions about food recalls, disposal instructions, and pantry safety. "
        "If asked about specific products, reference the recall data provided. "
        "Keep answers under 120 words and use plain language.\n\n"
        f"{recall_context}{pantry_context}\n\n"
        f"User question: {body.message}"
    )

    try:
        client = agent._get_client()
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=prompt,
        )
        return {"reply": resp.text.strip()}
    except RuntimeError as e:
        # GOOGLE_API_KEY not set
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Chat endpoint error")
        raise HTTPException(status_code=503, detail="AI unavailable")
