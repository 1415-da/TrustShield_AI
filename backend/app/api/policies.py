"""Policy Studio API: families, immutable versions, approvals, activation, rollback, simulation, exceptions."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import BadRequest, NotFound
from app.guardrails.rules import PolicySnapshot
from app.guardrails.topics import TOPICS
from app.guardrails.types import MATCH_FIELDS, RULE_ACTIONS, RULE_TYPES
from app.models import Policy, PolicyException, PolicyVersion, User
from app.models.base import utcnow
from app.schemas.policy import (
    ActivateRequest, ApprovalOut, CommentIn, CommentOut, ExceptionIn, ExceptionOut, Note, PolicyAuditOut, PolicyCreate,
    PolicyDetail, PolicyDraftUpdate, PolicyOut, RollbackRequest, SimulateRequest, VersionOut,
)
from app.services import audit, policies, simulation

router = APIRouter(prefix="/admin", tags=["policies"])
can_read = require_permission("policies:read")
can_write = require_permission("policies:write")
can_approve = require_permission("policies:approve")

ENTITY_TYPES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "BANK_ACCOUNT", "IBAN_CODE", "US_SSN", "TEST_NATIONAL_ID",
                "EMPLOYEE_ID", "SALARY_AMOUNT", "CREDENTIAL", "PERSON", "IP_ADDRESS"]
PROFILES = ["general", "hr", "finance", "it_security"]


# --------------------------------------------------------------------------- serialisation
def _summary(p: Policy) -> dict:
    head = policies.head_version(p)
    d = head.snapshot if head else {}
    active = policies.active_version(p)
    working = policies.working_version(p)
    next_review = active.activated_at + timedelta(days=p.review_cadence_days) if active and active.activated_at else None
    return {
        "id": p.id, "name": p.name, "description": d.get("description", ""), "risk_category": p.risk_category,
        "owner": p.owner, "review_cadence_days": p.review_cadence_days, "status": policies.family_status(p),
        "action": d.get("action", "—"), "severity": d.get("severity", "MEDIUM"), "rules_count": len(d.get("rules") or []),
        "active_version": active.version if active else None, "latest_version": p.latest_version,
        "working_status": working.status if working else None,
        "pending_review": bool(working and working.status == "IN_REVIEW"), "next_review_at": next_review,
        "created_at": p.created_at, "updated_at": p.updated_at,
    }


def _detail(p: Policy) -> dict:
    active, working = policies.active_version(p), policies.working_version(p)
    return {**_summary(p), "active": active, "working": working, "versions": list(reversed(p.versions))}


def _approval(db: Session, a) -> dict:  # type: ignore[no-untyped-def]
    p = db.get(Policy, a.policy_id)
    v = db.get(PolicyVersion, a.version_id)
    return {**ApprovalOut.model_validate(a).model_dump(), "policy_name": p.name if p else None,
            "version": v.version if v else None, "risk_category": p.risk_category if p else None}


def _exception(db: Session, e: PolicyException) -> dict:
    p = db.get(Policy, e.policy_id)
    return {**ExceptionOut.model_validate(e).model_dump(), "policy_name": p.name if p else None,
            "is_expired": e.expires_at <= utcnow()}


# --------------------------------------------------------------------------- catalogue & list
@router.get("/policies", response_model=list[PolicyOut])
def list_policies(_: User = Depends(can_read), db: Session = Depends(get_db)) -> list[dict]:
    return [_summary(p) for p in policies.list_policies(db)]


@router.get("/policies/catalogue")
def catalogue(_: User = Depends(can_read)) -> dict:
    """Option lists for the Policy Studio rule builder."""
    return {"rule_types": RULE_TYPES, "match_fields": MATCH_FIELDS, "actions": RULE_ACTIONS,
            "severities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"], "topics": TOPICS, "entity_types": ENTITY_TYPES,
            "profiles": PROFILES}


@router.post("/policies", response_model=PolicyDetail, status_code=201)
def create_policy(body: PolicyCreate, user: User = Depends(can_write), db: Session = Depends(get_db)) -> dict:
    data = body.model_dump(exclude={"change_summary"})
    return _detail(policies.create_policy(db, data, user, body.change_summary))


@router.get("/policy-approvals", response_model=list[ApprovalOut])
def approval_inbox(status: str | None = Query("PENDING"), _: User = Depends(can_read), db: Session = Depends(get_db)) -> list[dict]:
    return [_approval(db, a) for a in policies.approvals(db, None if status in (None, "", "all") else status.upper())]


@router.post("/simulate")
def simulate_any(body: SimulateRequest, user: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    if not body.prompt.strip():
        raise BadRequest("Enter a prompt to simulate")
    focus = simulation.draft_snapshot(body.draft_policy.model_dump(mode="json")) if body.draft_policy else None
    result = simulation.simulate(db, prompt=body.prompt, role=body.role, include_output=body.include_output, focus=focus,
                                 profile=body.profile)
    audit.record(db, "simulation.run", **audit.actor_fields(user), commit=True,
                 details={"role": body.role, "input_action": result["final"]["input_action"], "draft_policy": bool(focus)})
    return result


# --------------------------------------------------------------------------- one policy
@router.get("/policies/{policy_id}", response_model=PolicyDetail)
def get_policy(policy_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    return _detail(policies.get_policy(db, policy_id))


@router.patch("/policies/{policy_id}", response_model=VersionOut)
def save_draft_compat(policy_id: int, body: PolicyDraftUpdate, user: User = Depends(can_write), db: Session = Depends(get_db)):
    """Alias of POST /versions: edits never change the active version."""
    data = body.model_dump(mode="json", exclude_unset=True)
    summary = data.pop("change_summary", "")
    return policies.save_draft(db, policies.get_policy(db, policy_id), data, user, summary)


@router.delete("/policies/{policy_id}", status_code=204)
def archive_policy(policy_id: int, user: User = Depends(can_write), db: Session = Depends(get_db)) -> None:
    policies.archive_policy(db, policies.get_policy(db, policy_id), user)


@router.get("/policies/{policy_id}/versions", response_model=list[VersionOut])
def list_versions(policy_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)) -> list:
    return list(reversed(policies.get_policy(db, policy_id, include_archived=True).versions))


@router.get("/policies/{policy_id}/versions/{version_id}")
def get_version(policy_id: int, version_id: int, compare_to: str | None = Query("active", description="active | previous | <version id>"),
                _: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    p = policies.get_policy(db, policy_id, include_archived=True)
    v = policies.get_version(db, p, version_id)
    base = None
    if compare_to == "active":
        base = policies.active_version(p)
        if base and base.id == v.id:
            base = db.get(PolicyVersion, v.based_on_version_id) if v.based_on_version_id else None
    elif compare_to == "previous":
        base = db.get(PolicyVersion, v.based_on_version_id) if v.based_on_version_id else None
    elif compare_to and compare_to.isdigit():
        base = policies.get_version(db, p, int(compare_to))
    approval = next(iter([a for a in policies.approvals(db, None) if a.version_id == v.id]), None)
    return {
        "version": VersionOut.model_validate(v).model_dump(mode="json"),
        "compared_to": VersionOut.model_validate(base).model_dump(mode="json") if base else None,
        "diff": policies.diff_definitions(base.snapshot if base else None, v.snapshot),
        "approval": _approval(db, approval) if approval else None,
    }


@router.post("/policies/{policy_id}/versions", response_model=VersionOut, status_code=201)
def save_draft(policy_id: int, body: PolicyDraftUpdate, user: User = Depends(can_write), db: Session = Depends(get_db)):
    data = body.model_dump(mode="json", exclude_unset=True)
    summary = data.pop("change_summary", "")
    return policies.save_draft(db, policies.get_policy(db, policy_id), data, user, summary)


@router.post("/policies/{policy_id}/submit-for-review", response_model=ApprovalOut)
def submit(policy_id: int, body: Note, user: User = Depends(can_write), db: Session = Depends(get_db)) -> dict:
    return _approval(db, policies.submit_for_review(db, policies.get_policy(db, policy_id), user, body.note))


@router.post("/policies/{policy_id}/approve", response_model=VersionOut)
def approve(policy_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)):
    return policies.decide(db, policies.get_policy(db, policy_id), user, "APPROVED", body.note)


@router.post("/policies/{policy_id}/request-changes", response_model=VersionOut)
def request_changes(policy_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)):
    return policies.decide(db, policies.get_policy(db, policy_id), user, "CHANGES_REQUESTED", body.note)


@router.post("/policies/{policy_id}/reject", response_model=VersionOut)
def reject(policy_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)):
    return policies.decide(db, policies.get_policy(db, policy_id), user, "REJECTED", body.note)


@router.post("/policies/{policy_id}/activate", response_model=VersionOut)
def activate(policy_id: int, body: ActivateRequest | None = None, user: User = Depends(can_write), db: Session = Depends(get_db)):
    body = body or ActivateRequest()
    return policies.activate(db, policies.get_policy(db, policy_id), user, body.version_id, body.note)


@router.post("/policies/{policy_id}/deactivate", response_model=VersionOut)
def deactivate(policy_id: int, body: Note | None = None, user: User = Depends(can_write), db: Session = Depends(get_db)):
    return policies.deactivate(db, policies.get_policy(db, policy_id), user, (body or Note()).note)


@router.post("/policies/{policy_id}/rollback", response_model=VersionOut, status_code=201)
def rollback(policy_id: int, body: RollbackRequest, user: User = Depends(can_write), db: Session = Depends(get_db)):
    return policies.rollback(db, policies.get_policy(db, policy_id), user, body.version_id, body.note, body.activate)


@router.post("/policies/{policy_id}/simulate")
def simulate_policy(policy_id: int, body: SimulateRequest, user: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    """Simulate with a specific version forced active (default: the working draft, else the active version)."""
    p = policies.get_policy(db, policy_id)
    v = policies.get_version(db, p, body.version_id) if body.version_id else (policies.working_version(p) or policies.active_version(p))
    if v is None:
        raise NotFound("Policy version")
    focus = PolicySnapshot.from_version(v)
    if body.suite:
        result = {"version": v.version, "impact": simulation.impact_analysis(db, focus)}
        approval = policies.pending_approval(db, v)
        if approval:
            approval.impact = result["impact"]
    else:
        if not body.prompt.strip():
            raise BadRequest("Enter a prompt to simulate")
        result = simulation.simulate(db, prompt=body.prompt, role=body.role, include_output=body.include_output,
                                     focus=focus, profile=body.profile)
    audit.record(db, "simulation.run", **audit.actor_fields(user), policy_ids=[p.id], commit=True,
                 details={"version": v.version, "status": v.status, "suite": body.suite, "role": body.role})
    return result


@router.get("/policies/{policy_id}/audit-history", response_model=list[PolicyAuditOut])
def audit_history(policy_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)) -> list:
    policies.get_policy(db, policy_id, include_archived=True)
    return policies.audit_history(db, policy_id)


@router.get("/policies/{policy_id}/comments", response_model=list[CommentOut])
def list_comments(policy_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)) -> list:
    return policies.comments(db, policy_id)


@router.post("/policies/{policy_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(policy_id: int, body: CommentIn, user: User = Depends(can_read), db: Session = Depends(get_db)):
    if not (user.has("policies:write") or user.has("policies:approve")):
        raise BadRequest("Only policy authors and approvers can comment")
    return policies.add_comment(db, policies.get_policy(db, policy_id), user, body.body, body.version_id)


# --------------------------------------------------------------------------- exceptions
@router.get("/policy-exceptions", response_model=list[ExceptionOut])
def list_exceptions(_: User = Depends(can_read), db: Session = Depends(get_db)) -> list[dict]:
    return [_exception(db, e) for e in policies.list_exceptions(db)]


@router.post("/policy-exceptions", response_model=ExceptionOut, status_code=201)
def request_exception(body: ExceptionIn, user: User = Depends(can_write), db: Session = Depends(get_db)) -> dict:
    p = policies.get_policy(db, body.policy_id)
    return _exception(db, policies.request_exception(db, p, user, body.model_dump()))


def _get_exception(db: Session, exception_id: int) -> PolicyException:
    e = db.get(PolicyException, exception_id)
    if e is None:
        raise NotFound("Exception")
    return e


@router.post("/policy-exceptions/{exception_id}/approve", response_model=ExceptionOut)
def approve_exception(exception_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)) -> dict:
    return _exception(db, policies.decide_exception(db, _get_exception(db, exception_id), user, "APPROVED", body.note))


@router.post("/policy-exceptions/{exception_id}/reject", response_model=ExceptionOut)
def reject_exception(exception_id: int, body: Note, user: User = Depends(can_approve), db: Session = Depends(get_db)) -> dict:
    return _exception(db, policies.decide_exception(db, _get_exception(db, exception_id), user, "REJECTED", body.note))


@router.post("/policy-exceptions/{exception_id}/revoke", response_model=ExceptionOut)
def revoke_exception(exception_id: int, body: Note, user: User = Depends(can_write), db: Session = Depends(get_db)) -> dict:
    return _exception(db, policies.decide_exception(db, _get_exception(db, exception_id), user, "REVOKED", body.note))
