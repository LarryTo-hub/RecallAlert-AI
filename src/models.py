"""Database models for users, pantry items, and alerts."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from pathlib import Path
from dotenv import load_dotenv
from sqlmodel import SQLModel, Field, create_engine, Session, select, Relationship

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///recalls.db")
_engine = create_engine(DATABASE_URL, echo=False)


# ── Tables ────────────────────────────────────────────────────────────────

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(unique=True, index=True)
    language: str = Field(default="en")  # en, es, vi, …
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PantryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)  # User.id
    product_name: str
    brand: Optional[str] = None
    lot_code: Optional[str] = None
    source: str = Field(default="manual")  # manual | receipt
    added_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    recall_id: Optional[int] = None  # Recall.id from store.py
    recall_number: Optional[str] = None
    message: str = ""
    status: str = Field(default="sent")  # sent | disposed | ignored
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    responded_at: Optional[str] = None


# ── DB helpers ────────────────────────────────────────────────────────────

def init_models_db() -> None:
    """Create all model tables if they don't exist."""
    SQLModel.metadata.create_all(_engine)


def get_session() -> Session:
    return Session(_engine)


# ── User helpers ──────────────────────────────────────────────────────────

def get_or_create_user(telegram_id: int, language: str = "en") -> User:
    with get_session() as sess:
        user = sess.exec(select(User).where(User.telegram_id == telegram_id)).first()
        if user:
            return user
        user = User(telegram_id=telegram_id, language=language)
        sess.add(user)
        sess.commit()
        sess.refresh(user)
        return user


def set_user_language(telegram_id: int, language: str) -> User:
    with get_session() as sess:
        user = sess.exec(select(User).where(User.telegram_id == telegram_id)).first()
        if not user:
            user = User(telegram_id=telegram_id, language=language)
            sess.add(user)
        else:
            user.language = language
            sess.add(user)
        sess.commit()
        sess.refresh(user)
        return user


# ── Pantry helpers ────────────────────────────────────────────────────────

def add_pantry_item(user_id: int, product_name: str,
                    brand: str | None = None, lot_code: str | None = None,
                    source: str = "manual") -> PantryItem:
    with get_session() as sess:
        item = PantryItem(
            user_id=user_id,
            product_name=product_name,
            brand=brand,
            lot_code=lot_code,
            source=source,
        )
        sess.add(item)
        sess.commit()
        sess.refresh(item)
        return item


def get_pantry(user_id: int) -> list[PantryItem]:
    with get_session() as sess:
        return list(sess.exec(select(PantryItem).where(PantryItem.user_id == user_id)).all())


def clear_pantry(user_id: int) -> int:
    """Delete all pantry items for a user. Returns count deleted."""
    with get_session() as sess:
        items = sess.exec(select(PantryItem).where(PantryItem.user_id == user_id)).all()
        count = len(items)
        for item in items:
            sess.delete(item)
        sess.commit()
        return count


# ── Alert helpers ─────────────────────────────────────────────────────────

def create_alert(user_id: int, recall_number: str | None,
                 message: str, recall_id: int | None = None) -> Alert:
    with get_session() as sess:
        alert = Alert(
            user_id=user_id,
            recall_id=recall_id,
            recall_number=recall_number,
            message=message,
        )
        sess.add(alert)
        sess.commit()
        sess.refresh(alert)
        return alert


def update_alert_feedback(alert_id: int, feedback: str) -> Alert | None:
    with get_session() as sess:
        alert = sess.get(Alert, alert_id)
        if not alert:
            return None
        alert.status = feedback
        alert.responded_at = datetime.now(timezone.utc).isoformat()
        sess.add(alert)
        sess.commit()
        sess.refresh(alert)
        return alert


def get_all_users() -> list[User]:
    with get_session() as sess:
        return list(sess.exec(select(User)).all())
