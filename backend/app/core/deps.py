"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token, sha256_hex
from app.core.tenancy import ALL_ORGS, org_id, use_org
from app.models import ApiKey, ConnectedApp, User
from app.models.base import utcnow

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        raise unauthorized from None
    user = db.get(User, int(payload["sub"]), execution_options=ALL_ORGS)
    if user is None or not user.is_active:
        raise unauthorized
    use_org(db, user.organization_id)  # every query in this request is now scoped to the user's organization
    return user


def require_permission(*permissions: str) -> Callable[..., User]:
    """Dependency factory: the user must hold *all* listed permission scopes."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        missing = [p for p in permissions if not user.has(p)]
        if missing:
            raise HTTPException(status_code=403, detail=f"Missing permission: {', '.join(missing)}")
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
