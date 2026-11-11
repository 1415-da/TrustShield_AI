"""Generic policy-rule evaluator.

Policies are loaded from the database into immutable snapshots (`PolicySnapshot`) so the evaluator is a
pure function of (policies, context). No business rule is hardcoded here — only the *semantics* of the
six rule types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.guardrails.topics import TopicAnalysis
from app.guardrails.types import Entity, RuleMatch


@dataclass(frozen=True)
class RuleSnapshot:
    id: int | None
    name: str
    rule_type: str
    match_field: str
    pattern: str | None = None
    keywords: tuple[str, ...] = ()
    entity_types: tuple[str, ...] = ()
    topic: str | None = None
    required_permission: str | None = None
    threshold: float | None = None
    action: str | None = None
    severity: str | None = None
    applies_to_roles: tuple[str, ...] = ()
    is_active: bool = True


@dataclass(frozen=True)
class PolicySnapshot:
    id: int
    name: str
    risk_category: str
    action: str
    severity: str
    threshold: float
    user_message: str
    applicable_roles: tuple[str, ...]
    is_active: bool
    rules: tuple[RuleSnapshot, ...]
    version: int = 0
    profiles: tuple[str, ...] = ()  # channel policy profiles this policy is scoped to; empty = everywhere

    @classmethod
    def from_definition(cls, policy_id: int, definition: dict[str, Any], version: int = 0, active: bool = True) -> "PolicySnapshot":
        """Build an enforceable snapshot from a version's immutable definition dict."""
        return cls(
            id=policy_id,
            name=definition["name"],
            risk_category=definition.get("risk_category", "other"),
            action=definition["action"],
            severity=definition.get("severity", "MEDIUM"),
            threshold=float(definition.get("threshold", 0.5)),
            user_message=definition.get("user_message") or "",
            applicable_roles=tuple(definition.get("applicable_roles") or ()),
            is_active=active,
            version=version,
            profiles=tuple(definition.get("profiles") or ()),
            rules=tuple(
                RuleSnapshot(
                    id=i + 1, name=r.get("name") or r["rule_type"], rule_type=r["rule_type"],
                    match_field=r.get("match_field", "user_input"), pattern=r.get("pattern"),
                    keywords=tuple(r.get("keywords") or ()), entity_types=tuple(r.get("entity_types") or ()),
                    topic=r.get("topic"), required_permission=r.get("required_permission"), threshold=r.get("threshold"),
                    action=r.get("action"), severity=r.get("severity"), applies_to_roles=tuple(r.get("applies_to_roles") or ()),
                    is_active=r.get("is_active", True),
                )
                for i, r in enumerate(definition.get("rules") or [])
            ),
        )

    @classmethod
    def from_version(cls, version: Any) -> "PolicySnapshot":
        return cls.from_definition(version.policy_id, version.snapshot, version.version, active=True)


@dataclass
class FieldAnalysis:
    """Pre-computed analysis of one text field (prompt, retrieved chunk, or LLM draft)."""

    text: str
    entities: list[Entity] = field(default_factory=list)
    topics: TopicAnalysis | None = None
    confidence: float | None = None  # only for llm_output


@dataclass
class EvaluationContext:
    roles: set[str]
    permissions: set[str]
    fields: dict[str, FieldAnalysis]
    profile: str | None = None  # channel policy profile (e.g. "finance") for workspace / Slack traffic


def _roles_apply(required: tuple[str, ...], roles: set[str]) -> bool:
    return not required or bool(set(required) & roles)


def _entities_over(analysis: FieldAnalysis, types: tuple[str, ...], threshold: float) -> list[Entity]:
    wanted = set(types)
    return [e for e in analysis.entities if (not wanted or e.entity_type in wanted) and e.score >= threshold]


def _safe_regex(pattern: str, text: str) -> re.Match[str] | None:
    try:
        return re.search(pattern, text, re.IGNORECASE)
    except re.error:
        return None


def evaluate_rule(policy: PolicySnapshot, rule: RuleSnapshot, ctx: EvaluationContext) -> RuleMatch | None:
    analysis = ctx.fields.get(rule.match_field)
    if analysis is None or not analysis.text and rule.rule_type != "confidence_threshold":
        return None
    threshold = rule.threshold if rule.threshold is not None else policy.threshold
    score: float | None = None
    evidence = ""

    if rule.rule_type == "regex" and rule.pattern:
        m = _safe_regex(rule.pattern, analysis.text)
        if m:
            score, evidence = 1.0, f"pattern matched ({len(m.group(0))} chars)"
    elif rule.rule_type == "keyword" and rule.keywords:
        hits = [k for k in rule.keywords if re.search(rf"\b{re.escape(k)}\b", analysis.text, re.IGNORECASE)]
        if hits:
            score, evidence = 1.0, "keywords: " + ", ".join(hits[:5])
    elif rule.rule_type == "pii_entity":
        ents = _entities_over(analysis, rule.entity_types, threshold)
        if ents:
            score = max(e.score for e in ents)
            evidence = ", ".join(f"{e.entity_type} {e.masked}" for e in ents[:5])
    elif rule.rule_type == "topic" and rule.topic and analysis.topics:
        ts = analysis.topics.scores.get(rule.topic)
        if ts and ts.score >= threshold:
            score = ts.score
            evidence = f"topic {rule.topic}={ts.score:.2f} [{', '.join(ts.signals[:4])}]"
    elif rule.rule_type == "role_permission" and rule.required_permission:
        if rule.required_permission in ctx.permissions:
            return None
        if rule.topic and analysis.topics:
            ts = analysis.topics.scores.get(rule.topic)
            if ts and ts.score >= threshold:
                score = ts.score
                evidence = f"topic {rule.topic}={ts.score:.2f} without scope {rule.required_permission}"
        if score is None and rule.entity_types:
            ents = _entities_over(analysis, rule.entity_types, threshold)
            if ents:
                score = max(e.score for e in ents)
                evidence = f"{', '.join(sorted({e.entity_type for e in ents}))} without scope {rule.required_permission}"
    elif rule.rule_type == "confidence_threshold" and analysis.confidence is not None:
        if analysis.confidence < threshold:
            score = round(1.0 - analysis.confidence, 3)
            evidence = f"confidence {analysis.confidence:.2f} < {threshold:.2f}"

    if score is None:
        return None
    return RuleMatch(
        policy_id=policy.id,
        policy_name=policy.name,
        rule_id=rule.id,
        rule_name=rule.name,
        rule_type=rule.rule_type,
        match_field=rule.match_field,
        action=rule.action or policy.action,
        severity=rule.severity or policy.severity,
        risk_category=policy.risk_category,
        score=score,
        evidence=evidence,
        user_message=policy.user_message,
        policy_version=policy.version,
    )


def evaluate_policies(policies: list[PolicySnapshot], ctx: EvaluationContext, match_field: str) -> list[RuleMatch]:
    matches: list[RuleMatch] = []
    for policy in policies:
        if not policy.is_active or not _roles_apply(policy.applicable_roles, ctx.roles):
            continue
        if policy.profiles and ctx.profile not in policy.profiles:
            continue
        for rule in policy.rules:
            if not rule.is_active or rule.match_field != match_field or not _roles_apply(rule.applies_to_roles, ctx.roles):
                continue
            match = evaluate_rule(policy, rule, ctx)
            if match:
                matches.append(match)
    return matches
