"""Action precedence, risk aggregation and input→output mapping."""

from __future__ import annotations

from app.guardrails.types import SEVERITY_ORDER, SEVERITY_WEIGHT, InputAction, OutputAction, RuleMatch

# Most restrictive first. ESCALATE is BLOCK plus a mandatory security/compliance review.
INPUT_PRECEDENCE = [InputAction.ESCALATE, InputAction.BLOCK, InputAction.REVIEW, InputAction.REDACT, InputAction.ALLOW]
OUTPUT_PRECEDENCE = [
    OutputAction.BLOCK, OutputAction.SEND_TO_REVIEW, OutputAction.REDACT, OutputAction.SHOW_WITH_WARNING, OutputAction.SHOW,
]

# On the output side a rule's action is translated. A triggered ALLOW rule means "allowed, but flagged".
RULE_TO_OUTPUT = {
    "BLOCK": OutputAction.BLOCK,
    "ESCALATE": OutputAction.SEND_TO_REVIEW,
    "REVIEW": OutputAction.SEND_TO_REVIEW,
    "REDACT": OutputAction.REDACT,
    "ALLOW": OutputAction.SHOW_WITH_WARNING,
}

SLA_HOURS = {"CRITICAL": 1, "HIGH": 4, "MEDIUM": 8, "LOW": 24}


def decide_input(matches: list[RuleMatch]) -> InputAction:
    actions = {InputAction(m.action) for m in matches}
    for action in INPUT_PRECEDENCE:
        if action in actions:
            return action
    return InputAction.ALLOW


def decide_output(matches: list[RuleMatch], forced: list[OutputAction] | None = None) -> OutputAction:
    actions = {RULE_TO_OUTPUT[m.action] for m in matches} | set(forced or [])
    for action in OUTPUT_PRECEDENCE:
        if action in actions:
            return action
    return OutputAction.SHOW


def aggregate_risk(matches: list[RuleMatch], baseline: float = 0.0) -> float:
    """Noisy-OR of severity-weighted match scores, floored by a baseline signal (e.g. injection score)."""
    remaining = 1.0
    for m in matches:
        remaining *= 1.0 - SEVERITY_WEIGHT.get(m.severity, 0.5) * min(1.0, m.score)
    return round(max(1.0 - remaining, baseline), 3)


def max_severity(matches: list[RuleMatch], default: str = "MEDIUM") -> str:
    if not matches:
        return default
    return max((m.severity for m in matches), key=SEVERITY_ORDER.index)


def trust_status_for(input_action: InputAction, output_action: OutputAction | None) -> str:
    """Employee-facing badge: verified | redacted | needs_review | blocked."""
    if input_action in (InputAction.BLOCK,):
        return "blocked"
    if input_action == InputAction.ESCALATE:
        return "needs_review"
    if output_action == OutputAction.BLOCK:
        return "blocked"
    if output_action == OutputAction.SEND_TO_REVIEW:
        return "needs_review"
    if output_action == OutputAction.REDACT or input_action == InputAction.REDACT:
        return "redacted"
    return "verified"
