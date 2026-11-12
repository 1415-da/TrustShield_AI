from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.organization import TenantMixin
from app.models.base import JSONType, utcnow


class GuardrailDecision(TenantMixin, Base):
    __tablename__ = "guardrail_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    stage: Mapped[str] = mapped_column(String(20))  # input | context | output
    action: Mapped[str] = mapped_column(String(30), index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    signals: Mapped[dict] = mapped_column(JSONType, default=dict)
    matches: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    redaction_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AuditEvent(TenantMixin, Base):
    """Append-only, hash-chained audit record. Updates and deletes are rejected (ORM guard + DB trigger)."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_ids: Mapped[list[int]] = mapped_column(JSONType, default=list)
    input_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    output_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    final_action: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    redaction_count: Mapped[int] = mapped_column(Integer, default=0)
    review_case_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    event_hash: Mapped[str] = mapped_column(String(64), default="")


class ReviewCase(TenantMixin, Base):
    __tablename__ = "review_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    user_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    assistant_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    requester_role: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)  # PENDING | ESCALATED | APPROVED | EDITED | REJECTED
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", index=True)
    # Original priority/SLA at creation. Escalation changes `priority`/`sla_due_at`; these never change, which keeps
    # SLA evidence in compliance reports reproducible.
    initial_priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    initial_sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    origin: Mapped[str] = mapped_column(String(30), default="input")  # input | output | escalation
    reason: Mapped[str] = mapped_column(Text)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_matches: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    prompt_masked: Mapped[str] = mapped_column(Text)
    draft_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str] = mapped_column(String(30), default="APPROVE")
    sources: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    signals: Mapped[dict] = mapped_column(JSONType, default=dict)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    actions: Mapped[list["ReviewAction"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="ReviewAction.id", lazy="selectin"
    )


class ReviewAction(TenantMixin, Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("review_cases.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewer_email: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(20))  # APPROVE | EDIT | REJECT | ESCALATE | NOTE
    note: Mapped[str] = mapped_column(Text, default="")
    edited_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    case: Mapped[ReviewCase] = relationship(back_populates="actions")
