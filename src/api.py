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


class RecallResponse(BaseModel):
    recall_number: str
    product_description: str
    reason_for_recall: Optional[str]
    recall_initiation_date: Optional[str]
    severity: Optional[str] = None
    brands: List[str] = []
    lots: List[str] = []


class AlertFeedback(BaseModel):
    status: str = Field(..., pattern="^(disposed|ignored)$")


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
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
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


@app.get("/pantry", response_model=List[PantryItemResponse])
async def get_pantry(token_payload: dict = Depends(verify_token)):
    """Get user's pantry items."""
    from src.models import get_pantry

    user_id = token_payload["user_id"]
    items = get_pantry(user_id)
    return [
        {
            "id": item.id,
            "product_name": item.product_name,
            "brand": item.brand,
            "lot_code": item.lot_code,
            "added_at": item.added_at,
        }
        for item in items
    ]


@app.post("/pantry/items", response_model=PantryItemResponse)
async def add_pantry_item(item: PantryItemRequest, token_payload: dict = Depends(verify_token)):
    """Add item to user's pantry."""
    from src.models import add_pantry_item

    user_id = token_payload["user_id"]
    added = add_pantry_item(user_id, item.product_name, item.brand, item.lot_code)
    return {
        "id": added.id,
        "product_name": added.product_name,
        "brand": added.brand,
        "lot_code": added.lot_code,
        "added_at": added.added_at,
    }


@app.delete("/pantry/items/{item_id}")
async def delete_pantry_item(item_id: int, token_payload: dict = Depends(verify_token)):
    """Delete pantry item."""
    from src.models import delete_pantry_item

    user_id = token_payload["user_id"]
    delete_pantry_item(user_id, item_id)
    return {"status": "ok"}


@app.delete("/pantry")
async def clear_pantry(token_payload: dict = Depends(verify_token)):
    """Clear user's entire pantry."""
    from src.models import clear_pantry

    user_id = token_payload["user_id"]
    clear_pantry(user_id)
    return {"status": "ok"}


# ──────────────────────────────────────────────────────────────────────────────
# Recall Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@app.get("/recalls", response_model=List[RecallResponse])
async def get_recalls(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = None,
):
    """Get latest recalls (paginated, optionally filtered by severity)."""
    from src.store import get_all_recalls

    recalls = get_all_recalls(skip=skip, limit=limit)
    return [
        {
            "recall_number": r.recall_number,
            "product_description": r.product_description,
            "reason_for_recall": r.reason_for_recall,
            "recall_initiation_date": r.recall_initiation_date,
        }
        for r in recalls
    ]


@app.get("/recalls/matching")
async def get_matching_recalls(token_payload: dict = Depends(verify_token)):
    """Get recalls matching user's pantry."""
    from src.models import get_pantry, get_alerts
    from src.agent import parse_recall

    user_id = token_payload["user_id"]
    pantry = get_pantry(user_id)
    alerts = get_alerts(user_id)

    return [
        {
            "alert_id": a.id,
            "recall_number": a.recall_number,
            "message": a.message,
            "status": a.status,
            "created_at": a.created_at,
        }
        for a in alerts
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Alert Feedback Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@app.put("/alerts/{alert_id}/feedback")
async def submit_feedback(alert_id: int, feedback: AlertFeedback, token_payload: dict = Depends(verify_token)):
    """Submit feedback for an alert (disposed/ignored)."""
    from src.models import update_alert_feedback

    user_id = token_payload["user_id"]
    updated = update_alert_feedback(user_id, alert_id, feedback.status)
    return {
        "status": "ok",
        "alert_id": alert_id,
        "feedback": feedback.status,
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


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "ok"}


@app.get("/")
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
    telegram_id: int = 0


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with RecallAlert AI for recall questions and disposal instructions."""
    try:
        from src import agent
        
        user_id = request.telegram_id or 0
        message = request.message.strip()
        
        # Get user's pantry if registered
        pantry = []
        try:
            from src.models import get_pantry
            pantry = get_pantry(user_id)
        except Exception:
            pass
        
        # Build context
        pantry_str = ""
        if pantry:
            items = [f"{item.get('product_name', '?')}" + 
                     (f" ({item.get('brand', '')})" if item.get('brand') else "") 
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
