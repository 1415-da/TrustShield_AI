from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.organization import TenantMixin
from app.models.base import JSONType, utcnow


class TestCase(TenantMixin, Base):
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_test_cases_code_per_org"),)
    __test__ = False  # stop pytest from collecting this class

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80), index=True)
    role_key: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    expected_input_actions: Mapped[list[str]] = mapped_column(JSONType, default=list)
    expected_output_actions: Mapped[list[str]] = mapped_column(JSONType, default=list)  # empty = any
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TestRun(TenantMixin, Base):
    __tablename__ = "test_runs"
    __test__ = False

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | completed | failed
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    false_positives: Mapped[int] = mapped_column(Integer, default=0)
    false_negatives: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict] = mapped_column(JSONType, default=dict)

    results: Mapped[list["TestResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="TestResult.id"
    )


class TestResult(TenantMixin, Base):
    __tablename__ = "test_results"
    __test__ = False

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), index=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"))
    passed: Mapped[bool] = mapped_column(Boolean)
    actual_input_action: Mapped[str] = mapped_column(String(30))
    actual_output_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trust_status: Mapped[str] = mapped_column(String(30))
    matched_policies: Mapped[list[str]] = mapped_column(JSONType, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    false_positive: Mapped[bool] = mapped_column(Boolean, default=False)
    false_negative: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_reason: Mapped[str] = mapped_column(Text, default="")

    run: Mapped[TestRun] = relationship(back_populates="results")
