"""Shared guardrail types.

Raw sensitive values only ever live in memory inside `Entity.text`. Anything that leaves the guardrail
layer (matches, evidence, signals) is built from masked representations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class InputAction(str, Enum):
    ALLOW = "ALLOW"
    REDACT = "REDACT"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class OutputAction(str, Enum):
    SHOW = "SHOW"
    SHOW_WITH_WARNING = "SHOW_WITH_WARNING"
    REDACT = "REDACT"
    SEND_TO_REVIEW = "SEND_TO_REVIEW"
    BLOCK = "BLOCK"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


SEVERITY_WEIGHT: dict[str, float] = {"LOW": 0.25, "MEDIUM": 0.5, "HIGH": 0.75, "CRITICAL": 0.95}
SEVERITY_ORDER: list[str] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

RULE_TYPES = ("regex", "keyword", "pii_entity", "topic", "role_permission", "confidence_threshold")
MATCH_FIELDS = ("user_input", "llm_output", "retrieved_context")
RULE_ACTIONS = ("ALLOW", "REDACT", "REVIEW", "BLOCK", "ESCALATE")

# Entity types that are always masked before anything is persisted, regardless of policy outcome.
STORAGE_MASKED_ENTITIES: frozenset[str] = frozenset(
    {"CREDIT_CARD", "BANK_ACCOUNT", "US_SSN", "TEST_NATIONAL_ID", "EMAIL_ADDRESS", "PHONE_NUMBER", "IBAN_CODE", "CREDENTIAL"}
)


@dataclass
class Entity:
    entity_type: str
    start: int
    end: int
    score: float
    text: str = field(repr=False)  # raw value — never serialise
    source: str = "regex"  # presidio | regex

    @property
    def masked(self) -> str:
        return mask_value(self.entity_type, self.text)

    def public(self) -> dict:
        return {"entity_type": self.entity_type, "score": round(self.score, 2), "masked": self.masked, "source": self.source}


def mask_value(entity_type: str, raw: str) -> str:
    """Human-readable masked preview that never reveals the full value."""
    digits = [c for c in raw if c.isdigit()]
    if entity_type in {"CREDIT_CARD", "BANK_ACCOUNT", "IBAN_CODE"} and len(digits) >= 4:
        return "•••• " + "".join(digits[-4:])
    if entity_type == "EMAIL_ADDRESS" and "@" in raw:
        local, _, domain = raw.partition("@")
        return f"{local[:1]}•••@{domain}"
    if entity_type == "CREDENTIAL":
        return "••••••••"
    if entity_type == "SALARY_AMOUNT":
        return "<amount>"
    if entity_type == "PERSON":
        return raw[:1] + "•••"
    if digits:
        return "•" * max(len(digits) - 2, 1) + "".join(digits[-2:])
    return raw[:1] + "•••"


@dataclass
class RuleMatch:
    policy_id: int
    policy_name: str
    rule_id: int | None
    rule_name: str
    rule_type: str
    match_field: str
    action: str
    severity: str
    risk_category: str
    score: float
    evidence: str
    user_message: str = ""
    policy_version: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["score"] = round(self.score, 3)
        return d


@dataclass
class TopicScore:
    topic: str
    score: float
    signals: list[str]


@dataclass
class StageResult:
    """Outcome of one guardrail stage (input, context or output)."""

    stage: str
    action: str
    risk_score: float
    matches: list[RuleMatch] = field(default_factory=list)
    signals: dict = field(default_factory=dict)
    redaction_count: int = 0
    redacted_entity_types: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    @property
    def policy_ids(self) -> list[int]:
        return sorted({m.policy_id for m in self.matches})
