"""Organization workspaces (self-service signup, profile, onboarding) and the public guardrail playground."""

from __future__ import annotations

import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.ratelimit import client_key, limiter as shared_limiter
from app.core.deps import get_current_user, require_permission
from app.core.security import sha256_hex
from app.core.tenancy import current_org, use_org
from app.models import AuditEvent, Organization, User
from app.models.base import utcnow
from app.models.organization import DEFAULT_ORG_ID
from app.schemas.auth import LoginResponse, UserOut
from app.services import audit, organizations, simulation

router = APIRouter(tags=["organizations"])

EMAIL = r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"


class SignupRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(pattern=EMAIL, max_length=255)
    password: str = Field(min_length=10, max_length=200)
    industry: str = Field(default="", max_length=80)
    size: str = Field(default="", max_length=40)


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    industry: str | None = Field(default=None, max_length=80)
    size: str | None = Field(default=None, max_length=40)


class InviteRequest(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=255)
    full_name: str = Field(min_length=2, max_length=200)
    role_keys: list[str] = Field(default_factory=lambda: ["employee"], max_length=5)
    department: str = Field(default="General Operations", max_length=120)
    temporary_password: str = Field(min_length=10, max_length=200)


class PlaygroundRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    role: str = Field(default="employee", pattern=r"^(employee|hr_manager|finance_analyst)$")


limiter = shared_limiter  # re-exported for tests
_client = client_key


# --------------------------------------------------------------------------- workspaces
@router.post("/orgs/signup", response_model=LoginResponse, status_code=201)
def signup(body: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """Create an organization workspace and its first admin, then sign them in."""
    if not limiter.allow(f"signup:{_client(request)}", limit=20, window=3600):
        raise AppError(429, "RATE_LIMITED", "Too many workspaces created from this network. Please try again later.")
    from app.api.auth import sign_in

    _org, admin = organizations.create_organization(
        db, name=body.organization_name, full_name=body.full_name, email=body.email, password=body.password,
        industry=body.industry, size=body.size)
    result = sign_in(db, admin, request, response)
    db.commit()
    return result


@router.get("/orgs/current")
def current(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return organizations.summary(db, current_org(db))


@router.patch("/orgs/current")
def update_current(body: OrgUpdate, user: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)) -> dict:
    org = current_org(db)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(org, k, v.strip() if isinstance(v, str) else v)
    if changes:
        audit.record(db, "organization.updated", **audit.actor_fields(user), details={"fields": sorted(changes)})
    db.commit()
    db.info.pop("org", None)
    return organizations.summary(db, org)


@router.post("/admin/users", response_model=UserOut, status_code=201)
def invite(body: InviteRequest, admin: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)) -> UserOut:
    """Add a colleague to this workspace with a temporary password they should change after signing in."""
    user = organizations.invite_user(db, admin, email=body.email, full_name=body.full_name, role_keys=body.role_keys,
                                     password=body.temporary_password, department=body.department)
    return UserOut.of(user)


# --------------------------------------------------------------------------- public live demo
def _public_stage(st: dict | None) -> dict | None:
    if st is None:
        return None
    return {"stage": st["stage"], "action": st["action"], "risk_score": round(st["risk_score"], 3),
            "latency_ms": st["latency_ms"], "redacted_entity_types": st["redacted_entity_types"],
            "matches": [{"policy_name": m["policy_name"], "rule_name": m["rule_name"], "action": m["action"],
                         "severity": m["severity"], "risk_category": m["risk_category"]} for m in st["matches"]]}


@router.post("/public/playground")
def playground(body: PlaygroundRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    """Run a prompt through the live NovaCorp workspace's guardrails as a chosen role. Nothing is stored except an
    audit event with a hash of the prompt; the response never contains raw sensitive values."""
    if not limiter.allow(f"playground:{_client(request)}", limit=30, window=60):
        raise HTTPException(status_code=429, detail="You're sending prompts quickly. Wait a moment and try again.")
    use_org(db, DEFAULT_ORG_ID)
    t0 = time.perf_counter()
    r = simulation.simulate(db, prompt=body.prompt, role=body.role)
    final = r["final"]
    audit.record(db, "playground.scan", actor_role=body.role, content_hash=sha256_hex(body.prompt),
                 input_action=final["input_action"], output_action=final["output_action"],
                 details={"trust_status": final["trust_status"], "llm_called": final["llm_called"]}, commit=True)
    return {
        "role": body.role,
        "decision": final["input_action"],
        "output_decision": final["output_action"],
        "trust_status": final["trust_status"],
        "llm_called": final["llm_called"],
        "sanitized_prompt": r["sanitized_prompt"],
        "response": final["response_preview"],
        "explanation": final["explanation"],
        "citations": [{"title": c.get("title"), "heading": c.get("heading"), "snippet": c.get("snippet")}
                      for c in final.get("citations") or []],
        "stages": [s for s in (_public_stage(r["input"]), _public_stage(r["context"]), _public_stage(r["output"])) if s],
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


@router.get("/public/stats")
def public_stats(db: Session = Depends(get_db)) -> dict:
    """Live decision counts from the NovaCorp workspace over the last 30 days (aggregates only)."""
    use_org(db, DEFAULT_ORG_ID)
    since = utcnow() - timedelta(days=30)
    rows = db.execute(select(AuditEvent.input_action, func.count()).where(
        AuditEvent.event_type.like("%.request"), AuditEvent.created_at >= since).group_by(AuditEvent.input_action)).all()
    by = {k: v for k, v in rows if k}
    workspaces = db.scalar(select(func.count(Organization.id))) or 0
    return {"window_days": 30, "requests": sum(by.values()), "by_decision": by, "workspaces": workspaces}
