"""Store backend for recall records.

Supports:
- SQLite via SQLModel (default)
- Firestore via Firebase Admin SDK (set STORE_BACKEND=firebase)
"""

from __future__ import annotations

import os
import re
import hashlib
import logging
from typing import Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# In production (Cloud Run, Cloud Functions), default to Firebase/Firestore
# Local development defaults to SQLite
ENV = os.getenv("ENVIRONMENT", "development").lower()
DEFAULT_BACKEND = "firebase" if ENV == "production" else "sqlite"
STORE_BACKEND = os.getenv("STORE_BACKEND", DEFAULT_BACKEND).lower()

# ---------- Firebase / Firestore ----------
_firestore_client = None


def _fallback_id(record: Dict[str, Any]) -> str:
    """Build a stable ID when recall_number is missing."""
    parts = [
        str(record.get("source") or ""),
        str(record.get("report_date") or record.get("recall_initiation_date") or ""),
        str(record.get("product_description") or ""),
        str(record.get("reason_for_recall") or ""),
        str(record.get("company_name") or record.get("recalling_firm") or ""),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"fallback-{digest}"


def _sanitize_doc_id(doc_id: str) -> str:
    """Sanitize doc_id for Firestore (remove invalid characters)."""
    # Firestore allows: alphanumeric, underscore, hyphen
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', str(doc_id))
    # Ensure it's not empty
    result = sanitized or "doc"
    logger.debug(f"Sanitized doc_id: {doc_id} -> {result}")
    return result

def _init_firestore() -> None:
    """Initialize Firebase Admin + Firestore client once."""
    global _firestore_client
    if _firestore_client is not None:
        return

    import firebase_admin
    from firebase_admin import credentials, firestore
    import base64
    import json
    import tempfile

    if not firebase_admin._apps:
        cred_path = os.getenv("FIREBASE_CRED_PATH")
        if not cred_path:
            raise RuntimeError("FIREBASE_CRED_PATH is not set in .env")
        
        # Check if it's a base64-encoded JSON (from Render environment variable)
        if not os.path.exists(cred_path):
            try:
                # Try to decode as base64
                cred_json = base64.b64decode(cred_path).decode("utf-8")
                # Verify it's valid JSON
                json.loads(cred_json)
                # Write to a temporary file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
                    f.write(cred_json)
                    cred_path = f.name
            except (base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
                raise RuntimeError(f"Firebase cred file not found at: {cred_path} and could not decode as base64")
        
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

    _firestore_client = firestore.client()


def _firestore_save_if_new(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Save recall to Firestore if not already present (doc id = stable external id)."""
    _init_firestore()

    recall_number = record.get("recall_number")
    raw_doc_id = str(recall_number or _fallback_id(record))
    doc_id = _sanitize_doc_id(raw_doc_id)
    
    logger.info(f"Saving recall with doc_id={doc_id} (raw={raw_doc_id})")
    
    try:
        doc_ref = _firestore_client.collection("recalls").document(doc_id)
    except ValueError as e:
        logger.error(f"Invalid doc_id '{doc_id}': {e}")
        raise
    snap = doc_ref.get()
    if snap.exists:
        return None

    doc_ref.set(
        {
            "recall_number": recall_number,
            "external_id": doc_id,
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
        recall_number = str(record.get("recall_number") or "").strip()

        if recall_number:
            q = select(Recall).where(Recall.recall_number == recall_number)
            existing = sess.exec(q).first()
            if existing:
                return None
        else:
            # Fallback dedupe path for sources without official recall numbers.
            q = select(Recall).where(
                Recall.product_description == (record.get("product_description") or ""),
                Recall.reason_for_recall == (record.get("reason_for_recall") or ""),
                Recall.recall_initiation_date == (record.get("recall_initiation_date") or ""),
            )
            existing = sess.exec(q).first()
            if existing:
                return None

        stored_recall_number = recall_number or _fallback_id(record)

        r = Recall(
            recall_number=stored_recall_number,
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


def cleanup() -> None:
    """Close all database connections (called on shutdown)."""
    global _firestore_client
    if _firestore_client is not None:
        # Firestore clients don't need explicit close, but we clear reference
        _firestore_client = None
    # SQLite engine doesn't require explicit cleanup


def get_all_recalls(skip: int = 0, limit: int = 20) -> list:
    """Get paginated list of recalls from storage."""
    if STORE_BACKEND == "firebase":
        # For Firestore, query the recalls collection
        docs = _firestore_client.collection("recalls").limit(limit).offset(skip).stream()
        return [doc.to_dict() for doc in docs]
    else:
        # For SQLite
        with Session(_engine) as sess:
            recalls = sess.exec(
                select(Recall).order_by(Recall.id.desc()).offset(skip).limit(limit)
            ).all()
            return list(recalls)