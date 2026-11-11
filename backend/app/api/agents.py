"""Agent action-approval controls API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.models import ActionPolicy, ActionType, Agent, AgentAction, User
from app.models.agents import ACTION_CATEGORIES, ACTION_DECISIONS
from app.services import agent_actions as svc
from app.services import audit

router = APIRouter(tags=["agent actions"])
can_request = require_permission("actions:request")
can_approve = require_permission("actions:approve")
can_read_admin = require_permission("agents:read")
can_manage = require_permission("agents:manage")


class ActionRequest(BaseModel):
    request: str | None = Field(default=None, max_length=2000, description="Natural-language request, e.g. 'Issue a refund for INV-2291'")
    action_type: str | None = None
    params: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)
    conversation_id: int | None = None
    record_in_conversation: bool = False


class Note(BaseModel):
    note: str = Field(default="", max_length=2000)


def _visible(user: User, a: AgentAction) -> AgentAction:
    if not svc.can_view(user, a):
        raise NotFound("Action")
    return a


@router.post("/agent/actions", status_code=201)
def create_action(body: ActionRequest, user: User = Depends(can_request), db: Session = Depends(get_db),
                  idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict:
    action, created = svc.request_action(db, user, text=body.request, action_type=body.action_type, params=body.params,
                                         idempotency_key=body.idempotency_key or idempotency_key, conversation_id=body.conversation_id,
                                         record_in_conversation=body.record_in_conversation)
    return {**svc.action_out(db, action, detail=True), "idempotent_replay": not created}


@router.get("/agent/actions")
def list_actions(scope: Literal["mine", "approvals"] = "mine", user: User = Depends(can_request), db: Session = Depends(get_db)) -> list[dict]:
    if scope == "approvals":
        if not user.has("actions:approve"):
            raise Forbidden("Missing permission: actions:approve")
        rows = db.scalars(select(AgentAction).where(AgentAction.status.in_(("PENDING_APPROVAL", "IN_REVIEW", "ESCALATED")),
                                                    AgentAction.required_approver_role.in_(user.role_keys),
                                                    AgentAction.requested_by != user.id).order_by(AgentAction.id.desc()))
    else:
        rows = db.scalars(select(AgentAction).where(AgentAction.requested_by == user.id).order_by(AgentAction.id.desc()).limit(100))
    return [svc.action_out(db, a) for a in rows]


@router.get("/agent/actions/{action_id}")
def get_action(action_id: int, user: User = Depends(can_request), db: Session = Depends(get_db)) -> dict:
    return svc.action_out(db, _visible(user, svc.get_action(db, action_id)), detail=True)


@router.post("/agent/actions/{action_id}/approve")
def approve(action_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)) -> dict:
    return svc.action_out(db, svc.approve(db, svc.get_action(db, action_id), user, body.note), detail=True)


@router.post("/agent/actions/{action_id}/reject")
def reject(action_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)) -> dict:
    return svc.action_out(db, svc.reject(db, svc.get_action(db, action_id), user, body.note), detail=True)


@router.post("/agent/actions/{action_id}/request-info")
def request_info(action_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)) -> dict:
    return svc.action_out(db, svc.request_info(db, svc.get_action(db, action_id), user, body.note), detail=True)


@router.post("/agent/actions/{action_id}/escalate")
def escalate(action_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)) -> dict:
    return svc.action_out(db, svc.escalate(db, svc.get_action(db, action_id), user, body.note), detail=True)


@router.post("/agent/actions/{action_id}/execute")
def execute(action_id: int, user: User = Depends(can_request), db: Session = Depends(get_db)) -> dict:
    """Run (or retry) an approved action. Only the requester or an agent administrator may trigger it."""
    a = _visible(user, svc.get_action(db, action_id))
    if a.requested_by != user.id and not user.has("agents:manage"):
        raise Forbidden("Only the requester or an agent administrator can run this action")
    return svc.action_out(db, svc.execute(db, a, user), detail=True)


@router.post("/agent/actions/{action_id}/compensate")
def compensate(action_id: int, body: Note, user: User = Depends(can_manage), db: Session = Depends(get_db)) -> dict:
    return svc.action_out(db, svc.compensate(db, svc.get_action(db, action_id), user, body.note), detail=True)


# --------------------------------------------------------------------------- admin
@router.get("/admin/agent/actions")
def admin_actions(status: str | None = None, category: str | None = None, limit: int = Query(200, ge=1, le=500),
                  _: User = Depends(can_read_admin), db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(AgentAction).order_by(AgentAction.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(AgentAction.status == status.upper())
    if category:
        stmt = stmt.where(AgentAction.category == category.upper())
    return [svc.action_out(db, a) for a in db.scalars(stmt)]


@router.get("/admin/agent/actions/{action_id}/audit")
def action_audit(action_id: int, _: User = Depends(can_read_admin), db: Session = Depends(get_db)) -> list[dict]:
    svc.get_action(db, action_id)
    return svc.audit_trail(db, action_id)


@router.get("/admin/agent/summary")
def summary(_: User = Depends(can_read_admin), db: Session = Depends(get_db)) -> dict:
    by_status = dict(db.execute(select(AgentAction.status, func.count()).group_by(AgentAction.status)).all())
    by_category = dict(db.execute(select(AgentAction.category, func.count()).group_by(AgentAction.category)).all())
    return {"by_status": by_status, "by_category": {k or "UNCLASSIFIED": v for k, v in by_category.items()},
            "total": sum(by_status.values())}


@router.get("/admin/agent/catalog")
def catalog(_: User = Depends(can_read_admin), db: Session = Depends(get_db)) -> dict:
    return {
        "agents": [{"id": a.id, "key": a.key, "name": a.name, "description": a.description, "owner_team": a.owner_team, "status": a.status,
                    "allowed_action_types": a.allowed_action_types} for a in db.scalars(select(Agent).order_by(Agent.id))],
        "action_types": [{"id": t.id, "key": t.key, "name": t.name, "category": t.category, "description": t.description,
                          "target_system": t.target_system, "executor": t.executor, "required_permission": t.required_permission,
                          "is_enabled": t.is_enabled} for t in db.scalars(select(ActionType).order_by(ActionType.category, ActionType.key))],
        "categories": ACTION_CATEGORIES, "decisions": ACTION_DECISIONS,
    }


class PolicyIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = ""
    action_type: str | None = None
    category: Literal[ACTION_CATEGORIES] | None = None  # type: ignore[valid-type]
    conditions: dict[str, Any] = {}
    decision: Literal[ACTION_DECISIONS]  # type: ignore[valid-type]
    approver_role: str | None = None
    priority: int = Field(default=20, ge=0, le=100)
    is_active: bool = True


class PolicyPatch(BaseModel):
    description: str | None = None
    conditions: dict[str, Any] | None = None
    decision: Literal[ACTION_DECISIONS] | None = None  # type: ignore[valid-type]
    approver_role: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


ALLOWED_CONDITIONS = {"amount_gt", "amount_gte", "amount_lt", "amount_lte", "requester_roles", "external"}


def _policy_out(p: ActionPolicy) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description, "action_type": p.action_type, "category": p.category,
            "conditions": p.conditions, "decision": p.decision, "approver_role": p.approver_role, "priority": p.priority,
            "is_active": p.is_active, "created_by_email": p.created_by_email, "updated_at": p.updated_at.isoformat() + "Z"}


def _validate(db: Session, body: PolicyIn | PolicyPatch, action_type: str | None, category: str | None) -> None:
    if getattr(body, "conditions", None) and set(body.conditions) - ALLOWED_CONDITIONS:
        raise BadRequest(f"Unknown conditions: {', '.join(sorted(set(body.conditions) - ALLOWED_CONDITIONS))}")
    if action_type and not db.scalar(select(ActionType).where(ActionType.key == action_type)):
        raise BadRequest(f"Unknown action type '{action_type}'")
    if isinstance(body, PolicyIn) and not (action_type or category):
        raise BadRequest("Scope the policy to an action type or a category")
    if body.decision in ("REQUIRE_APPROVAL", "SEND_TO_REVIEW") and body.approver_role is None and isinstance(body, PolicyIn):
        raise BadRequest("Approval policies need an approver role")


@router.get("/admin/agent/action-policies")
def list_policies(_: User = Depends(can_read_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [_policy_out(p) for p in db.scalars(select(ActionPolicy).order_by(ActionPolicy.priority.desc(), ActionPolicy.name))]


@router.post("/admin/agent/action-policies", status_code=201)
def create_policy(body: PolicyIn, user: User = Depends(can_manage), db: Session = Depends(get_db)) -> dict:
    _validate(db, body, body.action_type, body.category)
    if db.scalar(select(ActionPolicy).where(ActionPolicy.name == body.name)):
        raise Conflict("An action policy with this name exists")
    p = ActionPolicy(**body.model_dump(), created_by_email=user.email)
    db.add(p)
    db.flush()
    audit.record(db, "agent_policy.created", **audit.actor_fields(user), details={"policy_id": p.id, **body.model_dump()}, commit=True)
    return _policy_out(p)


@router.patch("/admin/agent/action-policies/{policy_id}")
def update_policy(policy_id: int, body: PolicyPatch, user: User = Depends(can_manage), db: Session = Depends(get_db)) -> dict:
    p = db.get(ActionPolicy, policy_id)
    if p is None:
        raise NotFound("Action policy")
    _validate(db, body, p.action_type, p.category)
    changes = body.model_dump(exclude_unset=True)
    before = {k: getattr(p, k) for k in changes}
    for k, v in changes.items():
        setattr(p, k, v)
    audit.record(db, "agent_policy.updated", **audit.actor_fields(user), details={"policy_id": p.id, "before": before, "after": changes}, commit=True)
    return _policy_out(p)
