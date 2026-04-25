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
import re
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, Query, UploadFile, File
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
    source: Optional[str] = None
    recall_number: Optional[str] = None
    brand_name: Optional[str] = None
    product_description: Optional[str] = None
    product_type: Optional[str] = None
    reason_for_recall: Optional[str] = None
    company_name: Optional[str] = None
    status: Optional[str] = None
    affected_area: Optional[str] = None
    report_date: Optional[str] = None
    recall_initiation_date: Optional[str] = None
    url: Optional[str] = None
    severity: Optional[str] = None
    brands: List[str] = Field(default_factory=list)
    lots: List[str] = Field(default_factory=list)


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
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174").split(",")
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


@app.post("/ocr")
async def ocr_receipt_endpoint(file: UploadFile = File(...)):
    """Extract pantry items from an uploaded receipt image."""
    from src.agent import ocr_receipt

    # Accept common image types. Some mobile browsers send octet-stream.
    if file.content_type and not (
        file.content_type.startswith("image/")
        or file.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Please upload an image file")

    try:
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Empty file upload")

        items = ocr_receipt(payload)
        if not isinstance(items, list):
            items = []

        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = (item.get("product_name") or "").strip()
            if not name:
                continue
            normalized.append(
                {
                    "product_name": name,
                    "brand": (item.get("brand") or None),
                    "lot_code": (item.get("lot_code") or None),
                }
            )

        return {"items": normalized}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("OCR endpoint failed: %s", e)
        raise HTTPException(status_code=500, detail="OCR failed")


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
    sort: str = Query("latest", pattern="^(latest|oldest)$"),
):
    """Get paginated recalls. ``sort`` accepts ``latest`` (default) or ``oldest``."""
    from src.store import get_all_recalls, get_recall_count, get_cache_updated_at

    def normalize_status(value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        lower = value.strip().lower()
        if lower in {"ongoing", "on going", "on-going"}:
            return "ACTIVE"
        upper = value.strip().upper()
        if upper in {"ACTIVE", "CLOSED", "TERMINATED"}:
            return upper
        if upper in {"INACTIVE", "RESOLVED", "COMPLETE", "COMPLETED"}:
            return upper
        return value.strip()

    def normalize_date(value: Optional[str]) -> Optional[str]:
        """Normalize any date string to YYYY-MM-DD.  Handles:
        YYYYMMDD, YYYY-MM-DD (already good), MM/DD/YYYY, M/D/YYYY,
        Month DD YYYY, Month DD, YYYY."""
        if not value:
            return value
        text = value.strip()
        # Already ISO: YYYY-MM-DD
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text
        # Compact: YYYYMMDD
        m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # US: MM/DD/YYYY or M/D/YYYY
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if m:
            return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
        # Month name: "January 22, 2015" or "January 22 2015"
        try:
            from datetime import datetime as _dt
            for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
                try:
                    return _dt.strptime(text, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    pass
        except Exception:
            pass
        return text

    recalls = get_all_recalls(skip=offset, limit=limit, source=source, status=status, q=q, sort=sort)
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
                "source": field(r, "source"),
                "recall_number": field(r, "recall_number"),
                "brand_name": field(r, "brand_name"),
                "product_description": field(r, "product_description"),
                "product_type": field(r, "product_type"),
                "reason_for_recall": field(r, "reason_for_recall"),
                "company_name": field(r, "company_name"),
                "status": normalize_status(field(r, "status")),
                "affected_area": field(r, "affected_area"),
                "report_date": normalize_date(field(r, "report_date")),
                "recall_initiation_date": normalize_date(field(r, "recall_initiation_date")),
                "url": field(r, "url"),
                "severity": field(r, "severity"),
                "brands": field(r, "brands") or [],
                "lots": field(r, "lots") or [],
            }
            for r in recalls
        ],
    }


