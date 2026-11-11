from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDatetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class MessageOut(ORMModel):
    id: int
    conversation_id: int
    role: str
    content: str
    status: str
    trust_status: str | None
    request_id: str
    action_id: int | None = None
    explanation: dict[str, Any] | None = None
    citations: list[dict[str, Any]] = []
    created_at: UTCDatetime
    updated_at: UTCDatetime


class DecisionOut(BaseModel):
    request_id: str
    input_action: str
    output_action: str | None
    trust_status: str
    llm_called: bool
    review_case_id: int | None
    latency_ms: float


class ChatResponse(BaseModel):
    conversation_id: int
    user_message: MessageOut
    message: MessageOut
    decision: DecisionOut


class ConversationSummary(ORMModel):
    id: int
    title: str
    created_at: UTCDatetime
    updated_at: UTCDatetime
    last_trust_status: str | None = None
    pending_reviews: int = 0


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]
