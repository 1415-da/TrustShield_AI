from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel, UTCDatetime

RuleType = Literal["regex", "keyword", "pii_entity", "topic", "role_permission", "confidence_threshold"]
MatchField = Literal["user_input", "llm_output", "retrieved_context"]
Action = Literal["BLOCK", "REDACT", "REVIEW", "ESCALATE", "ALLOW"]
SeverityT = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class RuleIn(BaseModel):
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


class RuleOut(RuleIn, ORMModel):
    id: int

    @model_validator(mode="after")
    def _required_config(self) -> "RuleOut":  # type: ignore[override]
        return self


class PolicyBase(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = ""
    risk_category: str = Field(min_length=2, max_length=80)
    sensitive_data_type: str = "none"
    applicable_roles: list[str] = []
    action: Action
    severity: SeverityT = "MEDIUM"
    threshold: float = Field(default=0.5, ge=0, le=1)
    user_message: str = ""
    is_active: bool = True


class PolicyCreate(PolicyBase):
    rules: list[RuleIn] = Field(min_length=1)


class PolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    risk_category: str | None = None
    sensitive_data_type: str | None = None
    applicable_roles: list[str] | None = None
    action: Action | None = None
    severity: SeverityT | None = None
    threshold: float | None = Field(default=None, ge=0, le=1)
    user_message: str | None = None
    is_active: bool | None = None
    rules: list[RuleIn] | None = None
    change_summary: str = ""


class PolicyOut(PolicyBase, ORMModel):
    id: int
    version: int
    created_at: UTCDatetime
    updated_at: UTCDatetime
    rules: list[RuleOut]


class PolicyVersionOut(ORMModel):
    id: int
    version: int
    change_summary: str
    changed_by: int | None
    created_at: UTCDatetime
    snapshot: dict


class SimulateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    role: str = "employee"
    include_output: bool = True
    draft_policy: PolicyCreate | None = None  # evaluate an unsaved policy alongside active ones
