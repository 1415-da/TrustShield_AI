"""Compliance evidence reports and report schedules.

A READY report is an immutable evidence record: its content, hash, period, filters and source list can never change
(ORM guard below). The only permitted later changes are expiry (READY → EXPIRED) and withdrawal (deleted_at), both of
which are audited.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, event, inspect
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import JSONType, utcnow

IMMUTABLE_FIELDS = ("content", "content_hash", "source_event_ids", "source_record_count", "filters", "period_start",
                    "period_end", "report_type", "title", "generated_by", "completed_at")


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="GENERATING", index=True)  # GENERATING | READY | FAILED | EXPIRED
    version: Mapped[int] = mapped_column(Integer, default=1)
    filters_hash: Mapped[str] = mapped_column(String(64), index=True)
    filters: Mapped[dict] = mapped_column(JSONType, default=dict)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    content: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_event_ids: Mapped[list[int]] = mapped_column(JSONType, default=list)
    source_record_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    generated_by_email: Mapped[str] = mapped_column(String(255), default="scheduler")
    schedule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ImmutableReportError(RuntimeError):
    pass


@event.listens_for(ComplianceReport, "before_update")
def _guard_report(_mapper, _conn, target: ComplianceReport) -> None:
    state = inspect(target)
    hist = state.attrs.status.history
    previous = (list(hist.deleted) or list(hist.unchanged) or [target.status])[0]
    if previous not in ("READY", "EXPIRED"):
        return
    changed = [f for f in IMMUTABLE_FIELDS if getattr(state.attrs, f).history.has_changes()]
    if changed:
        raise ImmutableReportError(f"report {target.id} is an immutable evidence record; cannot change {', '.join(changed)}")
    if target.status not in ("READY", "EXPIRED"):
        raise ImmutableReportError(f"report {target.id} cannot move from {previous} to {target.status}")


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    filters: Mapped[dict] = mapped_column(JSONType, default=dict)  # period expressed as period_days
    cadence: Mapped[str] = mapped_column(String(20))  # weekly | monthly
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_email: Mapped[str] = mapped_column(String(255), default="")
    source_report_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_report_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
