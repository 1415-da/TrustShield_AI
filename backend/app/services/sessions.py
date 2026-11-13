"""Server-side sign-in sessions and the cookies that carry them.

Browser clients authenticate with three cookies set by the API:
  * `trustshield_access_token`  — HttpOnly, short-lived JWT (path /)
  * `trustshield_refresh_token` — HttpOnly, long-lived JWT used only to mint new access tokens (path /)
  * `trustshield_csrf`          — readable by the page; echoed in `X-CSRF-Token` on state-changing requests
Server-to-server clients may instead send `Authorization: Bearer <access token>` (CSRF does not apply).
Every token carries the session id; revoking the session (sign-out) rejects all of its tokens at once.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_token
from app.models import AuthSession, User
from app.models.base import utcnow

ACCESS_COOKIE = "trustshield_access_token"
REFRESH_COOKIE = "trustshield_refresh_token"
CSRF_COOKIE = "trustshield_csrf"
CSRF_HEADER = "x-csrf-token"


def _secure() -> bool:
    s = get_settings()
    return s.cookie_secure if s.cookie_secure is not None else s.environment == "production"


def start(db: Session, user: User, request: Request | None) -> AuthSession:
    s = get_settings()
    session = AuthSession(id=secrets.token_urlsafe(24), user_id=user.id, organization_id=user.organization_id,
                          expires_at=utcnow() + timedelta(days=s.refresh_token_days),
                          user_agent=(request.headers.get("user-agent", "") if request else "")[:200])
    db.add(session)
    db.flush()
    return session


def active(db: Session, sid: str | None, user_id: int) -> AuthSession | None:
    if not sid:
        return None
    session = db.get(AuthSession, sid)
    if session is None or session.user_id != user_id or session.revoked_at is not None or session.expires_at <= utcnow():
        return None
    return session


def revoke(db: Session, session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at, session.revoked_reason = utcnow(), reason


def revoke_all(db: Session, user_id: int, reason: str) -> int:
    from sqlalchemy import select

    rows = list(db.scalars(select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))))
    for r in rows:
        revoke(db, r, reason)
    return len(rows)


def tokens(user: User, session: AuthSession) -> dict:
    s = get_settings()
    return {
        "access_token": create_token(str(user.id), "access", {"roles": user.role_keys}, sid=session.id),
        "refresh_token": create_token(str(user.id), "refresh", sid=session.id),
        "token_type": "bearer",
        "expires_in": s.access_token_minutes * 60,
    }


def set_cookies(response: Response, pair: dict) -> None:
    s = get_settings()
    common = {"secure": _secure(), "samesite": s.cookie_samesite, "path": "/"}
    response.set_cookie(ACCESS_COOKIE, pair["access_token"], max_age=s.access_token_minutes * 60, httponly=True, **common)
    response.set_cookie(REFRESH_COOKIE, pair["refresh_token"], max_age=s.refresh_token_days * 86400, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(24), max_age=s.refresh_token_days * 86400, httponly=False, **common)


def clear_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=_secure(), samesite=get_settings().cookie_samesite)