@app.post("/match")
async def match_pantry(user_id: str = Query("")):
    """Match user's pantry items against stored recalls.

    Returns a list shaped for the frontend `MatchResult` contract.
    """
    from src.models import get_or_create_user_by_key, get_pantry
    from src.store import get_all_recalls
    from src.agent import parse_recall, match_pantry as agent_match_pantry

    user = get_or_create_user_by_key(user_id)
    pantry = get_pantry(user.id)
    if not pantry:
        return {"matches": [], "closed_matches": []}

    pantry_dicts = [
        {
            "product_name": p.product_name,
            "brand": p.brand,
            "lot_code": p.lot_code,
        }
        for p in pantry
    ]

    # Gather candidate recalls:
    # 1. Per-item text search by product name AND brand — finds product-specific recalls.
    # 2. Always also include the 100 most-recent recalls so active recalls
    #    for items not matched by a keyword search are never skipped.
    seen: set = set()
    candidates: List[dict] = []

    def _add_recall(recall: dict) -> None:
        key = (
            recall.get("recall_number") or "",
            recall.get("product_description") or "",
            recall.get("report_date") or "",
        )
        if key not in seen:
            seen.add(key)
            candidates.append(recall)

    for item in pantry_dicts:
        term = (item.get("product_name") or "").strip()
        brand = (item.get("brand") or "").strip()
        # Search by product name alone
        if term:
            for recall in get_all_recalls(skip=0, limit=50, q=term):
                _add_recall(recall)
        # Search by brand + product name combined so generic store brands ("Great Value",
        # "Kirkland") don't pull in every recall from that brand — they need a product hit too.
        if brand and term:
            for recall in get_all_recalls(skip=0, limit=50, q=f"{brand} {term}"):
                _add_recall(recall)
        elif brand:
            # No product name — search brand alone as last resort
            for recall in get_all_recalls(skip=0, limit=50, q=brand):
                _add_recall(recall)

    # Always merge the most-recent 100 active recalls so no current recall
    # is missed just because a pantry item keyword didn't match its DB text.
    for recall in get_all_recalls(skip=0, limit=100, status="active"):
        _add_recall(recall)

    def _raw_prefilter(recall: dict, pantry_items: List[dict]) -> bool:
        """Fast token check on raw DB fields — no Gemini. Skip obvious mismatches
        before paying the cost of parse_recall."""
        import re as _rp
        from src.agent import _extract_product_name, _tokenize
        prod = _extract_product_name(str(recall.get("product_description") or ""))
        brand = str(recall.get("brand_name") or "")
        prod_spaced = _rp.sub(r"([a-z])([A-Z])", r"\1 \2", prod)
        brand_spaced = _rp.sub(r"([a-z])([A-Z])", r"\1 \2", brand)
        # Product-only tokens (no brand) and combined tokens for different checks
        recall_prod_tokens = _tokenize(prod_spaced)
        recall_tokens = recall_prod_tokens | _tokenize(brand_spaced)
        recall_spaceless = _rp.sub(r"[^a-z0-9]", "", (prod_spaced + " " + brand_spaced).lower())
        recall_brand_lower = brand.lower().strip()
        for item in pantry_items:
            name = str(item.get("product_name") or "")
            item_brand = str(item.get("brand") or "").lower().strip()
            item_lot = str(item.get("lot_code") or "").lower().strip()
            name_spaced = _rp.sub(r"([a-z])([A-Z])", r"\1 \2", name)
            item_tokens = _tokenize(name_spaced)
            # Strip the brand word from item tokens so overlap only counts product words
            item_brand_tokens = _tokenize(item_brand)
            item_prod_tokens = item_tokens - item_brand_tokens
            item_spaceless = _rp.sub(r"[^a-z0-9]", "", name.lower())
            # Lot code exact match — check reason_for_recall and product_description
            if item_lot:
                recall_text = (
                    str(recall.get("reason_for_recall") or "") + " " +
                    str(recall.get("product_description") or "")
                ).lower()
                if item_lot in recall_text:
                    return True
            # Brand match + product-word overlap — excludes brand tokens from the
            # overlap so "Kraft" alone doesn't satisfy the overlap test for every Kraft recall.
            if item_brand and recall_brand_lower and item_brand == recall_brand_lower:
                if item_prod_tokens and (recall_prod_tokens & item_prod_tokens):
                    return True
            # Spaceless bidirectional substring — only for multi-word items.
            # Single words like "butter" would falsely match "buttermilk" or
            # "apples" would match "pineapplesorbet" due to accidental substring hits
            # when spaces are removed.
            if len(item_prod_tokens) >= 2:
                item_name_spaceless = _rp.sub(r"[^a-z0-9]", "", name.lower().replace(item_brand, "").strip())
                recall_prod_spaceless = _rp.sub(r"[^a-z0-9]", "", prod_spaced.lower())
                if item_name_spaceless and len(item_name_spaceless) >= 4 and (
                    item_name_spaceless in recall_prod_spaceless or recall_prod_spaceless in item_name_spaceless
                ):
                    return True
                # Full spaceless check (includes brand) — kept as fallback
                if item_spaceless and len(item_spaceless) >= 5 and (
                    item_spaceless in recall_spaceless or recall_spaceless in item_spaceless
                ):
                    return True
            # Product-word token overlap — require ≥2 matching non-brand tokens
            # so a single shared word like "cheese" doesn't match everything
            prod_overlap = recall_prod_tokens & item_prod_tokens
            if len(prod_overlap) >= 2:
                return True
        return False

    def deterministic_match(recall: dict, pantry_items: List[dict]) -> List[dict]:
        """Fallback matcher for obvious product-name matches missed by the LLM.

        Intentionally conservative: uses only the stripped product name (not
        the ingredient list) and skips single-word generic items that have no
        brand, so it cannot re-introduce ingredient-based false positives.
        """
        from src.agent import _extract_product_name, _tokenize, _normalize_name
        import re as _re2

        # Build a clean search text from structural fields only — NO ingredient lists.
        # CamelCase-split so "ReadyMeal" → "Ready Meal" before tokenizing.
        clean_desc = _extract_product_name(str(recall.get("product_description") or ""))
        brand_name = str(recall.get("brand_name") or "")
        clean_desc_spaced = _re2.sub(r"([a-z])([A-Z])", r"\1 \2", clean_desc)
        brand_name_spaced = _re2.sub(r"([a-z])([A-Z])", r"\1 \2", brand_name)
        clean_text = (clean_desc_spaced + " " + brand_name_spaced).lower()
        recall_norm = _normalize_name(clean_desc + " " + brand_name)
        recall_spaceless = _re2.sub(r"[^a-z0-9]", "", clean_text)
        # Product-only tokens for the recall (no brand contamination)
        recall_prod_tokens = _tokenize(clean_desc_spaced)
        recall_prod_spaceless = _re2.sub(r"[^a-z0-9]", "", clean_desc_spaced.lower())

        matched_items = []
        for item in pantry_items:
            name = str(item.get("product_name") or "").strip()
            item_brand = str(item.get("brand") or "").strip().lower()
            if not name:
                continue

            # CamelCase-split item name too so "ReadyMeal" → "ready meal" tokens
            name_spaced = _re2.sub(r"([a-z])([A-Z])", r"\1 \2", name)
            item_tokens = _tokenize(name_spaced)
            # Strip brand tokens from item so "Kraft" doesn't satisfy product overlap
            item_brand_tokens = _tokenize(item_brand)
            item_prod_tokens = item_tokens - item_brand_tokens
            item_norm = _normalize_name(name)

            # Skip single-word generic pantry items with no brand — they must
            # pass the LLM stage; the fallback cannot safely distinguish a bare
            # ingredient name from a product named after that ingredient.
            if len(item_prod_tokens) == 0 and not item_brand:
                continue

            name_lower = name.lower()
            item_prod_name = name_lower.replace(item_brand, "").strip()

            # Coverage ratio: overlap must be on product tokens only, not brand tokens.
            # This prevents "Kraft Cheddar Sliced" from matching "Kraft Dressing" via brand.
            #
            # Threshold is 0.70 (conservative) so this fallback only fires for close
            # product-name matches that Gemini missed.  Lower-confidence matches should
            # be handled by Gemini, not overridden here.  This also prevents
            # "Peanut Butter" (2 tokens, 50%) from matching "Peanut Butter ice cream"
            # (4 tokens) where Gemini correctly said "no".
            MIN_RECALL_COVERAGE = 0.70
            prod_overlap = len(item_prod_tokens & recall_prod_tokens)
            coverage = prod_overlap / len(recall_prod_tokens) if recall_prod_tokens else 0.0

            # Secondary signal: ≥2 overlapping product tokens with high coverage.
            if prod_overlap >= 2 and coverage >= MIN_RECALL_COVERAGE:
                matched_items.append(item)
                continue

            # Brand + product overlap — brand must appear AND product tokens must overlap recall product tokens
            # (not just recall_tokens which includes brand, causing brand-self-match)
            if item_brand and item_brand in clean_text and item_prod_tokens and (item_prod_tokens & recall_prod_tokens):
                matched_items.append(item)

        return matched_items

    matches = []
    for recall in candidates:
        # Fast raw-field pre-filter: skip Gemini calls for obvious non-matches
        if not _raw_prefilter(recall, pantry_dicts):
            continue
        parsed = parse_recall(recall)
        matched_items = agent_match_pantry(parsed, pantry_dicts)

        # Guardrail: if LLM matcher misses obvious direct text matches, use deterministic fallback.
        if not matched_items:
            matched_items = deterministic_match(recall, pantry_dicts)

        if not matched_items:
            continue

        # Boost severity to "high" when the pantry item name closely matches
        # the recalled product name — an exact/near-exact name match is high risk.
        from src.agent import _tokenize, _extract_product_name
        base_severity = (parsed.get("severity") or "medium").lower()
        recall_product_tokens: set = set()
        for _p in (parsed.get("products") or []):
            recall_product_tokens |= _tokenize(_extract_product_name(_p))
        for _b in (parsed.get("brands") or []):
            recall_product_tokens |= _tokenize(_b)
        for _mi in matched_items:
            _item_tokens = _tokenize(_mi.get("product_name", ""))
            if _mi.get("brand"):
                _item_tokens |= _tokenize(_mi["brand"])
            if recall_product_tokens and _item_tokens:
                _coverage = len(_item_tokens & recall_product_tokens) / len(_item_tokens)
                if _coverage >= 0.8 and base_severity != "high":
                    base_severity = "high"
                    break
        parsed_payload = {
            "severity": base_severity,
            "reason_summary": parsed.get("reason_summary")
            or (recall.get("reason_for_recall") or ""),
            "products": parsed.get("products") or [],
            "brands": parsed.get("brands") or [],
        }

        matches.append(
            {
                "recall": recall,
                "parsed": parsed_payload,
                "matched_items": matched_items,
            }
        )

    # Split matches into active vs closed/terminated/completed recalls.
    _inactive = {"CLOSED", "TERMINATED", "COMPLETED"}
    def _is_active(status: Optional[str]) -> bool:
        return (status or "").strip().upper() not in _inactive

    active_matches = [m for m in matches if _is_active(m["recall"].get("status"))]
    closed_matches = [m for m in matches if not _is_active(m["recall"].get("status"))]

    # Only email for active (still-open) recalls.
    if active_matches and user.email:
        try:
            from src.notifier import send_email_smtp
            matched_products = ", ".join(
                m["product_name"] for match in active_matches for m in match["matched_items"]
            )
            subject = f"[RecallAlert] {len(active_matches)} active recall(s) matched your pantry"
            body = f"The following pantry items matched active recalls:\n\n{matched_products}\n\n"
            for m in active_matches:
                recall = m["recall"]
                body += f"• {recall.get('product_description', 'Unknown')} — {recall.get('reason_for_recall', 'N/A')}\n"
            body += "\nCheck the RecallAlert app for full details."
            send_email_smtp(subject, body, user.email)
            logger.info("Sent match email to %s", user.email)
        except Exception:
            logger.exception("Failed to send match email to %s", user.email)

    return {"matches": active_matches, "closed_matches": closed_matches}


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
    from src.models import get_or_create_user_by_key, update_alert_feedback, get_pantry, delete_pantry_item
    from src.store import get_recall_by_id, get_recall_by_number
    from src.agent import parse_recall, match_pantry as agent_match_pantry

    user = get_or_create_user_by_key(user_id)
    updated = update_alert_feedback(user.id, alert_id, feedback.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")

    pantry_items_removed = 0
    if feedback.status == "disposed":
        recall = None
        if updated.recall_id:
            recall = get_recall_by_id(updated.recall_id)
        if recall is None and updated.recall_number:
            recall = get_recall_by_number(updated.recall_number)

        if recall:
            pantry = get_pantry(user.id)
            pantry_dicts = [
                {
                    "id": p.id,
                    "product_name": p.product_name,
                    "brand": p.brand,
                    "lot_code": p.lot_code,
                }
                for p in pantry
            ]

            parsed = parse_recall(recall)
            matched = agent_match_pantry(parsed, pantry_dicts)

            # Guardrail deterministic fallback — use ingredient-stripped text
            # and skip single-word items to avoid re-introducing false positives.
            if not matched:
                from src.agent import _extract_product_name, _tokenize
                clean_desc = _extract_product_name(str(recall.get("product_description") or ""))
                brand_name = str(recall.get("brand_name") or "")
                clean_text = (clean_desc + " " + brand_name).lower()
                MIN_RECALL_COVERAGE = 0.40
                matched = []
                for item in pantry_dicts:
                    name = str(item.get("product_name") or "").strip()
                    item_brand = str(item.get("brand") or "").strip().lower()
                    if not name:
                        continue
                    item_tokens = _tokenize(name)
                    # Same single-word and coverage guards as the /match fallback.
                    if len(item_tokens) <= 1 and not item_brand:
                        continue
                    name_lower = name.lower()
                    recall_tokens = _tokenize(clean_text)
                    overlap = len(item_tokens & recall_tokens)
                    coverage = overlap / len(recall_tokens) if recall_tokens else 0.0
                    if name_lower in clean_text and coverage >= MIN_RECALL_COVERAGE:
                        matched.append(item)
                        continue
                    if overlap >= 2 and coverage >= MIN_RECALL_COVERAGE:
                        matched.append(item)
                        continue
                    if item_brand and item_brand in clean_text:
                        matched.append(item)

            for item in matched:
                item_id = item.get("id")
                if item_id and delete_pantry_item(user.id, item_id):
                    pantry_items_removed += 1

    return {
        "id": updated.id,
        "user_id": updated.user_id,
        "recall_id": updated.recall_id,
        "recall_number": updated.recall_number,
        "message": updated.message,
        "status": updated.status,
        "created_at": updated.created_at,
        "responded_at": updated.responded_at,
        "pantry_items_removed": pantry_items_removed,
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
        active_connections.pop(user_id, None)


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


# ──────────────────────────────────────────────────────────────────────────────
# Chat Endpoint
# ──────────────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    user_id: str = ""


@app.post("/chat")
async def chat_endpoint(body: ChatRequest):
    """AI chatbot endpoint — answers food-safety questions using Gemini."""
    from src.agent import chat_with_agent
    from src.models import get_or_create_user_by_key, get_pantry
    from src.store import get_all_recalls

    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        user = get_or_create_user_by_key(body.user_id)
        pantry = get_pantry(user.id)
        pantry_dicts = [
            {"product_name": p.product_name, "brand": p.brand, "lot_code": p.lot_code}
            for p in pantry
        ]
        recent_recalls = get_all_recalls(skip=0, limit=20)
        if not isinstance(recent_recalls, list):
            recent_recalls = list(recent_recalls)
        # Convert ORM objects to plain dicts if needed
        recall_dicts = []
        for r in recent_recalls:
            if isinstance(r, dict):
                recall_dicts.append(r)
            else:
                recall_dicts.append({
                    "product_description": getattr(r, "product_description", ""),
                    "reason_for_recall": getattr(r, "reason_for_recall", ""),
                    "status": getattr(r, "status", ""),
                    "brand_name": getattr(r, "brand_name", ""),
                })

        reply = chat_with_agent(body.message, pantry_dicts, recall_dicts)
        return {"reply": reply}
    except Exception as e:
        logger.exception("Chat endpoint error: %s", e)
        raise HTTPException(status_code=500, detail="Chat failed")




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
    # get_recall_count(status="ACTIVE") already treats ONGOING as ACTIVE.
    active_recalls = get_recall_count(status="ACTIVE")
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
    """Save user's notification preferences."""
    from src.models import get_session
    from sqlmodel import select

    with get_session() as session:
        user = session.exec(
            select(User).where(User.user_key == user_id)
        ).first()

        if not user:
            user = User(
                user_key=user_id,
                language=body.get("language", "en"),
                severity_threshold=body.get("severity_threshold", "all"),
                sources=body.get("sources", "both"),
            )
            session.add(user)
        else:
            user.language = body.get("language", user.language or "en")
            user.severity_threshold = body.get(
                "severity_threshold",
                getattr(user, "severity_threshold", "all"),
            )
            user.sources = body.get(
                "sources",
                getattr(user, "sources", "both"),
            )

        session.commit()

    return {"status": "saved"}


class NotificationSettingsResponse(BaseModel):
    language: str
    severity_threshold: str
    sources: str


@app.get("/notifications/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(user_id: str = Query("")):
    from src.models import get_or_create_user_by_key

    user = get_or_create_user_by_key(user_id)

    return NotificationSettingsResponse(
        language=user.language or "en",
        severity_threshold=getattr(user, "severity_threshold", "all"),
        sources=getattr(user, "sources", "both"),
    )

@app.get("/api/recalls")
async def api_get_recalls(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = Query("latest"),
):
    return await get_recalls(offset, limit, source, status, q, sort)


@app.get("/api/stats", response_model=StatsResponse)
async def api_get_stats(user_id: str = Query("")):
    return await get_stats(user_id)


@app.get("/api/pantry", response_model=PantryListResponse)
async def api_get_pantry(user_id: str = Query("")):
    return await get_pantry_endpoint(user_id)


@app.post("/api/pantry/items", response_model=PantryItemResponse)
async def api_add_pantry_item(item: PantryItemRequest, user_id: str = Query("")):
    return await add_pantry_item_endpoint(item, user_id)


@app.post("/api/fetch")
async def api_trigger_fetch():
    return await trigger_fetch()

@app.get("/api/notifications/email", response_model=EmailSettings)
async def api_get_email_settings(user_id: str = Query("")):
    return await get_email_settings(user_id)


@app.post("/api/notifications/email")
async def api_save_email_settings(
    settings: EmailSettingsUpdate,
    user_id: str = Query("")
):
    return await save_email_settings(settings, user_id)


@app.get("/api/notifications/settings", response_model=NotificationSettingsResponse)
async def api_get_notification_settings(user_id: str = Query("")):
    return await get_notification_settings(user_id)


@app.post("/api/notifications/settings")
async def api_save_notification_settings(
    body: dict,
    user_id: str = Query("")
):
    return await save_notification_settings(body, user_id)

@app.post("/api/chat")
async def api_chat_endpoint(body: ChatRequest):
    return await chat_endpoint(body)

@app.post("/api/ocr")
async def api_ocr_receipt_endpoint(file: UploadFile = File(...)):
    return await ocr_receipt_endpoint(file)

@app.post("/api/match")
async def api_match_pantry(user_id: str = Query("")):
    return await match_pantry(user_id)

@app.delete("/api/pantry/items/{item_id}")
async def api_delete_pantry_item(item_id: int, user_id: str = Query("")):
    return await delete_pantry_item_endpoint(item_id, user_id)

@app.delete("/api/pantry")
async def api_clear_pantry(user_id: str = Query("")):
    return await clear_pantry_endpoint(user_id)

@app.get("/api/alerts")
async def api_get_alerts(user_id: str = Query(""), status: Optional[str] = None):
    return await get_alerts_endpoint(user_id, status)

@app.patch("/api/alerts/{alert_id}/feedback")
async def api_update_alert_feedback(alert_id: int, feedback: AlertFeedback, user_id: str = Query("")):
    return await submit_feedback(alert_id, feedback, user_id)