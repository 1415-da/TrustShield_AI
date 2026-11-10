"""Users & roles, connected apps & API keys, and read-only gateway settings."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.permissions import PERMISSION_CATALOGUE
from app.core.security import generate_api_key
from app.guardrails.pii import get_pii_detector
from app.models import ApiKey, ConnectedApp, Role, User
from app.models.base import utcnow
from app.schemas.auth import UserOut
from app.schemas.misc import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, AppCreate, AppOut, AppUpdate, RoleOut, RoleUpdate, UserUpdate
from app.services import audit
from app.services.embeddings import get_embedder
from app.services.llm import get_provider

router = APIRouter(prefix="/admin", tags=["admin"])
can_users = require_permission("users:manage")
can_apps = require_permission("apps:manage")
can_settings = require_permission("settings:read")


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(can_users), db: Session = Depends(get_db)) -> list:
    return [UserOut.of(u) for u in db.scalars(select(User).order_by(User.full_name))]


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, admin: User = Depends(can_users), db: Session = Depends(get_db)) -> UserOut:
    target = db.get(User, user_id)
    if target is None:
        raise NotFound("User")
    if target.id == admin.id and (body.is_active is False or (body.role_keys is not None and "trustshield_admin" not in body.role_keys)):
        raise BadRequest("You cannot remove your own admin access")
    changes: dict = {}
    if body.role_keys is not None:
        roles = list(db.scalars(select(Role).where(Role.key.in_(body.role_keys))))
        if len(roles) != len(set(body.role_keys)) or not roles:
            raise BadRequest("Unknown role")
        changes["roles"] = {"from": target.role_keys, "to": [r.key for r in roles]}
        target.roles = roles
    if body.is_active is not None and body.is_active != target.is_active:
        changes["is_active"] = body.is_active
        target.is_active = body.is_active
    if changes:
        audit.record(db, "user.updated", **audit.actor_fields(admin), details={"user_id": target.id, **changes})
    db.commit()
    return UserOut.of(target)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(_: User = Depends(can_users), db: Session = Depends(get_db)) -> list:
    return list(db.scalars(select(Role).order_by(Role.id)))


@router.get("/permissions")
def permissions(_: User = Depends(can_users)) -> dict:
    return PERMISSION_CATALOGUE


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(role_id: int, body: RoleUpdate, admin: User = Depends(can_users), db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("Role")
    unknown = [p for p in body.permissions if p not in PERMISSION_CATALOGUE]
    if unknown:
        raise BadRequest(f"Unknown permissions: {', '.join(unknown)}")
    if role.key == "trustshield_admin" and "users:manage" not in body.permissions:
        raise BadRequest("The admin role must keep users:manage")
    before = list(role.permissions or [])
    role.permissions = sorted(set(body.permissions))
    audit.record(db, "role.permissions_updated", **audit.actor_fields(admin),
                 details={"role": role.key, "added": sorted(set(role.permissions) - set(before)),
                          "removed": sorted(set(before) - set(role.permissions))})
    db.commit()
    return role


@router.get("/apps", response_model=list[AppOut])
def list_apps(_: User = Depends(can_apps), db: Session = Depends(get_db)) -> list:
    return list(db.scalars(select(ConnectedApp).order_by(ConnectedApp.id)))


@router.post("/apps", response_model=AppOut, status_code=201)
def create_app(body: AppCreate, admin: User = Depends(can_apps), db: Session = Depends(get_db)):
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")[:80]
    if db.scalar(select(ConnectedApp).where((ConnectedApp.slug == slug) | (ConnectedApp.name == body.name))):
        raise Conflict("An app with this name already exists")
    app = ConnectedApp(name=body.name, slug=slug, description=body.description, owner_team=body.owner_team)
    db.add(app)
    db.flush()
    audit.record(db, "app.created", **audit.actor_fields(admin), app_id=app.id, details={"name": app.name})
    db.commit()
    return app


@router.patch("/apps/{app_id}", response_model=AppOut)
def update_app(app_id: int, body: AppUpdate, admin: User = Depends(can_apps), db: Session = Depends(get_db)):
    app = db.get(ConnectedApp, app_id)
    if app is None:
        raise NotFound("App")
    if body.status:
        app.status = body.status
    if body.description is not None:
        app.description = body.description
    audit.record(db, "app.updated", **audit.actor_fields(admin), app_id=app.id, details=body.model_dump(exclude_none=True))
    db.commit()
    return app


@router.post("/apps/{app_id}/keys", response_model=ApiKeyCreated, status_code=201)
def create_key(app_id: int, body: ApiKeyCreate, admin: User = Depends(can_apps), db: Session = Depends(get_db)) -> dict:
    app = db.get(ConnectedApp, app_id)
    if app is None:
        raise NotFound("App")
    raw, prefix, digest = generate_api_key()
    key = ApiKey(app_id=app.id, name=body.name, prefix=prefix, key_hash=digest, created_by=admin.id)
    db.add(key)
    db.flush()
    audit.record(db, "api_key.created", **audit.actor_fields(admin), app_id=app.id, details={"key_id": key.id, "prefix": prefix})
    db.commit()
    db.refresh(key)
    return {**ApiKeyOut.model_validate(key).model_dump(), "key": raw}


@router.post("/apps/{app_id}/keys/{key_id}/revoke", status_code=204)
def revoke_key(app_id: int, key_id: int, admin: User = Depends(can_apps), db: Session = Depends(get_db)) -> None:
    key = db.get(ApiKey, key_id)
    if key is None or key.app_id != app_id:
        raise NotFound("API key")
    if key.revoked_at is None:
        key.revoked_at = utcnow()
        audit.record(db, "api_key.revoked", **audit.actor_fields(admin), app_id=app_id, details={"key_id": key.id, "prefix": key.prefix})
        db.commit()


@router.get("/settings")
def gateway_settings(_: User = Depends(can_settings)) -> dict:
    s = get_settings()
    provider = get_provider()
    return {
        "llm": {"configured_provider": s.llm_provider, "effective_provider": provider.name, "model": provider.model,
                "api_key_configured": bool(s.openai_api_key), "base_url_configured": bool(s.openai_base_url),
                "offline_mock": provider.name == "mock"},
        "embeddings": {"provider": get_embedder().name, "retrieval_top_k": s.retrieval_top_k,
                       "vector_store": "PostgreSQL JSON + in-process cosine (pgvector on roadmap)"},
        "pii": {"engine": get_pii_detector().engine_name, "spacy_model": s.spacy_model},
        "auth": {"access_token_minutes": s.access_token_minutes, "refresh_token_days": s.refresh_token_days,
                 "self_registration": s.allow_self_registration, "jwt_secret_is_default": s.jwt_secret == "change-me"},
        "thresholds_note": "Guardrail thresholds are policy rules — edit them in Policy Studio.",
    }
