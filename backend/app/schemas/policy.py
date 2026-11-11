from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel, UTCDatetime

RuleType = Literal["regex", "keyword", "pii_entity", "topic", "role_permission", "confidence_threshold"]
MatchField = Literal["user_input", "llm_output", "retrieved_context"]
Action = Literal["BLOCK", "REDACT", "REVIEW", "ESCALATE", "ALLOW"]
SeverityT = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class RuleIn(BaseModel):
    key: str | None = Field(default=None, max_length=32, description="Stable rule identity across versions (for diffs)")
    name: str = Field(default="", max_length=200)
    rule_type: RuleType
    match_field: MatchField = "user_input"
    pattern: str | None = Field(default=None, max_length=2000)
    keywords: list[str] = []
    entity_types: list[str] = []
    topic: str | None = None
    required_permission: str | None = None
    threshold: float | None = Field(default=None, ge=0, le=1)
    action: Action | None = None
    severity: SeverityT | None = None
    applies_to_roles: list[str] = []
    is_active: bool = True

    @field_validator("pattern")
    @classmethod
    def _valid_regex(cls, v: str | None) -> str | None:
        if v:
            try:
                re.compile(v)
            except re.error as exc:
                raise ValueError(f"invalid regular expression: {exc}") from None
        return v

    @model_validator(mode="after")
    def _required_config(self) -> "RuleIn":
        need = {
            "regex": self.pattern, "keyword": self.keywords, "pii_entity": self.entity_types, "topic": self.topic,
            "role_permission": self.required_permission and (self.topic or self.entity_types), "confidence_threshold": True,
        }[self.rule_type]
        if not need:
            raise ValueError(f"rule_type '{self.rule_type}' is missing its configuration")
        if self.rule_type == "confidence_threshold" and self.match_field != "llm_output":
            raise ValueError("confidence_threshold rules must match llm_output")
        return self


class PolicyDefinition(BaseModel):
    """Everything a version snapshot captures."""

    name: str = Field(min_length=3, max_length=200)
    description: str = ""
    risk_category: str = Field(min_length=2, max_length=80)
    sensitive_data_type: str = "none"
    owner: str = Field(default="", max_length=200)
    review_cadence_days: int = Field(default=180, ge=7, le=730)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    applicable_roles: list[str] = []
    profiles: list[str] = Field(default=[], description="Channel policy profiles; empty = applies everywhere")
    action: Action
    severity: SeverityT = "MEDIUM"
    threshold: float = Field(default=0.5, ge=0, le=1)
    user_message: str = ""
    rules: list[RuleIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _window(self) -> "PolicyDefinition":
        if self.effective_from and self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


class PolicyCreate(PolicyDefinition):
    change_summary: str = Field(default="Initial draft", max_length=500)


class PolicyDraftUpdate(BaseModel):
    """Partial update of the working draft. Omitted fields keep the draft's (or head version's) value."""

    name: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    risk_category: str | None = None
    sensitive_data_type: str | None = None
    owner: str | None = None
    review_cadence_days: int | None = Field(default=None, ge=7, le=730)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    applicable_roles: list[str] | None = None
    profiles: list[str] | None = None
    action: Action | None = None
    severity: SeverityT | None = None
    threshold: float | None = Field(default=None, ge=0, le=1)
    user_message: str | None = None
    rules: list[RuleIn] | None = Field(default=None, min_length=1)
    change_summary: str = Field(default="", max_length=500)


class Note(BaseModel):
    note: str = Field(default="", max_length=2000)


class ActivateRequest(Note):
    version_id: int | None = None


class RollbackRequest(Note):
    version_id: int
    activate: bool = False


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    version_id: int | None = None


class VersionOut(ORMModel):
    id: int
    policy_id: int
    version: int
    status: str
    snapshot: dict[str, Any]
    snapshot_hash: str
    change_summary: str
    based_on_version_id: int | None
    effective_from: UTCDatetime | None
    effective_to: UTCDatetime | None
    created_by_email: str
    submitted_at: UTCDatetime | None
    approved_by_email: str | None
    approved_at: UTCDatetime | None
    activated_by_email: str | None
    activated_at: UTCDatetime | None
    deactivated_at: UTCDatetime | None
    created_at: UTCDatetime
    updated_at: UTCDatetime


class VersionSummary(ORMModel):
    id: int
    version: int
    status: str
    change_summary: str
    created_by_email: str
    approved_by_email: str | None
    created_at: UTCDatetime
    activated_at: UTCDatetime | None


class PolicyOut(BaseModel):
    """List view: family metadata plus the head version's headline definition."""

    id: int
    name: str
    description: str
    risk_category: str
    owner: str
    review_cadence_days: int
    status: str
    action: str
    severity: str
    rules_count: int
    active_version: int | None
    latest_version: int
    working_status: str | None
    pending_review: bool
    next_review_at: UTCDatetime | None
    created_at: UTCDatetime
    updated_at: UTCDatetime


class PolicyDetail(PolicyOut):
    active: VersionOut | None
    working: VersionOut | None
    versions: list[VersionSummary]


class ApprovalOut(ORMModel):
    id: int
    policy_id: int
    version_id: int
    status: str
    requested_by_email: str
    request_note: str
    requested_at: UTCDatetime
    decided_by_email: str | None
    decision_note: str
    decided_at: UTCDatetime | None
    impact: dict[str, Any] | None = None
    policy_name: str | None = None
    version: int | None = None
    risk_category: str | None = None


class CommentOut(ORMModel):
    id: int
    policy_id: int
    version_id: int | None
    author_email: str
    body: str
    created_at: UTCDatetime


class PolicyAuditOut(ORMModel):
    id: int
    version_id: int | None
    version_number: int | None
    event_type: str
    from_status: str | None
    to_status: str | None
    actor_email: str | None
    actor_role: str | None
    note: str
    details: dict[str, Any]
    audit_event_id: int | None
    created_at: UTCDatetime


class SimulateRequest(BaseModel):
    prompt: str = Field(default="", max_length=4000)
    role: str = "employee"
    include_output: bool = True
    profile: str | None = None
    version_id: int | None = Field(default=None, description="Version to force active; default = the working draft")
    suite: bool = Field(default=False, description="Run the impact analysis across the evaluation suite instead")
    draft_policy: PolicyDefinition | None = None


class ExceptionIn(BaseModel):
    policy_id: int
    subject_type: Literal["user", "role", "department"]
    subject: str = Field(min_length=2, max_length=255)
    justification: str = Field(min_length=10, max_length=2000)
    starts_at: datetime | None = None
    expires_at: datetime


class ExceptionOut(ORMModel):
    id: int
    policy_id: int
    subject_type: str
    subject: str
    justification: str
    status: str
    requested_by_email: str
    decided_by_email: str | None
    decision_note: str
    starts_at: UTCDatetime
    expires_at: UTCDatetime
    created_at: UTCDatetime
    decided_at: UTCDatetime | None
    revoked_at: UTCDatetime | None
    policy_name: str | None = None
    is_expired: bool = False
