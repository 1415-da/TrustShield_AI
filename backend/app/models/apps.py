from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.organization import TenantMixin
from app.models.base import utcnow


class ConnectedApp(TenantMixin, Base):
    __tablename__ = "connected_apps"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_connected_apps_name_per_org"), UniqueConstraint("organization_id", "slug", name="uq_connected_apps_slug_per_org"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_team: Mapped[str] = mapped_column(String(120), default="IT")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | paused
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    keys: Mapped[list["ApiKey"]] = relationship(back_populates="app", cascade="all, delete-orphan", lazy="selectin")


class ApiKey(TenantMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("connected_apps.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    app: Mapped[ConnectedApp] = relationship(back_populates="keys")
