from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONType, utcnow


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    risk_category: Mapped[str] = mapped_column(String(80), index=True)
    sensitive_data_type: Mapped[str] = mapped_column(String(80), default="none")
    applicable_roles: Mapped[list[str]] = mapped_column(JSONType, default=list)  # empty = all roles
    action: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    threshold: Mapped[float] = mapped_column(Float, default=0.5)
    user_message: Mapped[str] = mapped_column(Text, default="")  # plain-language explanation shown to employees
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    rules: Mapped[list["PolicyRule"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", lazy="selectin", order_by="PolicyRule.id"
    )


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    rule_type: Mapped[str] = mapped_column(String(40))  # regex | keyword | pii_entity | topic | role_permission | confidence_threshold
    match_field: Mapped[str] = mapped_column(String(40), default="user_input")
    pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSONType, default=list)
    entity_types: Mapped[list[str]] = mapped_column(JSONType, default=list)
    topic: Mapped[str | None] = mapped_column(String(80), nullable=True)
    required_permission: Mapped[str | None] = mapped_column(String(80), nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    action: Mapped[str | None] = mapped_column(String(20), nullable=True)  # None → inherit policy action
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    applies_to_roles: Mapped[list[str]] = mapped_column(JSONType, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    policy: Mapped[Policy] = relationship(back_populates="rules")


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONType)
    change_summary: Mapped[str] = mapped_column(String(500), default="")
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
