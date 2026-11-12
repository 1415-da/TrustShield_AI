"""Policy families, immutable versions, approvals, comments, policy audit trail, and exceptions.

A *policy* row is the stable family (name, owner, cadence). Its behaviour lives entirely in
`policy_versions.snapshot`. Only a version with status ACTIVE is ever enforced, and a partial unique index
guarantees at most one ACTIVE version per family. Once a version leaves DRAFT its snapshot can never change
(ORM guard below); later changes always create a new version.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event, inspect, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.organization import TenantMixin
from app.models.base import JSONType, utcnow

VERSION_STATUSES = ("DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "REJECTED", "APPROVED", "ACTIVE", "INACTIVE", "ARCHIVED")
EDITABLE_STATUSES = ("DRAFT", "CHANGES_REQUESTED", "REJECTED")


class Policy(TenantMixin, Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_policies_name_per_org"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    risk_category: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(200), default="")
    review_cadence_days: Mapped[int] = mapped_column(Integer, default=180)
    is_archived: Mapped[bool] = mapped_column(default=False)
    active_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("policy_versions.id", use_alter=True, name="fk_policies_active_version", ondelete="SET NULL"), nullable=True
    )
    latest_version: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    versions: Mapped[list["PolicyVersion"]] = relationship(
        back_populates="policy", foreign_keys="PolicyVersion.policy_id", order_by="PolicyVersion.version",
        cascade="all, delete-orphan", lazy="selectin",
    )


class PolicyVersion(TenantMixin, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version", name="uq_policy_version_number"),
        Index("uq_one_active_version", "policy_id", unique=True,
              postgresql_where=text("status = 'ACTIVE'"), sqlite_where=text("status = 'ACTIVE'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    snapshot: Mapped[dict] = mapped_column(JSONType)
    snapshot_hash: Mapped[str] = mapped_column(String(64), default="")
    change_summary: Mapped[str] = mapped_column(String(500), default="")
    based_on_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_email: Mapped[str] = mapped_column(String(255), default="")
    submitted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activated_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    policy: Mapped[Policy] = relationship(back_populates="versions", foreign_keys=[policy_id])


class ImmutableVersionError(RuntimeError):
    pass


@event.listens_for(PolicyVersion, "before_update")
def _guard_snapshot(_mapper, _conn, target: PolicyVersion) -> None:
    state = inspect(target)
    if not state.attrs.snapshot.history.has_changes():
        return
    hist = state.attrs.status.history
    previous = (list(hist.deleted) or list(hist.unchanged) or [target.status])[0]
    if previous not in EDITABLE_STATUSES:
        raise ImmutableVersionError(f"policy version v{target.version} is {previous} and cannot be modified")


class PolicyApproval(TenantMixin, Base):
    """One review request per submission. Decisions: APPROVED, CHANGES_REQUESTED, REJECTED (or WITHDRAWN)."""

    __tablename__ = "policy_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("policy_versions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    requested_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_by_email: Mapped[str] = mapped_column(String(255), default="")
    request_note: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    impact: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # cached evaluation-suite impact analysis


class PolicyComment(TenantMixin, Base):
    __tablename__ = "policy_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int | None] = mapped_column(ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True)
    author_id: Mapped[int] = mapped_column(Integer)
    author_email: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PolicyAuditEvent(TenantMixin, Base):
    """Per-policy lifecycle trail. Each row is mirrored into the global hash-chained audit_events table."""

    __tablename__ = "policy_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    audit_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PolicyException(TenantMixin, Base):
    """A time-boxed, approved exemption from one policy for a user, role, or department."""

    __tablename__ = "policy_exceptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    subject_type: Mapped[str] = mapped_column(String(20))  # user | role | department
    subject: Mapped[str] = mapped_column(String(255))
    justification: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="REQUESTED", index=True)  # REQUESTED | APPROVED | REJECTED | REVOKED
    requested_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_by_email: Mapped[str] = mapped_column(String(255), default="")
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
