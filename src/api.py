"""REST API for RecallAlert-AI (website backend).

Provides:
- User authentication (JWT)
- Recall querying & filtering
- Pantry management
- Alert feedback tracking
- WebSocket live updates
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
import jwt

from pathlib import Path
from dotenv import load_dotenv

from sqlmodel import select, Session
from src.models import User, PantryItem, Alert

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# ──────────────────────────────────────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────────────────────────────────────


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int


class UserProfile(BaseModel):
    id: int
    email: str
    name: str
    language: str
    created_at: str


class PantryItemRequest(BaseModel):
    product_name: str
    brand: Optional[str] = None
    lot_code: Optional[str] = None


class PantryItemResponse(BaseModel):
    id: int
    product_name: str
    brand: Optional[str]
    lot_code: Optional[str]
    added_at: str


class PantryListResponse(BaseModel):
    items: List[PantryItemResponse]


class RecallResponse(BaseModel):
    recall_number: Optional[str] = None
    product_description: Optional[str] = None
    reason_for_recall: Optional[str] = None
    recall_initiation_date: Optional[str] = None
    severity: Optional[str] = None
    brands: List[str] = []
    lots: List[str] = []


class AlertFeedback(BaseModel):
    status: str = Field(..., pattern="^(disposed|ignored)$")


class StatsResponse(BaseModel):
    total_recalls: int
    active_recalls: int
    pantry_items: int
    total_alerts: int
    disposed: int
    ignored: int
    cache_updated_at: Optional[str]


class EmailSettings(BaseModel):
    email: str
    notify_new_only: bool


class EmailSettingsUpdate(BaseModel):
    email: str
    notify_new_only: bool


class AlertsResponse(BaseModel):
    alerts: List[dict]


# ──────────────────────────────────────────────────────────────────────────────
# Security
# ──────────────────────────────────────────────────────────────────────────────

security = HTTPBearer()


def create_access_token(user_id: int, email: str) -> str:
    """Create JWT access token."""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI App Setup
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="RecallAlert-AI API",
    description="Food recall notifications API",
    version="1.0.0",
)

# Enable CORS for React frontend
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Authentication Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@app.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """Register a new user."""
    from src.models import get_or_create_user

    try:
        # TODO: Hash password and store in database
        # For now, using telegram_id as placeholder
        user = get_or_create_user(
            telegram_id=hash(user_data.email) % (10**8),  # Generate ID from email
            language="en",
        )

        token = create_access_token(user.id, user_data.email)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user.id,
        }
    except Exception as e:
        logger.exception("Registration error: %s", e)
        raise HTTPException(status_code=400, detail="Registration failed")


@app.post("/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Login user."""
    # TODO: Verify password against database
    # For now, just return token
    try:
        user_id = hash(user_data.email) % (10**8)
        token = create_access_token(user_id, user_data.email)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user_id,
        }
    except Exception as e:
        logger.exception("Login error: %s", e)
        raise HTTPException(status_code=401, detail="Login failed")


# ──────────────────────────────────────────────────────────────────────────────
# User Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@app.get("/user/profile", response_model=UserProfile)
async def get_profile(token_payload: dict = Depends(verify_token)):
    """Get current user profile."""
    from src.models import get_or_create_user

    user_id = token_payload["user_id"]
    # TODO: Fetch from database instead of creating
    user = get_or_create_user(user_id)
    return {
        "id": user.id,
        "email": token_payload["email"],
        "name": "User",
        "language": user.language,
        "created_at": user.created_at,
    }


@app.put("/user/language")
async def set_language(language: str, token_payload: dict = Depends(verify_token)):
    """Update user language preference."""
    from src.models import set_user_language

    user_id = token_payload["user_id"]
    set_user_language(user_id, language)
    return {"status": "ok", "language": language}


# ──────────────────────────────────────────────────────────────────────────────
# Pantry Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@app.get("/pantry", response_model=PantryListResponse)
async def get_pantry_endpoint(user_id: str = Query("")):
    """Get user's pantry items."""
    from src.models import get_or_create_user_by_key, get_pantry

    user = get_or_create_user_by_key(user_id)
    items = get_pantry(user.id)
    return {
        "items": [
            {
                "id": item.id,
                "product_name": item.product_name,
                "brand": item.brand,
                "lot_code": item.lot_code,
                "added_at": item.added_at,
            }
            for item in items
        ]
    }


@app.post("/pantry/items", response_model=PantryItemResponse)
async def add_pantry_item_endpoint(item: PantryItemRequest, user_id: str = Query("")):
    """Add item to user's pantry."""
    from src.models import get_or_create_user_by_key, add_pantry_item

    user = get_or_create_user_by_key(user_id)
    added = add_pantry_item(user.id, item.product_name, item.brand, item.lot_code)
    return {
        "id": added.id,
        "product_name": added.product_name,
        "brand": added.brand,
        "lot_code": added.lot_code,
        "added_at": added.added_at,
    }


