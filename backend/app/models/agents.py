"""Agent action governance: registry, configurable action policies, requested actions, approvals, executions, audit.

Duplicate execution is impossible at the database level: a partial unique index allows at most one SUCCEEDED
execution per action. Request-level idempotency keys are unique per user.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import JSONType, utcnow

ACTION_CATEGORIES = ("READ", "SENSITIVE_READ", "CREATE", "UPDATE", "FINANCIAL_ACTION", "COMMUNICATION", "DESTRUCTIVE_ACTION", "ADMIN_ACTION")
ACTION_DECISIONS = ("EXECUTE", "REQUIRE_APPROVAL", "SEND_TO_REVIEW", "BLOCK", "ESCALATE")
ACTION_STATUSES = ("PENDING_APPROVAL", "IN_REVIEW", "ESCALATED", "NEEDS_INFO", "APPROVED", "EXECUTING", "EXECUTED", "REJECTED",
                   "BLOCKED", "FAILED", "COMPENSATED")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_team: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | paused
    allowed_action_types: Mapped[list[str]] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ActionType(Base):
    __tablename__ = "action_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    target_system: Mapped[str] = mapped_column(String(120), default="")
    executor: Mapped[str] = mapped_column(String(60))
    required_permission: Mapped[str | None] = mapped_column(String(60), nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSONType, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ActionPolicy(Base):
    """Configurable approval rule. Conditions: amount_gt/gte/lt/lte, requester_roles, external (bool)."""

    __tablename__ = "action_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    action_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    conditions: Mapped[dict] = mapped_column(JSONType, default=dict)
    decision: Mapped[str] = mapped_column(String(30))
    approver_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_email: Mapped[str] = mapped_column(String(255), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    requester_email: Mapped[str] = mapped_column(String(255))
    requester_role: Mapped[str] = mapped_column(String(64))
    action_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    summary: Mapped[str] = mapped_column(String(500), default="")
    target_system: Mapped[str] = mapped_column(String(120), default="")
    target_record: Mapped[str] = mapped_column(String(200), default="")
    params: Mapped[dict] = mapped_column(JSONType, default=dict)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    external: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    required_approver_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_basis: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    request_text_masked: Mapped[str] = mapped_column(Text, default="")
    missing_info: Mapped[list[str]] = mapped_column(JSONType, default=list)
    info_request_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ActionApproval(Base):
    __tablename__ = "action_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("agent_actions.id", ondelete="CASCADE"), index=True)
    approver_role: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)  # PENDING | APPROVED | REJECTED | INFO_REQUESTED | ESCALATED
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ActionExecution(Base):
    __tablename__ = "action_executions"
    __table_args__ = (
        Index("uq_one_successful_execution", "action_id", unique=True,
              postgresql_where=text("status = 'SUCCEEDED'"), sqlite_where=text("status = 'SUCCEEDED'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("agent_actions.id", ondelete="CASCADE"), index=True)
    executor: Mapped[str] = mapped_column(String(60))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))  # SUCCEEDED | FAILED | COMPENSATED
    result: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_by_email: Mapped[str] = mapped_column(String(255), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ActionAuditEvent(Base):
    """Per-action trail; every row is mirrored into the hash-chained global audit log."""

    __tablename__ = "action_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("agent_actions.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    audit_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ActionIdempotencyKey(Base):
    __tablename__ = "action_idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_action_idempotency_per_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(128))
    action_id: Mapped[int] = mapped_column(ForeignKey("agent_actions.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
