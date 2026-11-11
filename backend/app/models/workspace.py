"""Connected workspace (built-in channels) and Slack integration records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import utcnow


class PolicyProfile(Base):
    """A named channel policy profile. Policies list the profiles they are scoped to (empty = everywhere)."""

    __tablename__ = "policy_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WorkspaceChannel(Base):
    __tablename__ = "workspace_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # Slack channel id (or internal id)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    policy_hint: Mapped[str] = mapped_column(Text, default="")
    profile_key: Mapped[str] = mapped_column(String(40), default="general")
    source: Mapped[str] = mapped_column(String(20), default="internal")  # internal | slack
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SlackIdentity(Base):
    """Maps a Slack user to a TrustShield user (linked by verified email)."""

    __tablename__ = "slack_identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    slack_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SlackEvent(Base):
    """One inbound message (built-in workspace or Slack). `event_id` is the idempotency key. Text is stored masked."""

    __tablename__ = "slack_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(20), index=True)  # workspace | slack
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("workspace_channels.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    external_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    thread_ts: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED", index=True)
    # RECEIVED | PROCESSED | FAILED | RATE_LIMITED | REJECTED | REJECTED_UNLINKED
    deliveries: Mapped[int] = mapped_column(Integer, default=1)  # Slack retries increment this; processing happens once
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assistant_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    review_case_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trust_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    input_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    text_masked: Mapped[str] = mapped_column(Text, default="")
    text_hash: Mapped[str] = mapped_column(String(64), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