@app.delete("/pantry/items/{item_id}")
async def delete_pantry_item_endpoint(item_id: int, user_id: str = Query("")):
    """Delete pantry item."""
    from src.models import get_or_create_user_by_key, delete_pantry_item

    user = get_or_create_user_by_key(user_id)
    delete_pantry_item(user.id, item_id)
    return {"status": "ok"}


@app.delete("/pantry")
async def clear_pantry_endpoint(user_id: str = Query("")):
    """Clear user's entire pantry."""
    from src.models import get_or_create_user_by_key, clear_pantry

    user = get_or_create_user_by_key(user_id)
    deleted = clear_pantry(user.id)
    return {"deleted": deleted}


# ──────────────────────────────────────────────────────────────────────────────
# Recall Endpoints
# ──────────────────────────────────────────────────────────────────────────────


class RecallsResponse(BaseModel):
    total: int
    recalls: List[RecallResponse]
    updated_at: Optional[str] = None


@app.get("/recalls", response_model=RecallsResponse)
async def get_recalls(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
):
    """Get latest recalls (paginated, with optional source/status/q filters)."""
    from src.store import get_all_recalls, get_recall_count, get_cache_updated_at

    recalls = get_all_recalls(skip=offset, limit=limit, source=source, status=status, q=q)
    total = get_recall_count(source=source, status=status, q=q)

    def field(x, key):
        if isinstance(x, dict):
            return x.get(key)
        return getattr(x, key, None)

    return {
        "total": total,
        "updated_at": get_cache_updated_at(),
        "recalls": [
            {
                "recall_number": field(r, "recall_number"),
                "product_description": field(r, "product_description"),
                "reason_for_recall": field(r, "reason_for_recall"),
                "recall_initiation_date": field(r, "recall_initiation_date"),
                "severity": field(r, "severity"),
                "brands": field(r, "brands") or [],
                "lots": field(r, "lots") or [],
            }
            for r in recalls
        ],
    }


@app.post("/match")
async def match_pantry(user_id: str = Query("")):
    """Return pantry match candidates.

    Current lightweight implementation returns an empty list while preserving
    the frontend contract.
    """
    from src.models import get_or_create_user_by_key

    get_or_create_user_by_key(user_id)
    return {"matches": []}


# ──────────────────────────────────────────────────────────────────────────────
# Alert Feedback Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@app.get("/alerts")
async def get_alerts_endpoint(user_id: str = Query(""), status: Optional[str] = None):
    """Get alerts for the current user."""
    from src.models import get_or_create_user_by_key, get_alerts

    user = get_or_create_user_by_key(user_id)
    alerts = get_alerts(user.id)
    if status:
        alerts = [a for a in alerts if a.status == status]

    return {
        "alerts": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "recall_id": a.recall_id,
                "recall_number": a.recall_number,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at,
                "responded_at": a.responded_at,
            }
            for a in alerts
        ]
    }


