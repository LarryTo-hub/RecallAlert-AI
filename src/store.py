"""Store backend for recall records.

Supports:
- SQLite via SQLModel (default)
- Firestore via Firebase Admin SDK (set STORE_BACKEND=firebase)
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()

STORE_BACKEND = os.getenv("STORE_BACKEND", "sqlite").lower()

# ---------- Firebase / Firestore ----------
_firestore_client = None

def _init_firestore() -> None:
    """Initialize Firebase Admin + Firestore client once."""
    global _firestore_client
    if _firestore_client is not None:
        return

    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        cred_path = os.getenv("FIREBASE_CRED_PATH")
        if not cred_path:
            raise RuntimeError("FIREBASE_CRED_PATH is not set in .env")
        if not os.path.exists(cred_path):
            raise RuntimeError(f"Firebase cred file not found at: {cred_path}")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

    _firestore_client = firestore.client()


def _firestore_save_if_new(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Save recall to Firestore if not already present (doc id = recall_number)."""
    _init_firestore()

    recall_number = record.get("recall_number")
    if not recall_number:
        return None

    doc_ref = _firestore_client.collection("recalls").document(str(recall_number))
    snap = doc_ref.get()
    if snap.exists:
        return None

    doc_ref.set(
        {
            "recall_number": recall_number,
            "reason_for_recall": record.get("reason_for_recall"),
            "product_description": record.get("product_description"),
            "recall_initiation_date": record.get("recall_initiation_date"),
        }
    )
    return record


# ---------- SQLite (existing) ----------
from sqlmodel import SQLModel, Field, create_engine, Session, select  # noqa: E402

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///recalls.db")
_engine = create_engine(DATABASE_URL, echo=False)

class Recall(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recall_number: str
    reason_for_recall: Optional[str] = None
    product_description: Optional[str] = None
    recall_initiation_date: Optional[str] = None

def _sqlite_init_db() -> None:
    SQLModel.metadata.create_all(_engine)

def _sqlite_save_if_new(record: dict) -> Optional[Recall]:
    with Session(_engine) as sess:
        q = select(Recall).where(Recall.recall_number == record.get("recall_number"))
        existing = sess.exec(q).first()
        if existing:
            return None
        r = Recall(
            recall_number=record.get("recall_number", ""),
            reason_for_recall=record.get("reason_for_recall", ""),
            product_description=record.get("product_description", ""),
            recall_initiation_date=record.get("recall_initiation_date", ""),
        )
        sess.add(r)
        sess.commit()
        sess.refresh(r)
        return r


# ---------- Public API ----------
def init_db() -> None:
    if STORE_BACKEND == "firebase":
        _init_firestore()
    else:
        _sqlite_init_db()

def save_if_new(record: dict):
    if STORE_BACKEND == "firebase":
        return _firestore_save_if_new(record)
    return _sqlite_save_if_new(record)