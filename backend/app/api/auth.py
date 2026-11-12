from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.tenancy import ALL_ORGS, use_org
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import Role, User
from app.models.base import utcnow
from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, RegisterRequest, TokenPair, UserOut
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user: User) -> dict:
    return {
        "access_token": create_token(str(user.id), "access", {"roles": user.role_keys}),
        "refresh_token": create_token(str(user.id), "refresh"),
        "token_type": "bearer",
        "expires_in": get_settings().access_token_minutes * 60,
    }


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.strip().lower()).execution_options(**ALL_ORGS))
    if user is not None:
        use_org(db, user.organization_id)
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        audit.record(db, "auth.login_failed", details={"email_domain": body.email.split("@")[-1][:80]}, commit=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user.last_login_at = utcnow()
    audit.record(db, "auth.login", **audit.actor_fields(user))
    db.commit()
    return {**_tokens(user), "user": UserOut.of(user)}


@router.post("/register", response_model=LoginResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    if not get_settings().allow_self_registration:
        raise HTTPException(status_code=403, detail="Self-registration is disabled")
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower()).execution_options(**ALL_ORGS)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    role = db.scalar(select(Role).where(Role.key == "employee"))
    user = User(email=body.email.lower(), full_name=body.full_name, department=body.department, title="Employee",
                password_hash=hash_password(body.password), roles=[role] if role else [])
    db.add(user)
    db.flush()
    audit.record(db, "auth.registered", **audit.actor_fields(user))
    db.commit()
    return {**_tokens(user), "user": UserOut.of(user)}


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None
    user = db.get(User, int(payload["sub"]), execution_options=ALL_ORGS)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return _tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.of(user)
