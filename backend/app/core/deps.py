"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

import hmac
from collections.abc import Callable

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_token, sha256_hex
from app.core.tenancy import ALL_ORGS, org_id, use_org
from app.models import ApiKey, ConnectedApp, User
from app.models.base import utcnow

bearer = HTTPBearer(auto_error=False)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
UNAUTHENTICATED_MESSAGE = "Your session has expired. Please sign in again."
DENIED_MESSAGE = "You do not have permission to perform this action."


def _unauthorized() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "UNAUTHENTICATED", UNAUTHENTICATED_MESSAGE)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate from the session cookie (browsers) or a bearer token (API clients).

    The token must be valid (signature, expiry, issuer, audience, type) *and* belong to a live server-side session,
    so sign-out takes effect immediately. Cookie-authenticated state-changing requests must echo the CSRF cookie.
    The request's workspace is always the signed-in user's own — never taken from the client.
    """
    from app.services import sessions

    token = creds.credentials if creds else request.cookies.get(sessions.ACCESS_COOKIE)
    if not token:
        raise _unauthorized()
    if creds is None and request.method not in SAFE_METHODS:
        sent, expected = request.headers.get(sessions.CSRF_HEADER), request.cookies.get(sessions.CSRF_COOKIE)
        if not sent or not expected or not hmac.compare_digest(sent, expected):
            raise AppError(403, "CSRF_FAILED", "Your session could not be verified. Refresh the page and try again.")
    try:
        payload = decode_token(token, "access")
    except jwt.PyJWTError:
        raise _unauthorized() from None
    user = db.get(User, int(payload["sub"]), execution_options=ALL_ORGS)
    if user is None or not user.is_active or sessions.active(db, payload.get("sid"), user.id) is None:
        raise _unauthorized()
    use_org(db, user.organization_id)  # every query in this request is now scoped to the user's organization
    request.state.user = user
    return user


def require_permission(*permissions: str) -> Callable[..., User]:
    """Dependency factory: the user must hold *all* listed permission scopes. Denials are audited."""

    def _dep(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        missing = [p for p in permissions if not user.has(p)]
        if missing:
            from app.services import audit

            audit.record(db, "auth.access_denied", **audit.actor_fields(user),
                         details={"permission": missing, "method": request.method, "path": request.url.path[:200]}, commit=True)
            raise AppError(403, "AUTHORIZATION_DENIED", DENIED_MESSAGE)
        return user

    return _dep


def resolve_app(
    x_trustshield_app_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ConnectedApp | None:
    """Attribute a request to a connected app. No header → the first-party web assistant."""
    if x_trustshield_app_key:
        key = db.scalar(select(ApiKey).where(ApiKey.key_hash == sha256_hex(x_trustshield_app_key)).execution_options(**ALL_ORGS))
        if key is None or key.revoked_at is not None or key.app.status != "active" or key.organization_id != org_id(db):
            raise HTTPException(status_code=401, detail="Invalid or revoked app key")
        key.last_used_at = utcnow()
        db.commit()
        return key.app
    return first_party_app(db)


FIRST_PARTY_SLUGS = ("web-assistant", "novacorp-assistant-web")


def first_party_app(db: Session) -> ConnectedApp | None:
    """The organization's own web assistant app (used when a request carries no app key)."""
    return db.scalar(select(ConnectedApp).where(ConnectedApp.slug.in_(FIRST_PARTY_SLUGS)).order_by(ConnectedApp.id).limit(1))
