from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import NotFound
from app.models import AuditEvent, GuardrailDecision, User
from app.schemas.misc import AuditEventOut, AuditPage
from app.services import analytics, audit

router = APIRouter(prefix="/admin", tags=["analytics", "audit"])
can_analytics = require_permission("analytics:read")
can_audit = require_permission("audit:read")


@router.get("/analytics/overview")
def overview(days: int = Query(14, ge=1, le=90), _: User = Depends(can_analytics), db: Session = Depends(get_db)) -> dict:
    return analytics.overview(db, days)


@router.get("/analytics/guardrails")
def guardrails(days: int = Query(14, ge=1, le=90), _: User = Depends(can_analytics), db: Session = Depends(get_db)) -> dict:
    return analytics.guardrail_stats(db, days)


@router.get("/analytics/reviews")
def review_analytics(_: User = Depends(can_analytics), db: Session = Depends(get_db)) -> dict:
    return analytics.review_stats(db)


@router.get("/audit-events", response_model=AuditPage)
def audit_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: str | None = None,
    action: str | None = None,
    actor: str | None = Query(None, max_length=200),
    request_id: str | None = None,
    since: datetime | None = None,
    _: User = Depends(can_audit),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(AuditEvent)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type.like(f"{event_type}%"))
    if action:
        stmt = stmt.where(or_(AuditEvent.final_action == action, AuditEvent.input_action == action))
    if actor:
        stmt = stmt.where(AuditEvent.actor_email.ilike(f"%{actor}%"))
    if request_id:
        stmt = stmt.where(AuditEvent.request_id == request_id)
    if since:
        stmt = stmt.where(AuditEvent.created_at >= since.replace(tzinfo=None))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(AuditEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit-events/verify")
def verify(_: User = Depends(can_audit), db: Session = Depends(get_db)) -> dict:
    return audit.verify_chain(db)


@router.get("/audit-events/{event_id}")
def audit_event(event_id: int, _: User = Depends(can_audit), db: Session = Depends(get_db)) -> dict:
    ev = db.get(AuditEvent, event_id)
    if ev is None:
        raise NotFound("Audit event")
    decisions = []
    if ev.request_id:
        for d in db.scalars(select(GuardrailDecision).where(GuardrailDecision.request_id == ev.request_id).order_by(GuardrailDecision.id)):
            decisions.append({"stage": d.stage, "action": d.action, "risk_score": d.risk_score, "matches": d.matches,
                              "signals": d.signals, "redaction_count": d.redaction_count, "latency_ms": d.latency_ms})
    return {"event": AuditEventOut.model_validate(ev).model_dump(mode="json"), "guardrail_decisions": decisions}
