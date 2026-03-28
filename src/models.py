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
    email: Optional[str] = Field(default=None, index=True)
    notify_new_only: bool = Field(default=True)  # True = new recalls only, False = all pantry matches
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


def get_all_users() -> list[User]:
    """Get all registered users."""
    with get_session() as sess:
        return list(sess.exec(select(User)).all())


def set_user_language(user_id: int, language: str) -> User:
    with get_session() as sess:
        user = sess.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        user.language = language
        sess.add(user)
        sess.commit()
        sess.refresh(user)
        return user


def set_user_email(user_id: int, email: str, notify_new_only: bool = True) -> User:
    with get_session() as sess:
        user = sess.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        user.email = email
        user.notify_new_only = notify_new_only
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


def delete_pantry_item(user_id: int, item_id: int) -> bool:
    """Delete a specific pantry item for a user. Returns True if deleted."""
    with get_session() as sess:
        item = sess.get(PantryItem, item_id)
        if not item or item.user_id != user_id:
            return False
        sess.delete(item)
        sess.commit()
        return True


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


def update_alert_feedback(user_id: int, alert_id: int, feedback: str) -> Alert | None:
    with get_session() as sess:
        alert = sess.get(Alert, alert_id)
        if not alert or alert.user_id != user_id:
            return None
        alert.status = feedback
        alert.responded_at = datetime.now(timezone.utc).isoformat()
        sess.add(alert)
        sess.commit()
        sess.refresh(alert)
        return alert


def get_alerts(user_id: int, limit: int = 50) -> list[Alert]:
    """Get recent alerts for a user."""
    with get_session() as sess:
        return list(
            sess.exec(
                select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at.desc()).limit(limit)
            ).all()
        )


def get_all_users() -> list[User]:
    with get_session() as sess:
        return list(sess.exec(select(User)).all())
