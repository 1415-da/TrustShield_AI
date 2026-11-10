"""Append-only, hash-chained audit log.

Each event stores `prev_hash` and `event_hash = sha256(prev_hash || canonical_json(event))`. Editing or
deleting any row breaks the chain, which `verify_chain` detects. Updates and deletes are additionally
rejected by an ORM guard (below) and, on PostgreSQL, by a trigger installed in the initial migration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.models.base import utcnow

HASHED_FIELDS = (
    "event_type", "request_id", "actor_user_id", "actor_email", "actor_role", "app_id", "policy_ids", "input_risk_score",
    "output_risk_score", "input_action", "output_action", "final_action", "redaction_count", "review_case_id",
    "model_provider", "model_name", "latency_ms", "content_hash", "details", "created_at",
)


class AuditImmutableError(RuntimeError):
    pass


@event.listens_for(AuditEvent, "before_update")
def _block_update(*_: Any) -> None:
    raise AuditImmutableError("audit_events is append-only")


@event.listens_for(AuditEvent, "before_delete")
def _block_delete(*_: Any) -> None:
    raise AuditImmutableError("audit_events is append-only")


def _canonical(ev: AuditEvent) -> str:
    payload = {}
    for f in HASHED_FIELDS:
        v = getattr(ev, f)
        payload[f] = v.isoformat() if isinstance(v, datetime) else v
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def compute_hash(prev_hash: str, ev: AuditEvent) -> str:
    return hashlib.sha256((prev_hash + _canonical(ev)).encode("utf-8")).hexdigest()


def record(db: Session, event_type: str, *, created_at: datetime | None = None, commit: bool = False, **fields: Any) -> AuditEvent:
    """Append an audit event. Callers must pass masked values only."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(424242)"))  # serialise chain appends
    last = db.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
    ev = AuditEvent(event_type=event_type, created_at=(created_at or utcnow()).replace(microsecond=0), **fields)
    ev.details = ev.details or {}
    ev.policy_ids = ev.policy_ids or []
    ev.redaction_count = ev.redaction_count or 0
    ev.prev_hash = last.event_hash if last else "0" * 64
    ev.event_hash = compute_hash(ev.prev_hash, ev)
    db.add(ev)
    db.flush()
    if commit:
        db.commit()
    return ev


def actor_fields(user: Any) -> dict[str, Any]:
    if user is None:
        return {}
    return {"actor_user_id": user.id, "actor_email": user.email, "actor_role": user.primary_role}


def verify_chain(db: Session) -> dict[str, Any]:
    prev = "0" * 64
    checked = 0
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        if ev.prev_hash != prev or compute_hash(prev, ev) != ev.event_hash:
            return {"valid": False, "checked": checked, "broken_at_event_id": ev.id}
        prev = ev.event_hash
        checked += 1
    return {"valid": True, "checked": checked, "broken_at_event_id": None}
