from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDatetime


class DocumentOut(ORMModel):
    id: int
    title: str
    filename: str
    content_type: str
    source: str
    trust_level: str
    status: str
    chunk_count: int
    uploaded_by: int | None
    created_at: UTCDatetime
    indexed_at: UTCDatetime | None


class ChunkOut(ORMModel):
    id: int
    ordinal: int
    heading: str
    text: str
    token_count: int


class DocumentDetail(DocumentOut):
    content: str
    chunks: list[ChunkOut]


class ReviewActionOut(ORMModel):
    id: int
    reviewer_id: int
    reviewer_email: str
    action: str
    note: str
    edited_response: str | None
    created_at: UTCDatetime


class ReviewCaseOut(ORMModel):
    id: int
    request_id: str
    requester_role: str
    status: str
    priority: str
    origin: str
    reason: str
    risk_score: float
    confidence: float | None
    prompt_masked: str
    suggested_action: str
    sla_due_at: UTCDatetime
    created_at: UTCDatetime
    resolved_at: UTCDatetime | None
    policy_matches: list[dict[str, Any]]


class ReviewCaseDetail(ReviewCaseOut):
    draft_response: str | None
    final_response: str | None
    sources: list[dict[str, Any]]
    signals: dict[str, Any]
    actions: list[ReviewActionOut]
    requester_department: str | None = None
    resolved_by_email: str | None = None


class ReviewDecision(BaseModel):
    note: str = Field(default="", max_length=2000)


class ReviewEdit(ReviewDecision):
    edited_response: str = Field(min_length=1, max_length=8000)


class AuditEventOut(ORMModel):
    id: int
    event_type: str
    request_id: str | None
    actor_user_id: int | None
    actor_email: str | None
    actor_role: str | None
    app_id: int | None
    policy_ids: list[int]
    input_risk_score: float | None
    output_risk_score: float | None
    input_action: str | None
    output_action: str | None
    final_action: str | None
    redaction_count: int
    review_case_id: int | None
    model_provider: str | None
    model_name: str | None
    latency_ms: float | None
    content_hash: str | None
    details: dict[str, Any]
    created_at: UTCDatetime
    prev_hash: str
    event_hash: str


class AuditPage(BaseModel):
    items: list[AuditEventOut]
    total: int
    page: int
    page_size: int


class TestCaseIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=3, max_length=200)
    category: str
    role_key: str = "employee"
    prompt: str = Field(min_length=1, max_length=4000)
    expected_input_actions: list[str] = Field(min_length=1)
    expected_output_actions: list[str] = []
    notes: str = ""


class TestCaseOut(TestCaseIn, ORMModel):
    id: int
    is_active: bool


class TestRunRequest(BaseModel):
    case_ids: list[int] | None = None


class TestRunOut(ORMModel):
    id: int
    status: str
    started_at: UTCDatetime
    finished_at: UTCDatetime | None
    total: int
    passed: int
    failed: int
    false_positives: int
    false_negatives: int
    summary: dict[str, Any]


class TestResultOut(ORMModel):
    id: int
    test_case_id: int
    passed: bool
    actual_input_action: str
    actual_output_action: str | None
    trust_status: str
    matched_policies: list[str]
    confidence: float | None
    latency_ms: float
    false_positive: bool
    false_negative: bool
    failure_reason: str
    code: str | None = None
    name: str | None = None
    category: str | None = None
    role_key: str | None = None
    prompt: str | None = None
    expected_input_actions: list[str] = []
    expected_output_actions: list[str] = []


class RoleOut(ORMModel):
    id: int
    key: str
    name: str
    description: str
    permissions: list[str]


class RoleUpdate(BaseModel):
    permissions: list[str]


class UserUpdate(BaseModel):
    role_keys: list[str] | None = None
    is_active: bool | None = None


class AppOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str
    owner_team: str
    status: str
    created_at: UTCDatetime
    keys: list["ApiKeyOut"] = []


class AppCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = ""
    owner_team: str = "IT"


class AppUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(active|paused)$")
    description: str | None = None


class ApiKeyOut(ORMModel):
    id: int
    name: str
    prefix: str
    created_at: UTCDatetime
    last_used_at: UTCDatetime | None
    revoked_at: UTCDatetime | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class ApiKeyCreated(ApiKeyOut):
    key: str  # shown once


AppOut.model_rebuild()
