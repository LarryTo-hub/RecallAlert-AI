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
from datetime import datetime
from urllib.parse import urlparse
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


def _norm_text(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _norm_recall_number(value: Optional[str]) -> str:
    # Keep alnum + dash and normalize casing/spacing for stable comparisons.
    raw = (value or "").strip().upper()
    if not raw:
        return ""
    return re.sub(r"\s+", "", raw)


def _canonical_record_key(record: Dict[str, Any]) -> str:
    """Stable key for deduping equivalent recalls across sources."""
    recall_number = _norm_recall_number(record.get("recall_number"))
    if recall_number:
        return f"rn:{recall_number}"

    # USDA and some FDA entries may omit recall_number; URL slug is often stable.
    url = (record.get("url") or "").strip()
    if url:
        try:
            parsed = urlparse(url)
            slug = _norm_text(parsed.path.rsplit("/", 1)[-1])
            if slug:
                return f"url:{slug}"
        except Exception:
            pass

    # For records without recall numbers, dedupe by core content, not source/date.
    product = _norm_text(record.get("product_description"))
    reason = _norm_text(record.get("reason_for_recall"))
    company = _norm_text(record.get("company_name") or record.get("recalling_firm"))
    return f"fallback:{product}|{reason}|{company}"


def _dedupe_records(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Preserve input order while removing duplicate recall entries."""
    seen = set()
    deduped = []
    for record in records:
        key = _canonical_record_key(record)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _parse_recall_date(value: Optional[str]) -> Optional[datetime]:
    raw = (value or "").strip()
    if not raw:
        return None

    # Known source date formats across FDA/USDA feeds.
    for fmt in (
        "%Y-%m-%d",
        "%Y%m%d",
        "%m/%d/%Y",
        "%a, %m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _recall_sort_key(record: Dict[str, Any]) -> tuple[datetime, int]:
    report_dt = _parse_recall_date(record.get("report_date"))
    init_dt = _parse_recall_date(record.get("recall_initiation_date"))
    best_dt = report_dt or init_dt or datetime.min

    try:
        row_id = int(record.get("id") or 0)
    except (TypeError, ValueError):
        row_id = 0

    return best_dt, row_id


def _sort_recalls_latest_first(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return sorted(records, key=_recall_sort_key, reverse=True)


def _source_matches(value: Optional[str], source_filter: Optional[str]) -> bool:
    if not source_filter:
        return True
    v = (value or "").strip().upper()
    f = source_filter.strip().upper()
    if not v:
        return False
    # Match canonical filters (FDA/USDA) to source variants (e.g., FDA-web, FDA-food).
    if f in {"FDA", "USDA"}:
        return v.startswith(f)
    return v == f


def _status_matches(value: Optional[str], status_filter: Optional[str]) -> bool:
    if not status_filter:
        return True

    normalized = (value or "").strip().upper()
    target = status_filter.strip().upper()

    # Some sources report active recalls as "ONGOING".
    if target == "ACTIVE":
        return normalized in {"ACTIVE", "ONGOING"}
    return normalized == target


def _record_matches(record: Dict[str, Any], source: Optional[str], status: Optional[str], q: Optional[str]) -> bool:
    if not _source_matches(record.get("source"), source):
        return False
    if not _status_matches(record.get("status"), status):
        return False

    if q:
        q_lower = q.lower()
        if (
            q_lower not in (record.get("product_description") or "").lower()
            and q_lower not in (record.get("brand_name") or "").lower()
            and q_lower not in (record.get("reason_for_recall") or "").lower()
            and q_lower not in (record.get("company_name") or "").lower()
        ):
            return False

    return True


def _fallback_id(record: Dict[str, Any]) -> str:
    """Build a stable ID when recall_number is missing."""
    parts = [
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

    recall_number = _norm_recall_number(record.get("recall_number")) or None
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
            "source": record.get("source"),
            "brand_name": record.get("brand_name"),
            "product_description": record.get("product_description"),
            "product_type": record.get("product_type"),
            "reason_for_recall": record.get("reason_for_recall"),
            "company_name": record.get("company_name") or record.get("recalling_firm"),
            "status": record.get("status"),
            "affected_area": record.get("affected_area") or record.get("distribution_pattern"),
            "report_date": record.get("report_date"),
            "recall_initiation_date": record.get("recall_initiation_date"),
            "url": record.get("url"),
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
    source: Optional[str] = None
    brand_name: Optional[str] = None
    product_type: Optional[str] = None
    company_name: Optional[str] = None
    status: Optional[str] = None
    affected_area: Optional[str] = None
    report_date: Optional[str] = None
    url: Optional[str] = None

def _sqlite_init_db() -> None:
    SQLModel.metadata.create_all(_engine)

def _sqlite_save_if_new(record: dict) -> Optional[Recall]:
    with Session(_engine) as sess:
        recall_number = _norm_recall_number(record.get("recall_number"))

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
            source=record.get("source"),
            brand_name=record.get("brand_name"),
            product_type=record.get("product_type"),
            company_name=record.get("company_name") or record.get("recalling_firm"),
            status=record.get("status"),
            affected_area=record.get("affected_area") or record.get("distribution_pattern"),
            report_date=record.get("report_date"),
            url=record.get("url"),
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


def get_all_recalls(
    skip: int = 0,
    limit: int = 20,
    source: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = "latest",
) -> list:
    """Get paginated list of recalls from storage.

    Args:
        sort: ``"latest"`` (default) — newest date first;
              ``"oldest"`` — oldest date first.
    """
    reverse = sort != "oldest"

    if STORE_BACKEND == "firebase":
        query = _firestore_client.collection("recalls")
        docs = query.stream()
        all_records = [doc.to_dict() for doc in docs]
        filtered = [
            r for r in all_records
            if _record_matches(r, source=source, status=status, q=q)
        ]
        deduped = _dedupe_records(filtered)
        ordered = sorted(deduped, key=_recall_sort_key, reverse=reverse)
        return ordered[skip: skip + limit]
    else:
        # For SQLite, filter in Python to keep matching logic identical to Firestore.
        with Session(_engine) as sess:
            query = select(Recall).order_by(Recall.id.desc())
            recalls = sess.exec(query).all()
            all_records = [r.model_dump() for r in recalls]
            filtered = [
                r for r in all_records
                if _record_matches(r, source=source, status=status, q=q)
            ]
            deduped = _dedupe_records(filtered)
            ordered = sorted(deduped, key=_recall_sort_key, reverse=reverse)
            return ordered[skip: skip + limit]


def get_recall_by_id(recall_id: int) -> Optional[dict]:
    """Get a recall by integer ID (SQLite only)."""
    if STORE_BACKEND == "firebase":
        # Firestore docs do not use integer IDs from SQLite.
        return None

    with Session(_engine) as sess:
        recall = sess.get(Recall, recall_id)
        return recall.model_dump() if recall else None


def get_recall_by_number(recall_number: str) -> Optional[dict]:
    """Get a recall by recall_number from the active backend."""
    if not recall_number:
        return None

    if STORE_BACKEND == "firebase":
        query = _firestore_client.collection("recalls").where("recall_number", "==", recall_number).limit(1)
        docs = list(query.stream())
        if not docs:
            return None
        return docs[0].to_dict()

    with Session(_engine) as sess:
        recall = sess.exec(select(Recall).where(Recall.recall_number == recall_number)).first()
        return recall.model_dump() if recall else None


def get_recall_count(
    source: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> int:
    """Get total number of recalls in storage."""
    # Use identical filtering semantics for both backends.
    if STORE_BACKEND == "firebase":
        query = _firestore_client.collection("recalls")
        docs = query.stream()
        all_records = [doc.to_dict() for doc in docs]
    else:
        with Session(_engine) as sess:
            query = select(Recall).order_by(Recall.id.desc())
            recalls = sess.exec(query).all()
            all_records = [r.model_dump() for r in recalls]

    filtered = [
        r for r in all_records
        if _record_matches(r, source=source, status=status, q=q)
    ]
    return len(_dedupe_records(filtered))


def get_cache_updated_at() -> Optional[str]:
    """Get the last cache update timestamp."""
    # For now, return None; could be implemented with a metadata table
    return None