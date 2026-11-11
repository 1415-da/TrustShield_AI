from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDatetime

ReportType = Literal["governance_summary", "sensitive_data", "human_oversight", "policy_changes", "exceptions"]


class ReportRequest(BaseModel):
    report_type: ReportType
    period_start: datetime | None = None
    period_end: datetime | None = None
    departments: list[str] = []
    policy_ids: list[int] = []
    risk_levels: list[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]] = []
    reviewers: list[str] = []
    include_reviews: bool = True
    include_policy_changes: bool = True
    include_sensitive_events: bool = True
    retention_days: int | None = Field(default=None, ge=1, le=3650, description="Report expires after this many days")
    title: str | None = Field(default=None, max_length=300)


class ScheduleRequest(BaseModel):
    cadence: Literal["weekly", "monthly"]
    retention_days: int | None = Field(default=None, ge=1, le=3650)


class ReportOut(ORMModel):
    id: int
    report_type: str
    title: str
    status: str
    version: int
    filters: dict[str, Any]
    period_start: UTCDatetime
    period_end: UTCDatetime
    content_hash: str | None
    source_record_count: int
    generated_by_email: str
    schedule_id: int | None
    error: str | None
    created_at: UTCDatetime
    completed_at: UTCDatetime | None
    expires_at: UTCDatetime | None
    deleted_at: UTCDatetime | None


class ReportDetail(ReportOut):
    content: dict[str, Any] | None


class ScheduleOut(ORMModel):
    id: int
    report_type: str
    title: str
    filters: dict[str, Any]
    cadence: str
    retention_days: int | None
    is_active: bool
    created_by_email: str
    source_report_id: int | None
    next_run_at: UTCDatetime
    last_run_at: UTCDatetime | None
    last_report_id: int | None
    created_at: UTCDatetime
