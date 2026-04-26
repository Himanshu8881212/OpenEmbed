"""
API Key authentication and input validation for EMBEd.

Auth model:
- Each store gets a unique API key on creation (sk-embed-...).
- Only the SHA256 hash is stored in ChromaDB collection metadata.
- Plaintext key returned ONLY once at creation.
- Frontend uses ADMIN_API_KEY to bypass per-store auth.
- Health and formats endpoints remain public.
"""
import re
import hmac
import secrets
import hashlib
from typing import Optional
from pathlib import Path

from fastapi import Request, HTTPException

from app.core.config import settings
from app.core.logger import app_logger as logger


# ── Key Generation & Verification ────────────────────────────────

def generate_api_key() -> tuple:
    """Generate a new API key and its SHA256 hash. Returns (plaintext, hash)."""
    plaintext = f"sk-embed-{secrets.token_urlsafe(32)}"
    hashed = hash_api_key(plaintext)
    return plaintext, hashed


def hash_api_key(key: str) -> str:
    """SHA256 hex digest of an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a key against a stored hash."""
    provided_hash = hash_api_key(provided_key)
    return hmac.compare_digest(provided_hash, stored_hash)


# ── Request Auth ─────────────────────────────────────────────────

def extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from X-API-Key header or ?api_key= query param.

    Query-param form is needed for <img>/<video>/<audio> tags that can't set
    custom headers — used by /api/files/{store}/{name}.
    """
    return request.headers.get("X-API-Key") or request.query_params.get("api_key")


def validate_admin_auth(request: Request) -> None:
    """
    Check that the request carries a valid ADMIN_API_KEY.
    No-op if admin key is not configured (dev mode).
    """
    if not settings.admin_api_key:
        return  # Dev mode: no admin key required
    key = extract_api_key(request)
    if not key or key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Admin API key required")


def validate_request_auth(request: Request, store_name: str) -> None:
    """
    Validate request is authorized to access the given store.
    1. Admin key bypass
    2. Per-store key check
    """
    key = extract_api_key(request)

    # Admin key bypasses per-store auth
    if settings.admin_api_key and key == settings.admin_api_key:
        return

    # No key provided
    if not key:
        if not settings.admin_api_key:
            return  # Dev mode: no auth required
        raise HTTPException(status_code=401, detail="API key required. Pass X-API-Key header.")

    # Look up store's key hash
    from app.services import chroma_service
    meta = chroma_service.get_collection_metadata(store_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Store '{store_name}' not found")

    stored_hash = meta.get("api_key_hash")
    if not stored_hash:
        # Legacy store without API key — require admin key
        if settings.admin_api_key:
            raise HTTPException(status_code=403, detail="This store requires admin API key")
        return  # Dev mode

    if not verify_api_key(key, stored_hash):
        logger.warning(f"Invalid API key attempt for store '{store_name}'")
        raise HTTPException(status_code=403, detail="Invalid API key for this store")


# ── Input Validation ─────────────────────────────────────────────

_STORE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$')


def validate_store_name(name: str) -> None:
    """Validate store name: alphanumeric, hyphens, underscores, 1-100 chars."""
    if not name or not _STORE_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=400,
            detail="Store name must be 1-100 characters, start with alphanumeric, "
                   "and contain only letters, numbers, hyphens, and underscores."
        )


def sanitize_filename(filename: str) -> str:
    """Sanitize an uploaded filename: strip paths, limit length."""
    # Get just the filename, no directory
    name = Path(filename).name
    # Remove any remaining dangerous characters
    name = re.sub(r'[^\w\s.\-]', '_', name)
    # Limit length
    name = name[:255]
    return name or "unnamed"
