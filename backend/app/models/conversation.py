from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.organization import TenantMixin
from app.models.base import JSONType, utcnow


class Conversation(TenantMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    app_id: Mapped[int | None] = mapped_column(ForeignKey("connected_apps.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(TenantMixin, Base):
    """A chat message. `content` is always the *masked* text; raw content is kept only as a hash."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(30), default="delivered")  # delivered | pending_review | blocked
    trust_status: Mapped[str | None] = mapped_column(String(30), nullable=True)  # verified | needs_review | redacted | blocked
    request_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    action_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # agent action card
    explanation: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    citations: Mapped[list[dict]] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
