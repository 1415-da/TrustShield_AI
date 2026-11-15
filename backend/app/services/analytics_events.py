"""Categorical analytics context safe to expose to the frontend.

This module deliberately emits no prompts, answers, policy names, employee IDs, or raw scores.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

ROLES = {
    "employee", "hr_manager", "finance_analyst", "people_manager", "finance_head", "security_admin",
    "compliance_reviewer", "security_auditor", "trustshield_admin",
}


def _risk_tier(score: float | int | None) -> str:
    if score is None:
        return "unknown"
    value = max(0.0, min(1.0, float(score)))
    if value < 0.25:
        return "low"
    if value < 0.5:
        return "medium"
    if value < 0.75:
        return "high"
    return "critical"


def _confidence_bucket(value: float | int | None) -> str:
    if value is None:
        return "unknown"
    score = float(value)
    if score < 0.55:
        return "under_0_55"
    if score < 0.75:
        return "0_55_to_0_74"
    if score < 0.9:
        return "0_75_to_0_89"
    return "0_90_plus"


def _latency_bucket(value: float | int | None) -> str:
    if value is None:
        return "unknown"
    ms = max(0.0, float(value))
    if ms < 1000:
        return "under_1s"
    if ms < 3000:
        return "1_3s"
    if ms < 10000:
        return "3_10s"
    return "10s_plus"


def _policy_category(match: Any) -> str | None:
    if isinstance(match, dict):
        risk = str(match.get("risk_category", "")).lower()
        hint = f"{match.get('policy_name', '')} {match.get('rule_name', '')}".lower()
    else:
        risk = str(getattr(match, "risk_category", "")).lower()
        hint = f"{getattr(match, 'policy_name', '')} {getattr(match, 'rule_name', '')}".lower()
    if risk == "pii":
        return "pii_protection"
    if risk == "compensation":
        return "compensation_confidentiality"
    if risk == "financial_data":
        if any(term in hint for term in ("bank", "account", "ifsc")):
            return "bank_account_confidentiality"
        if any(term in hint for term in ("card", "credit")):
            return "payment_card_data"
        return "finance_channel_controls"
    if risk == "credentials":
        return "credential_protection"
    if risk == "prompt_injection":
        return "system_prompt_leakage" if "system prompt" in hint else "prompt_injection"
    if risk == "data_exfiltration":
        return "bulk_exfiltration"
    if risk == "legal":
        return "legal_routing"
    if risk == "quality":
        return "grounding_confidence"
    return None


def analytics_metadata(
    *, workspace_id: int | str | None, user_role: str | None, surface: str, input_action: str | None,
    trust_status: str | None, input_risk_score: float | None = None, output_risk_score: float | None = None,
    confidence: float | None = None, citation_count: int = 0, model_called: bool = False,
    latency_ms: float | None = None, matches: Iterable[Any] = (), simulation_role: str | None = None,
) -> dict[str, Any]:
    action = (input_action or "").upper()
    if action == "ESCALATE":
        decision = "escalate"
    elif trust_status == "blocked":
        decision = "block"
    elif trust_status == "redacted":
        decision = "redact"
    elif trust_status == "needs_review":
        decision = "review"
    else:
        decision = "allow"
    categories = sorted({category for match in matches if (category := _policy_category(match))})
    result: dict[str, Any] = {
        "surface": surface, "decision": decision, "input_risk_tier": _risk_tier(input_risk_score),
        "output_risk_tier": _risk_tier(output_risk_score), "confidence_bucket": _confidence_bucket(confidence),
        "citation_count": max(0, min(100, int(citation_count))), "response_time_bucket": _latency_bucket(latency_ms),
        "model_called": bool(model_called),
    }
    if workspace_id is not None:
        result["workspace_id"] = f"ws_{workspace_id}"
    if user_role in ROLES:
        result["user_role"] = user_role
    if simulation_role in ROLES:
        result["simulation_role"] = simulation_role
    if trust_status in {"verified", "redacted", "needs_review", "blocked"}:
        result["trust_status"] = trust_status
    if categories:
        result["policy_categories"] = categories
    return result