@app.patch("/alerts/{alert_id}/feedback")
async def submit_feedback(alert_id: int, feedback: AlertFeedback, user_id: str = Query("")):
    """Submit feedback for an alert (disposed/ignored)."""
    from src.models import get_or_create_user_by_key, update_alert_feedback

    user = get_or_create_user_by_key(user_id)
    updated = update_alert_feedback(user.id, alert_id, feedback.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {
        "id": updated.id,
        "user_id": updated.user_id,
        "recall_id": updated.recall_id,
        "recall_number": updated.recall_number,
        "message": updated.message,
        "status": updated.status,
        "created_at": updated.created_at,
        "responded_at": updated.responded_at,
    }


# ──────────────────────────────────────────────────────────────────────────────
# WebSocket Endpoint (Live Updates)
# ──────────────────────────────────────────────────────────────────────────────

# Track active websocket connections per user
active_connections: dict[int, WebSocket] = {}


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for live recall notifications.

    Usage:
      ws = new WebSocket('ws://localhost:8000/ws/123');
      ws.onmessage = (event) => {
        const alert = JSON.parse(event.data);
        // Handle new alert
      };
    """
    await websocket.accept()
    active_connections[user_id] = websocket

    try:
        while True:
            # Keep connection alive, waiting for messages from polling loop
            data = await websocket.receive_text()
            # Could handle client commands here
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
    finally:
        del active_connections[user_id]


# ──────────────────────────────────────────────────────────────────────────────
# Utility: Broadcast to user via WebSocket
# ──────────────────────────────────────────────────────────────────────────────


async def broadcast_alert(user_id: int, alert_message: dict):
    """Send alert to user via WebSocket if connected."""
    import json

    if user_id in active_connections:
        try:
            await active_connections[user_id].send_text(json.dumps(alert_message))
        except Exception as e:
            logger.exception("Failed to broadcast to user %d: %s", user_id, e)


# ──────────────────────────────────────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────────────────────────────────────


@app.post("/fetch")
async def trigger_fetch():
    """Manually trigger a recall fetch and alert cycle."""
    try:
        from src.polling import poll_and_alert
        import asyncio
        asyncio.create_task(poll_and_alert())
        return {"status": "triggered"}
    except Exception as e:
        logger.exception("Fetch trigger error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "ok"}


@app.get("/api")
async def root():
    """Welcome endpoint."""
    return {
        "name": "RecallAlert-AI API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Chat (AI Assistant)
# ──────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str = ""


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with RecallAlert AI for recall questions and disposal instructions."""
    try:
        from src import agent
        
        from src.models import get_or_create_user_by_key

        user = get_or_create_user_by_key(request.user_id)
        message = request.message.strip()
        
        # Get user's pantry if registered
        pantry = []
        try:
            from src.models import get_pantry
            pantry = get_pantry(user.id)
        except Exception:
            pass
        
        # Build context
        pantry_str = ""
        if pantry:
            items = [f"{getattr(item, 'product_name', '?')}" + 
                     (f" ({getattr(item, 'brand', '')})" if getattr(item, 'brand', None) else "") 
                     for item in pantry]
            pantry_str = f"\nUser's pantry items: {', '.join(items)}"
        
        # Generate response
        prompt = (
            "You are RecallAlert AI, a friendly food safety assistant. "
            "Answer user questions about food recalls, disposal instructions, "
            "food safety, and whether their pantry items might be affected.\n"
            "Be concise (1-3 sentences), practical, and reassuring.\n"
            f"{pantry_str}\n\n"
            f"User: {message}"
        )
        
        resp = agent._get_client().models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        reply = resp.text.strip()
        
        return ChatResponse(reply=reply)
    except Exception as e:
        logger.exception("Chat error: %s", e)
        return ChatResponse(reply="Sorry, I'm having trouble responding right now. Please try again later.")


@app.get("/stats", response_model=StatsResponse)
async def get_stats(user_id: str = Query("")):
    """Get user statistics."""
    from src.models import get_session, get_or_create_user_by_key
    from src.store import get_recall_count, get_cache_updated_at
    from sqlmodel import select

    user = get_or_create_user_by_key(user_id)
    with get_session() as session:
        pantry_items = session.exec(
            select(PantryItem).where(PantryItem.user_id == user.id)
        ).all()
        alerts = session.exec(
            select(Alert).where(Alert.user_id == user.id)
        ).all()
        total_alerts = len(alerts)
        disposed = sum(1 for a in alerts if a.status == "disposed")
        ignored = sum(1 for a in alerts if a.status == "ignored")
    
    # Recalls from store
    total_recalls = get_recall_count()
    active_recalls = total_recalls  # For now, assume all are active; could filter by status
    cache_updated_at = get_cache_updated_at()
    
    return StatsResponse(
        total_recalls=total_recalls,
        active_recalls=active_recalls,
        pantry_items=len(pantry_items),
        total_alerts=total_alerts,
        disposed=disposed,
        ignored=ignored,
        cache_updated_at=cache_updated_at,
    )


@app.get("/notifications/email", response_model=EmailSettings)
async def get_email_settings(user_id: str = Query("")):
    """Get user's email notification settings."""
    from src.models import get_or_create_user_by_key, get_session
    from sqlmodel import select

    user = get_or_create_user_by_key(user_id)
    return EmailSettings(
        email=user.email or "",
        notify_new_only=user.notify_new_only,
    )


@app.post("/notifications/email")
async def save_email_settings(
    settings: EmailSettingsUpdate,
    user_id: str = Query("")
):
    """Save user's email notification settings."""
    from src.models import get_or_create_user_by_key, get_session
    from sqlmodel import select

    with get_session() as session:
        user = session.exec(
            select(User).where(User.user_key == user_id)
        ).first()
        if not user:
            user = User(user_key=user_id, email=settings.email, notify_new_only=settings.notify_new_only)
            session.add(user)
        else:
            user.email = settings.email
            user.notify_new_only = settings.notify_new_only
        session.commit()

    return {"status": "saved"}


@app.post("/notifications/settings")
async def save_notification_settings(
    body: dict,
    user_id: str = Query("")
):
    """Save user's notification preferences to localStorage-compatible response."""
    # Preferences (language, threshold, sources) are stored client-side;
    # this endpoint is a no-op acknowledgement so the frontend call succeeds.
    return {"status": "saved"}
