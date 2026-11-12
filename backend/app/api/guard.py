"""Guard API: TrustShield as a guardrail service in front of your own LLM stack.

    your app ──► POST /api/v1/guard/input  ──► (ALLOW / REDACT: call your model with `sanitized_text`)
             ──► POST /api/v1/guard/output ──► (SHOW / REDACT: show `sanitized_text`; otherwise don't)

Authenticated with a connected-app key (`X-TrustShield-App-Key`), no user session needed. The organization's live
policies apply, every call is written to its hash-chained audit log, and raw sensitive values are never returned.
"""

from __future__ import annotations

import dataclasses
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import sha256_hex
from app.core.tenancy import ALL_ORGS, localize, use_org
from app.guardrails.pii import get_pii_detector
from app.guardrails.pipeline import ContextItem, GuardrailEngine
from app.guardrails.types import InputAction, StageResult
from app.models import ApiKey, ConnectedApp, Role
from app.models.base import utcnow
from app.services import audit, directory, policies
from app.services.evaluation import actor_for_role
from app.services.gateway import ESCALATION_MESSAGE, OUTPUT_BLOCK_MESSAGE, REVIEW_HOLDING_MESSAGE, _block_text

router = APIRouter(prefix="/v1/guard", tags=["guard api"])


def app_from_key(x_trustshield_app_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> ConnectedApp:
    if not x_trustshield_app_key:
        raise HTTPException(status_code=401, detail="Send your app key in the X-TrustShield-App-Key header")
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == sha256_hex(x_trustshield_app_key)).execution_options(**ALL_ORGS))
    if key is None or key.revoked_at is not None or key.app.status != "active":
        raise HTTPException(status_code=401, detail="Invalid or revoked app key")
    use_org(db, key.organization_id)
    key.last_used_at = utcnow()
    return key.app


class Subject(BaseModel):
    role: str = Field(default="employee", max_length=64, description="TrustShield role whose data scopes apply")
    email: str | None = Field(default=None, max_length=255, description="Lets approved policy exceptions apply")
    department: str = Field(default="", max_length=120)
    profile: str | None = Field(default=None, max_length=40, description="Channel policy profile, e.g. finance")


class InputCheck(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    subject: Subject = Field(default_factory=Subject)


class OutputCheck(BaseModel):
    text: str = Field(min_length=1, max_length=16000, description="The model's draft answer")
    prompt: str = Field(default="", max_length=8000, description="The (sanitized) prompt the answer responds to")
    context: list[str] = Field(default_factory=list, max_length=20, description="Passages the model was given")
    subject: Subject = Field(default_factory=Subject)


def _engine(db: Session, subject: Subject, *, grounding: bool) -> tuple[GuardrailEngine, object]:
    if not db.scalar(select(Role.id).where(Role.key == subject.role)):
        raise HTTPException(status_code=422, detail=f"Unknown role '{subject.role}'")
    actor = dataclasses.replace(actor_for_role(db, subject.role), email=subject.email or f"api+{subject.role}@guard",
                                department=subject.department, profile=subject.profile)
    snaps = policies.active_snapshots(db)
    exempt = policies.exempt_policy_ids(db, email=actor.email, roles=actor.roles, department=actor.department)
    snaps = [s for s in snaps if s.id not in exempt]
    if not grounding:  # no evidence supplied, so confidence-threshold rules can't be evaluated meaningfully
        snaps = [dataclasses.replace(s, rules=tuple(r for r in s.rules if r.rule_type != "confidence_threshold")) for s in snaps]
        snaps = [s for s in snaps if s.rules]
    return GuardrailEngine(snaps, get_pii_detector(), directory.directory_names(db)), actor


def _matches(st: StageResult) -> list[dict]:
    return [{"policy": m.policy_name, "policy_version": m.policy_version, "rule": m.rule_name, "action": m.action,
             "severity": m.severity, "category": m.risk_category} for m in st.matches]


def _record(db: Session, app: ConnectedApp, kind: str, subject: Subject, text: str, st: StageResult, request_id: str) -> None:
    audit.record(db, f"api.guard_{kind}", request_id=request_id, app_id=app.id, actor_email=subject.email,
                 actor_role=subject.role, content_hash=sha256_hex(text), policy_ids=sorted({m.policy_id for m in st.matches}),
                 input_risk_score=st.risk_score if kind == "input" else None,
                 output_risk_score=st.risk_score if kind == "output" else None,
                 input_action=st.action if kind == "input" else None, output_action=st.action if kind == "output" else None,
                 final_action=st.action, redaction_count=st.redaction_count,
                 details={"redacted_entity_types": st.redacted_entity_types, "profile": subject.profile}, commit=True)


@router.post("/input")
def check_input(body: InputCheck, app: ConnectedApp = Depends(app_from_key), db: Session = Depends(get_db)) -> dict:
    """Check a user's prompt before it reaches your model."""
    engine, actor = _engine(db, body.subject, grounding=False)
    out = engine.run_input(body.text, actor)  # type: ignore[arg-type]
    action = InputAction(out.stage.action)
    message = None
    if action == InputAction.BLOCK:
        message = _block_text(out.stage.matches)
    elif action == InputAction.ESCALATE:
        message = ESCALATION_MESSAGE
    elif action == InputAction.REVIEW:
        message = REVIEW_HOLDING_MESSAGE
    request_id = uuid.uuid4().hex
    _record(db, app, "input", body.subject, body.text, out.stage, request_id)
    return {
        "request_id": request_id,
        "decision": action.value,
        "allow_model_call": action in (InputAction.ALLOW, InputAction.REDACT, InputAction.REVIEW),
        "hold_answer_for_review": action == InputAction.REVIEW,
        "sanitized_text": out.sanitized_prompt,
        "risk_score": round(out.stage.risk_score, 3),
        "redacted_entity_types": out.stage.redacted_entity_types,
        "matches": _matches(out.stage),
        "user_message": localize(db, message),
    }


@router.post("/output")
def check_output(body: OutputCheck, app: ConnectedApp = Depends(app_from_key), db: Session = Depends(get_db)) -> dict:
    """Check your model's answer before a person sees it."""
    engine, actor = _engine(db, body.subject, grounding=bool(body.context))
    items = [ContextItem(index=i + 1, title=f"Passage {i + 1}", text=t, score=0.5) for i, t in enumerate(body.context)]
    out = engine.run_output(body.text, query=body.prompt or body.text, context=items, actor=actor,  # type: ignore[arg-type]
                            input_action=InputAction.ALLOW, input_risk=0.0)
    action = out.stage.action
    message = {"BLOCK": OUTPUT_BLOCK_MESSAGE, "SEND_TO_REVIEW": REVIEW_HOLDING_MESSAGE}.get(action)
    request_id = uuid.uuid4().hex
    _record(db, app, "output", body.subject, body.text, out.stage, request_id)
    return {
        "request_id": request_id,
        "decision": action,
        "show_to_user": action in ("SHOW", "SHOW_WITH_WARNING", "REDACT"),
        "sanitized_text": out.final_text if action != "BLOCK" else None,
        "risk_score": round(out.stage.risk_score, 3),
        "confidence": round(out.grounding.confidence, 3) if body.context else None,
        "redacted_entity_types": out.stage.redacted_entity_types,
        "matches": _matches(out.stage),
        "user_message": localize(db, message),
    }

