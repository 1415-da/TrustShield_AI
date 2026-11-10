from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONType, utcnow

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    permissions: Mapped[list[str]] = mapped_column(JSONType, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(120), default="General Operations")
    title: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")

    @property
    def role_keys(self) -> list[str]:
        return [r.key for r in self.roles]

    @property
    def permissions(self) -> set[str]:
        perms: set[str] = set()
        for role in self.roles:
            perms.update(role.permissions or [])
        return perms

    @property
    def primary_role(self) -> str:
        """The most privileged role, used for display and audit attribution."""
        order = ["trustshield_admin", "security_auditor", "compliance_reviewer", "hr_manager", "finance_analyst", "employee"]
        keys = self.role_keys
        for key in order:
            if key in keys:
                return key
        return keys[0] if keys else "employee"

    def has(self, permission: str) -> bool:
        return permission in self.permissions


class EmployeeRecord(Base):
    """Synthetic HR directory. Every row is fake test data (is_test_data is always true)."""

    __tablename__ = "employee_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    department: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(120))
    work_email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(40))
    salary_band: Mapped[str] = mapped_column(String(20))
    salary_range: Mapped[str] = mapped_column(String(80))
    test_national_id: Mapped[str] = mapped_column(String(20))
    is_test_data: Mapped[bool] = mapped_column(Boolean, default=True)
