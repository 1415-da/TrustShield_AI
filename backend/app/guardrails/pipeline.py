"""Guardrail stages: input → retrieved context → output.

`GuardrailEngine` is constructed per request from policy snapshots, so a draft (inactive) policy can be
injected for simulation without touching the live configuration.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field

from app.guardrails.decision import RULE_TO_OUTPUT, aggregate_risk, decide_input, decide_output
from app.guardrails.grounding import GroundingSignals, assess_grounding
from app.guardrails.pii import PIIDetector
from app.guardrails.rules import EvaluationContext, FieldAnalysis, PolicySnapshot, evaluate_policies
from app.guardrails.topics import classify_topics
from app.guardrails.types import STORAGE_MASKED_ENTITIES, Entity, InputAction, OutputAction, RuleMatch, StageResult


@dataclass
class Actor:
    """Who a request is evaluated for. May be a real user or a simulated role."""

    user_id: int | None
    email: str
    roles: set[str]
    permissions: set[str]
    primary_role: str


@dataclass
class ContextItem:
    index: int
    title: str
    text: str
    document_id: int | None = None
    chunk_id: int | None = None
    heading: str = ""
    score: float = 0.0
    kind: str = "policy"  # policy | directory
    trust_level: str = "trusted"

    def as_prompt_block(self) -> str:
        return f"[{self.index}] {self.title}{' — ' + self.heading if self.heading else ''}\n{self.text}"


@dataclass
class InputOutcome:
    stage: StageResult
    sanitized_prompt: str
    analysis: FieldAnalysis


@dataclass
class ContextOutcome:
    stage: StageResult
    kept: list[ContextItem]
    quarantined: list[ContextItem] = field(default_factory=list)


@dataclass
class OutputOutcome:
    stage: StageResult
    final_text: str
    grounding: GroundingSignals


def _mask_entities(pii: PIIDetector, text: str, entities: list[Entity], types: set[str]) -> tuple[str, list[Entity]]:
    targets = [e for e in entities if e.entity_type in types]
    return pii.anonymize(text, targets), targets


def _redaction_types(matches: list[RuleMatch], policies: list[PolicySnapshot]) -> set[str]:
    """Entity types named by matched REDACT rules (pii_entity or role_permission with entity_types)."""
    rule_index = {(p.id, r.id): r for p in policies for r in p.rules}
    types: set[str] = set()
    for m in matches:
        if m.action != "REDACT":
            continue
        rule = rule_index.get((m.policy_id, m.rule_id))
        if rule is not None:
            types.update(rule.entity_types)
    return types


class GuardrailEngine:
    def __init__(self, policies: list[PolicySnapshot], pii: PIIDetector, directory_names: list[str] | None = None) -> None:
        self.policies = policies
        self.pii = pii
        self.directory_names = directory_names or []

    def analyze(self, text: str, *, confidence: float | None = None) -> FieldAnalysis:
        entities = self.pii.analyze(text)
        topics = classify_topics(text, entities, self.directory_names)
        return FieldAnalysis(text=text, entities=entities, topics=topics, confidence=confidence)

    def _ctx(self, actor: Actor, field_name: str, analysis: FieldAnalysis) -> EvaluationContext:
        return EvaluationContext(roles=actor.roles, permissions=actor.permissions, fields={field_name: analysis})

    # ------------------------------------------------------------------ input
    def run_input(self, prompt: str, actor: Actor) -> InputOutcome:
        t0 = time.perf_counter()
        analysis = self.analyze(prompt)
        matches = evaluate_policies(self.policies, self._ctx(actor, "user_input", analysis), "user_input")
        action = decide_input(matches)

        # Baseline data minimisation: high-risk identifiers never leave the gateway unmasked,
        # plus whatever matched REDACT rules ask for.
        mask_types = set(STORAGE_MASKED_ENTITIES) | _redaction_types(matches, self.policies)
        sanitized, masked = _mask_entities(self.pii, prompt, analysis.entities, mask_types)
        notes: list[str] = []
        if masked and action == InputAction.ALLOW:
            action = InputAction.REDACT
            notes.append("baseline minimisation masked identifiers not covered by a policy")

        topics = analysis.topics
        injection = topics.score("prompt_injection") if topics else 0.0
        top_topic = max((v.score for k, v in topics.scores.items() if k != "prompt_injection"), default=0.0) if topics else 0.0
        stage = StageResult(
            stage="input",
            action=action.value,
            risk_score=aggregate_risk(matches, baseline=max(injection * 0.8, top_topic * 0.5)),
            matches=matches,
            signals={
                "entities": [e.public() for e in analysis.entities],
                "topics": topics.public() if topics else {},
                "targets_named_people": len(topics.target_people) if topics else 0,
                "injection_score": injection,
                "pii_engine": self.pii.engine_name,
                "notes": notes,
            },
            redaction_count=len(masked),
            redacted_entity_types=sorted({e.entity_type for e in masked}),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
        return InputOutcome(stage=stage, sanitized_prompt=sanitized, analysis=analysis)

    # ---------------------------------------------------------------- context
    def run_context(self, items: list[ContextItem], actor: Actor) -> ContextOutcome:
        """Scan retrieved chunks for indirect prompt injection or other rule hits; quarantine offenders."""
        t0 = time.perf_counter()
        kept, quarantined, matches = [], [], []
        redactions = 0
        for item in items:
            analysis = self.analyze(item.text)
            hits = evaluate_policies(self.policies, self._ctx(actor, "retrieved_context", analysis), "retrieved_context")
            for h in hits:
                h.evidence = f"source [{item.index}] '{item.title}': {h.evidence}"
            matches.extend(hits)
            if not hits:
                kept.append(item)
            elif all(h.action == "REDACT" for h in hits):
                # Sensitive values inside a knowledge source are masked before the model sees them.
                masked_text, masked = _mask_entities(self.pii, item.text, analysis.entities, _redaction_types(hits, self.policies))
                item.text = masked_text
                redactions += len(masked)
                kept.append(item)
            else:
                quarantined.append(item)
        # Re-number kept items so citations stay contiguous.
        for i, item in enumerate(kept, start=1):
            item.index = i
        action = decide_output(matches).value if matches else OutputAction.SHOW.value
        stage = StageResult(
            stage="context",
            action=action,
            risk_score=aggregate_risk(matches),
            matches=matches,
            signals={"retrieved": len(items), "quarantined": len(quarantined),
                     "quarantined_sources": [q.title for q in quarantined], "masked_values": redactions},
            redaction_count=redactions,
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
        return ContextOutcome(stage=stage, kept=kept, quarantined=quarantined)

    # ----------------------------------------------------------------- output
    def run_output(
        self,
        draft: str,
        *,
        query: str,
        context: list[ContextItem],
        actor: Actor,
        input_action: InputAction,
        input_risk: float,
        context_matches: list[RuleMatch] | None = None,
    ) -> OutputOutcome:
        t0 = time.perf_counter()
        retrieval_sim = max((c.score for c in context), default=0.0)
        evidence = [f"{c.title} {c.heading}\n{c.text}" for c in context]
        grounding = assess_grounding(query, draft, evidence, retrieval_sim, input_risk)
        analysis = self.analyze(draft, confidence=grounding.confidence)
        matches = evaluate_policies(self.policies, self._ctx(actor, "llm_output", analysis), "llm_output")

        forced: list[OutputAction] = []
        if input_action == InputAction.REVIEW:
            forced.append(OutputAction.SEND_TO_REVIEW)
        for cm in context_matches or []:
            forced.append(RULE_TO_OUTPUT[cm.action])
        action = decide_output(matches, forced)

        mask_types = set(STORAGE_MASKED_ENTITIES) | _redaction_types(matches, self.policies)
        final_text, masked = _mask_entities(self.pii, draft, analysis.entities, mask_types)
        if masked and action in (OutputAction.SHOW, OutputAction.SHOW_WITH_WARNING):
            action = OutputAction.REDACT

        stage = StageResult(
            stage="output",
            action=action.value,
            risk_score=aggregate_risk(matches, baseline=round((1 - grounding.confidence) * 0.5, 3)),
            matches=matches,
            signals={
                "entities": [e.public() for e in analysis.entities],
                "topics": analysis.topics.public() if analysis.topics else {},
                "grounding": grounding.public(),
                "forced": [f.value for f in forced],
            },
            redaction_count=len(masked),
            redacted_entity_types=sorted({e.entity_type for e in masked}),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
        return OutputOutcome(stage=stage, final_text=final_text, grounding=grounding)

    def mask_for_storage(self, text: str) -> tuple[str, Counter]:
        entities = self.pii.analyze(text)
        masked_text, masked = _mask_entities(self.pii, text, entities, set(STORAGE_MASKED_ENTITIES))
        return masked_text, Counter(e.entity_type for e in masked)
