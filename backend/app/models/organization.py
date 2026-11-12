"""Organizations (workspaces) and the tenant mixin that scopes every business table to one of them."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.core.database import Base
from app.models.base import utcnow

# The original workspace created by the first migration. Sessions with no organization set act within it.
DEFAULT_ORG_ID = 1


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    industry: Mapped[str] = mapped_column(String(80), default="")
    size: Mapped[str] = mapped_column(String(40), default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TenantMixin:
    """Adds `organization_id`. Reads are filtered and inserts are stamped automatically (see app.core.tenancy)."""

    @declared_attr
    def organization_id(cls) -> Mapped[int]:  # noqa: N805
        return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
