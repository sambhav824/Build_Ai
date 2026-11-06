"""
security.py — JWT Authentication Scaffold for BuildSmartAI
=========================================================
Placeholder security utilities. In production, replace SECRET_KEY with a
cryptographically secure random value stored in .env and never committed.

NOTE: Full authentication (OAuth2, role-based access) is outside the MVP scope.
      These helpers provide a scaffold for future implementation.
"""

import os
import hashlib
import hmac
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# Configuration — load from environment in production
# ---------------------------------------------------------------------------
_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "REPLACE_WITH_SECURE_RANDOM_KEY_IN_DOTENV")
_ALGORITHM = "HS256"
_DEFAULT_EXPIRY_MINUTES = 60 * 8  # 8-hour session


# ---------------------------------------------------------------------------
# Minimal JWT implementation (no external library dependency for MVP)
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def create_access_token(
    subject: str,
    role: str = "viewer",
    expiry_minutes: int = _DEFAULT_EXPIRY_MINUTES,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a signed JWT access token.

    Parameters
    ----------
    subject : str
        User identifier (e.g. user email or ID).
    role : str
        One of ``'admin'``, ``'builder'``, ``'viewer'``.
    expiry_minutes : int
        Token validity window in minutes.
    extra_claims : dict, optional
        Additional payload fields to embed.

    Returns
    -------
    str
        A compact JWT string ``header.payload.signature``.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expiry_minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    header = {"alg": _ALGORITHM, "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    signature = hmac.new(
        _SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256
    ).digest()

    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify a JWT token and return its payload.

    Raises
    ------
    ValueError
        If the token is malformed, signature invalid, or expired.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token: expected 3 parts")

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

        expected_sig = hmac.new(
            _SECRET_KEY.encode("utf-8"),
            signing_input,
            hashlib.sha256
        ).digest()

        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise ValueError("Token signature verification failed")

        payload = json.loads(_b64url_decode(payload_b64))
        now = int(datetime.now(timezone.utc).timestamp())
        if payload.get("exp", 0) < now:
            raise ValueError("Token has expired")

        return payload

    except (KeyError, json.JSONDecodeError, Exception) as exc:
        raise ValueError(f"Token validation error: {exc}") from exc


def hash_password(plain: str) -> str:
    """
    Return a salted SHA-256 hex digest of ``plain``.
    For production, replace with bcrypt or Argon2.
    """
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 260_000)
    return base64.b64encode(salt + digest).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify ``plain`` against a stored ``hashed`` password from :func:`hash_password`.
    """
    try:
        raw = base64.b64decode(hashed.encode())
        salt, stored = raw[:16], raw[16:]
        digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 260_000)
        return hmac.compare_digest(digest, stored)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Role-based permission helpers
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: Dict[str, list] = {
    "admin":   ["read", "write", "approve", "delete", "manage_users"],
    "builder": ["read", "write", "approve"],
    "viewer":  ["read"],
}


def has_permission(token_payload: Dict[str, Any], permission: str) -> bool:
    """Return True if the token's role grants ``permission``."""
    role = token_payload.get("role", "viewer")
    return permission in ROLE_PERMISSIONS.get(role, [])
