"""HMAC signing helpers for inbound webhook authentication."""
import hashlib
import hmac
from typing import Optional


def sign(body: bytes, secret: str) -> str:
    """Return the hex HMAC-SHA256 of ``body`` under ``secret``."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def is_valid_signature(body: bytes, provided: Optional[str], secret: str) -> bool:
    """Constant-time check of a provided signature; a missing signature is invalid."""
    if not provided:
        return False
    return hmac.compare_digest(provided, sign(body, secret))
