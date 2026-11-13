"""Sign-in, token refresh, sign-out and the current session.

Browsers use HTTP-only cookies (see `app.services.sessions`); the JSON body also carries the tokens for
server-to-server API clients that authenticate with `Authorization: Bearer`.
There is no self-registration: accounts are created by creating a workspace (`/orgs/signup`) or by an admin.
"""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import UNAUTHENTICATED_MESSAGE, get_current_user
from app.core.errors import AppError
from app.core.ratelimit import client_key, limiter
from app.core.security import decode_token, verify_password
from app.core.tenancy import ALL_ORGS, use_org
from app.models import User
from app.models.base import utcnow
from app.models.organization import DEFAULT_ORG_ID
from app.schemas.auth import LoginRequest, LoginResponse, TokenPair, UserOut
from app.services import audit, sessions

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "Incorrect email or password."
# Brute-force protection counts *failed* attempts only, so busy offices and shared networks can still sign in.
LOGIN_LIMIT_PER_CLIENT = (20, 60.0)   # failed attempts per minute from one network address
LOGIN_LIMIT_PER_EMAIL = (10, 300.0)   # failed attempts per 5 minutes for one account


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


def sign_in(db: Session, user: User, request: Request, response: Response) -> dict:
    """Start a server-side session for `user`, set the session cookies and return the token pair + user."""
    session = sessions.start(db, user, request)
    pair = sessions.tokens(user, session)
    sessions.set_cookies(response, pair)
    return {**pair, "user": UserOut.of(user)}


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    client, account = f"login:{client_key(request)}", f"login-email:{email}"
    if limiter.exceeded(client, *LOGIN_LIMIT_PER_CLIENT) or limiter.exceeded(account, *LOGIN_LIMIT_PER_EMAIL):
        raise AppError(429, "RATE_LIMITED", "Too many sign-in attempts. Please try again shortly.")
    user = db.scalar(select(User).where(func.lower(User.email) == email).execution_options(**ALL_ORGS))
    # Failed sign-ins for an unknown address belong to no workspace; they are recorded in the platform workspace.
    use_org(db, user.organization_id if user is not None else DEFAULT_ORG_ID)
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        limiter.hit(client)
        limiter.hit(account)
        audit.record(db, "auth.login_failed", details={"email_domain": email.split("@")[-1][:80]}, commit=True)
        raise AppError(401, "INVALID_CREDENTIALS", INVALID_CREDENTIALS)
    user.last_login_at = utcnow()
    result = sign_in(db, user, request, response)
    audit.record(db, "auth.login", **audit.actor_fields(user))
    db.commit()
    return result


@router.post("/refresh", response_model=TokenPair)
def refresh(request: Request, response: Response, body: RefreshRequest | None = None, db: Session = Depends(get_db)) -> dict:
    """Mint a new access token from a refresh token (cookie, or body for API clients). The session must be live."""
    token = (body.refresh_token if body else None) or request.cookies.get(sessions.REFRESH_COOKIE)
    unauthorized = AppError(401, "UNAUTHENTICATED", UNAUTHENTICATED_MESSAGE)
    if not token:
        raise unauthorized
    try:
        payload = decode_token(token, "refresh")
    except jwt.PyJWTError:
        sessions.clear_cookies(response)
        raise unauthorized from None
    user = db.get(User, int(payload["sub"]), execution_options=ALL_ORGS)
    session = sessions.active(db, payload.get("sid"), user.id) if user is not None else None
    if user is None or not user.is_active or session is None:
        raise unauthorized
    session.last_seen_at = utcnow()
    pair = sessions.tokens(user, session)
    # Keep the caller's refresh token (it stays bound to the same session) so concurrent refreshes never conflict.
    pair["refresh_token"] = token
    sessions.set_cookies(response, pair)
    db.commit()
    return pair


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    """Revoke the current session (every token it issued stops working) and clear the session cookies.

    Always succeeds, so a client can sign out even with an expired token.
    """
    header = request.headers.get("authorization", "")
    candidates = [header[7:] if header.lower().startswith("bearer ") else None,
                  request.cookies.get(sessions.ACCESS_COOKIE), request.cookies.get(sessions.REFRESH_COOKIE)]
    for token in filter(None, candidates):
        payload = None
        for kind in ("access", "refresh"):
            try:
                payload = decode_token(token, kind)
                break
            except jwt.PyJWTError:
                continue
        if not payload:
            continue
        user = db.get(User, int(payload["sub"]), execution_options=ALL_ORGS)
        session = sessions.active(db, payload.get("sid"), user.id) if user is not None else None
        if user is not None and session is not None:
            use_org(db, user.organization_id)
            sessions.revoke(db, session, "logout")
            audit.record(db, "auth.logout", **audit.actor_fields(user))
            db.commit()
            break
    out = Response(status_code=204)
    sessions.clear_cookies(out)
    return out


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    """The signed-in user with their workspace, roles, permissions and data scopes (all resolved server-side)."""
    return UserOut.of(user)
