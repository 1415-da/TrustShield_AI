from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.guardrails.rules import PolicySnapshot
from app.guardrails.topics import TOPICS
from app.guardrails.types import MATCH_FIELDS, RULE_ACTIONS, RULE_TYPES
from app.models import User
from app.schemas.policy import PolicyCreate, PolicyOut, PolicyUpdate, PolicyVersionOut, SimulateRequest
from app.services import audit, policies, simulation

router = APIRouter(prefix="/admin", tags=["policies"])
can_read = require_permission("policies:read")
can_write = require_permission("policies:write")

ENTITY_TYPES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "BANK_ACCOUNT", "IBAN_CODE", "US_SSN", "TEST_NATIONAL_ID",
                "EMPLOYEE_ID", "SALARY_AMOUNT", "CREDENTIAL", "PERSON", "IP_ADDRESS"]


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(_: User = Depends(can_read), db: Session = Depends(get_db)) -> list:
    return policies.list_policies(db)


@router.get("/policies/catalogue")
def catalogue(_: User = Depends(can_read)) -> dict:
    """Option lists for the Policy Studio rule builder."""
    return {"rule_types": RULE_TYPES, "match_fields": MATCH_FIELDS, "actions": RULE_ACTIONS,
            "severities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"], "topics": TOPICS, "entity_types": ENTITY_TYPES}


@router.post("/policies", response_model=PolicyOut, status_code=201)
def create_policy(body: PolicyCreate, user: User = Depends(can_write), db: Session = Depends(get_db)):
    return policies.create_policy(db, body.model_dump(), user)


@router.post("/simulate")
def simulate_any(body: SimulateRequest, user: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    focus = simulation.draft_snapshot(body.draft_policy.model_dump()) if body.draft_policy else None
    result = simulation.simulate(db, prompt=body.prompt, role=body.role, include_output=body.include_output, focus=focus)
    audit.record(db, "simulation.run", **audit.actor_fields(user), commit=True,
                 details={"role": body.role, "input_action": result["final"]["input_action"], "draft_policy": bool(focus)})
    return result


@router.get("/policies/{policy_id}", response_model=PolicyOut)
def get_policy(policy_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)):
    return policies.get_policy(db, policy_id)


@router.get("/policies/{policy_id}/versions", response_model=list[PolicyVersionOut])
def policy_versions(policy_id: int, _: User = Depends(can_read), db: Session = Depends(get_db)) -> list:
    policies.get_policy(db, policy_id)
    return policies.versions(db, policy_id)


@router.patch("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: int, body: PolicyUpdate, user: User = Depends(can_write), db: Session = Depends(get_db)):
    policy = policies.get_policy(db, policy_id)
    data = body.model_dump(exclude_unset=True)
    summary = data.pop("change_summary", "")
    return policies.update_policy(db, policy, data, user, summary)


@router.delete("/policies/{policy_id}", status_code=204)
def delete_policy(policy_id: int, user: User = Depends(can_write), db: Session = Depends(get_db)) -> None:
    policies.archive_policy(db, policies.get_policy(db, policy_id), user)


@router.post("/policies/{policy_id}/activate", response_model=PolicyOut)
def activate(policy_id: int, user: User = Depends(can_write), db: Session = Depends(get_db)):
    return policies.set_active(db, policies.get_policy(db, policy_id), True, user)


@router.post("/policies/{policy_id}/deactivate", response_model=PolicyOut)
def deactivate(policy_id: int, user: User = Depends(can_write), db: Session = Depends(get_db)):
    return policies.set_active(db, policies.get_policy(db, policy_id), False, user)


@router.post("/policies/{policy_id}/simulate")
def simulate_policy(policy_id: int, body: SimulateRequest, user: User = Depends(can_read), db: Session = Depends(get_db)) -> dict:
    """Simulate with this policy forced active (so drafts can be tested before activation)."""
    focus = PolicySnapshot.from_model(policies.get_policy(db, policy_id))
    result = simulation.simulate(db, prompt=body.prompt, role=body.role, include_output=body.include_output, focus=focus)
    audit.record(db, "simulation.run", **audit.actor_fields(user), policy_ids=[policy_id], commit=True,
                 details={"role": body.role, "input_action": result["final"]["input_action"],
                          "focus_triggered": result["focus_policy"]["triggered"]})
    return result
