"""Password hashing, JWT issuance/verification, and content hashing helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import get_settings

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(subject: str, token_type: TokenType, extra: dict[str, Any] | None = None, *, sid: str = "") -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "sid": sid,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "jti": secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Verify signature, expiry, issuer, audience and token type. Raises `jwt.PyJWTError` on any failure."""
    settings = get_settings()
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience, issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "iss", "aud", "type", "sid", "jti"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext_key, prefix, sha256_hash). Only the hash is persisted."""
    raw = "tsk_" + secrets.token_urlsafe(32)
    return raw, raw[:12], sha256_hex(raw)
