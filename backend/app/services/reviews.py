"""Human-in-the-loop review actions. Every action is recorded as a ReviewAction and an audit event."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import case as sa_case
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.guardrails.decision import SLA_HOURS
from app.guardrails.pii import get_pii_detector
from app.guardrails.types import STORAGE_MASKED_ENTITIES
from app.models import Message, ReviewAction, ReviewCase, User
from app.models.base import utcnow
from app.services import audit, gateway

OPEN_STATUSES = ("PENDING", "ESCALATED")

# Overridable clock so the seed script can back-date review history; production uses wall time.
clock = utcnow
PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def list_cases(db: Session, *, status: str | None = None, priority: str | None = None, origin: str | None = None,
               q: str | None = None, limit: int = 200) -> list[ReviewCase]:
    stmt = select(ReviewCase)
    if status == "open":
        stmt = stmt.where(ReviewCase.status.in_(OPEN_STATUSES))
    elif status == "resolved":
        stmt = stmt.where(ReviewCase.status.not_in(OPEN_STATUSES))
    elif status:
        stmt = stmt.where(ReviewCase.status == status.upper())
    if priority:
        stmt = stmt.where(ReviewCase.priority == priority.upper())
    if origin:
        stmt = stmt.where(ReviewCase.origin == origin)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(ReviewCase.prompt_masked.ilike(like), ReviewCase.reason.ilike(like)))
    rank = sa_case(*[(ReviewCase.priority == k, v) for k, v in PRIORITY_RANK.items()], else_=9)
    open_first = sa_case((ReviewCase.status.in_(OPEN_STATUSES), 0), else_=1)
    stmt = stmt.order_by(open_first, rank, ReviewCase.sla_due_at).limit(limit)
    return list(db.scalars(stmt))


def get_case(db: Session, case_id: int) -> ReviewCase:
    c = db.get(ReviewCase, case_id)
    if c is None:
        raise NotFound("Review case")
    return c


def _require_open(c: ReviewCase) -> None:
    if c.status not in OPEN_STATUSES:
        raise Conflict(f"Case is already {c.status.lower()}")


def _deliver(db: Session, c: ReviewCase, text: str, trust_status: str, decision: str, citations: list[dict] | None = None) -> None:
    if c.assistant_message_id is None:
        return
    msg = db.get(Message, c.assistant_message_id)
    if msg is None:
        return
    msg.content = text
    msg.status = "blocked" if trust_status == "blocked" else "delivered"
    msg.trust_status = trust_status
    msg.citations = citations if citations is not None else (c.sources or [])
    explanation = dict(msg.explanation or {})
    explanation.update({
        "headline": {"approved": "Reviewed and approved by NovaCorp compliance",
                     "edited": "Reviewed and edited by NovaCorp compliance",
                     "rejected": "Reviewed by NovaCorp compliance — not approved"}[decision],
        "reviewed": {"decision": decision, "at": clock().isoformat() + "Z"},
        "warning": None,
    })
    msg.explanation = explanation
    msg.updated_at = clock()


def _act(db: Session, c: ReviewCase, reviewer: User, action: str, note: str, edited: str | None = None) -> None:
    db.add(ReviewAction(case_id=c.id, reviewer_id=reviewer.id, reviewer_email=reviewer.email, action=action,
                        note=note or "", edited_response=edited, created_at=clock()))
    audit.record(
        db, f"review.{action.lower()}", created_at=clock(), **audit.actor_fields(reviewer), request_id=c.request_id, review_case_id=c.id,
        policy_ids=sorted({m["policy_id"] for m in c.policy_matches or []}), final_action=action,
        details={"status": c.status, "priority": c.priority, "note": (note or "")[:500]},
    )


def _notify_channels(db: Session, c: ReviewCase) -> None:
    """If the held answer came from the connected workspace or Slack, push the final response to that thread."""
    if c.assistant_message_id:
        from app.services import workspace

        workspace.on_message_updated(db, c.assistant_message_id)


def _resolve(c: ReviewCase, reviewer: User, status: str, final: str) -> None:
    c.status, c.final_response, c.resolved_by, c.resolved_at = status, final, reviewer.id, clock()


def approve(db: Session, c: ReviewCase, reviewer: User, note: str = "") -> ReviewCase:
    _require_open(c)
    citations = None
    trust = "verified"
    if c.draft_response is None:
        requester = db.get(User, c.requester_id) if c.requester_id else None
        if requester is None:
            raise BadRequest("Requester no longer exists; edit or reject instead")
        text, citations, out_action = gateway.generate_for_review(db, gateway.actor_from_user(requester), c.prompt_masked)
        trust = "blocked" if out_action == "BLOCK" else ("redacted" if out_action == "REDACT" else "verified")
    else:
        text = c.draft_response
        if "<" in text and any(f"<{t}>" in text for t in STORAGE_MASKED_ENTITIES | {"SALARY_AMOUNT"}):
            trust = "redacted"
    _resolve(c, reviewer, "APPROVED", text)
    _deliver(db, c, text, trust, "approved", citations)
    _act(db, c, reviewer, "APPROVE", note)
    db.commit()
    _notify_channels(db, c)
    db.refresh(c)
    return c


def edit(db: Session, c: ReviewCase, reviewer: User, edited_response: str, note: str = "") -> ReviewCase:
    _require_open(c)
    if not edited_response.strip():
        raise BadRequest("Edited response cannot be empty")
    # A reviewer cannot accidentally leak data: re-scan before delivery.
    pii = get_pii_detector()
    ents = [e for e in pii.analyze(edited_response) if e.entity_type in STORAGE_MASKED_ENTITIES]
    safe = pii.anonymize(edited_response, ents)
    _resolve(c, reviewer, "EDITED", safe)
    _deliver(db, c, safe, "redacted" if ents else "verified", "edited")
    _act(db, c, reviewer, "EDIT", note + (f" [{len(ents)} sensitive value(s) auto-masked]" if ents else ""), edited=safe)
    db.commit()
    _notify_channels(db, c)
    db.refresh(c)
    return c


def reject(db: Session, c: ReviewCase, reviewer: User, note: str = "") -> ReviewCase:
    _require_open(c)
    _resolve(c, reviewer, "REJECTED", gateway.FALLBACK_REJECTED)
    _deliver(db, c, gateway.FALLBACK_REJECTED, "blocked", "rejected", citations=[])
    _act(db, c, reviewer, "REJECT", note)
    db.commit()
    _notify_channels(db, c)
    db.refresh(c)
    return c


def escalate(db: Session, c: ReviewCase, reviewer: User, note: str = "") -> ReviewCase:
    _require_open(c)
    c.status, c.priority = "ESCALATED", "CRITICAL"
    c.sla_due_at = clock() + timedelta(hours=SLA_HOURS["CRITICAL"])
    _act(db, c, reviewer, "ESCALATE", note)
    db.commit()
    db.refresh(c)
    return c


def add_note(db: Session, c: ReviewCase, reviewer: User, note: str) -> ReviewCase:
    if not note.strip():
        raise BadRequest("Note cannot be empty")
    _act(db, c, reviewer, "NOTE", note)
    db.commit()
    db.refresh(c)
    return c
