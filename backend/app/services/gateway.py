"""TrustShield gateway: orchestrates one request through every guardrail stage.

    input guardrails ──► (BLOCK / ESCALATE: stop — the LLM is never called)
          │
          ▼
    retrieval ──► context guardrails (quarantine injected chunks) ──► LLM ──► output guardrails
          │
          ▼
    persistence: masked messages, guardrail decisions, review case, hash-chained audit event

The same `process` function serves live chat (persist=True), the policy simulator and the evaluation
harness (persist=False), and the seed script (persist=True with a back-dated clock).
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import sha256_hex
from app.guardrails.decision import SLA_HOURS, max_severity, trust_status_for
from app.guardrails.grounding import GroundingSignals
from app.guardrails.pii import get_pii_detector
from app.guardrails.pipeline import Actor, ContextItem, GuardrailEngine
from app.guardrails.rules import PolicySnapshot
from app.guardrails.types import InputAction, OutputAction, RuleMatch, StageResult
from app.models import ConnectedApp, Conversation, GuardrailDecision, Message, ReviewCase, User
from app.models.base import utcnow
from app.services import audit, directory, policies, retrieval
from app.services.llm import LLMError, LLMProvider, get_provider

REVIEW_HOLDING_MESSAGE = (
    "Your request is being checked by NovaCorp's compliance team before an answer is shared. "
    "You'll see the reviewed answer here as soon as it's ready."
)
ESCALATION_MESSAGE = (
    "This request has been paused and escalated to NovaCorp's security and compliance team. "
    "It was not sent to the AI model. Someone will follow up if action is needed."
)
OUTPUT_BLOCK_MESSAGE = (
    "An answer was generated, but TrustShield withheld it because it contained information that can't be "
    "shared through the assistant. No sensitive data was shown."
)
FALLBACK_REJECTED = (
    "After review, the compliance team was unable to approve an answer to this request through the assistant. "
    "Please contact the relevant policy owner directly."
)

SUGGESTIONS = {
    "compensation": "For questions about your own pay, contact your HR Business Partner.",
    "salary": "For questions about your own pay, contact your HR Business Partner.",
    "financial_data": "Card and bank details are only handled through the Finance Operations portal.",
    "credentials": "Use the IT self-service portal to reset passwords or request access. Never share credentials.",
    "prompt_injection": "Rephrase your question as a normal request about NovaCorp policy.",
    "data_exfiltration": "Bulk data requests must go through a Data Access Request with the Privacy Office.",
    "pii": "Personal details of colleagues are only available through the HR system to authorised staff.",
    "legal": "For legal questions, the Legal team can advise on your specific situation.",
}


@dataclass
class GatewayResult:
    request_id: str
    input_stage: StageResult
    context_stage: StageResult | None
    output_stage: StageResult | None
    input_action: InputAction
    output_action: OutputAction | None
    trust_status: str
    message_status: str
    final_text: str
    sanitized_prompt: str
    citations: list[dict] = field(default_factory=list)
    explanation: dict[str, Any] = field(default_factory=dict)
    grounding: GroundingSignals | None = None
    draft_masked: str | None = None
    llm_called: bool = False
    provider: str | None = None
    model: str | None = None
    latency_ms: float = 0.0
    conversation_id: int | None = None
    user_message_id: int | None = None
    assistant_message_id: int | None = None
    review_case_id: int | None = None

    @property
    def all_matches(self) -> list[RuleMatch]:
        out = list(self.input_stage.matches)
        for st in (self.context_stage, self.output_stage):
            if st:
                out.extend(st.matches)
        return out

    @property
    def redaction_count(self) -> int:
        return self.input_stage.redaction_count + (self.output_stage.redaction_count if self.output_stage else 0)


def actor_from_user(user: User) -> Actor:
    return Actor(user.id, user.email, set(user.role_keys), set(user.permissions), user.primary_role)


# --------------------------------------------------------------------------- helpers
def _dedupe_policies(matches: list[RuleMatch]) -> list[dict]:
    seen: dict[int, dict] = {}
    for m in matches:
        if m.policy_id not in seen:
            seen[m.policy_id] = {"id": m.policy_id, "name": m.policy_name, "severity": m.severity,
                                 "category": m.risk_category, "reason": m.user_message}
    return list(seen.values())


def _explain(
    input_stage: StageResult, output_stage: StageResult | None, context_stage: StageResult | None,
    trust_status: str, grounding: GroundingSignals | None,
) -> dict[str, Any]:
    """Plain-language explanation for the employee. No regex evidence or raw values."""
    restrictive_input = [m for m in input_stage.matches if m.action in ("BLOCK", "ESCALATE", "REVIEW")]
    out_matches = output_stage.matches if output_stage else []
    ctx_matches = context_stage.matches if context_stage else []
    primary = restrictive_input or [m for m in out_matches if m.action in ("BLOCK", "REVIEW", "ESCALATE")] or ctx_matches or out_matches or input_stage.matches
    policies_ = _dedupe_policies(primary)
    redactions = Counter(input_stage.redacted_entity_types)
    if output_stage:
        redactions.update(output_stage.redacted_entity_types)

    headline = {
        "blocked": "This request was blocked by a NovaCorp AI policy",
        "needs_review": "This answer is waiting for human review",
        "redacted": "Sensitive information was masked",
        "verified": "Answer supported by NovaCorp policy documents",
    }[trust_status]
    if input_stage.action == "ESCALATE":
        headline = "This request was escalated to security and compliance"
    elif output_stage and output_stage.action == "BLOCK":
        headline = "The generated answer was withheld"

    warning = None
    if output_stage and output_stage.action == OutputAction.SHOW_WITH_WARNING.value:
        warning = "Limited supporting evidence was found for parts of this answer. Confirm with the policy owner before acting."
    if context_stage and context_stage.signals.get("quarantined"):
        warning = "A knowledge source contained suspicious instructions and was excluded from this answer."

    category = policies_[0]["category"] if policies_ else None
    return {
        "headline": headline,
        "detail": policies_[0]["reason"] if policies_ and policies_[0]["reason"] else None,
        "policies": policies_ if trust_status != "verified" or warning else [],
        "redactions": [{"entity_type": k, "count": v} for k, v in redactions.items()],
        "warning": warning,
        "suggestion": SUGGESTIONS.get(category or "") if trust_status in ("blocked", "needs_review") else None,
        "confidence": grounding.confidence if grounding else None,
        "groundedness": grounding.groundedness if grounding else None,
        "confidence_label": "Risk signal, not a guarantee",
        "quarantined_sources": context_stage.signals.get("quarantined", 0) if context_stage else 0,
    }


def _citations(engine: GuardrailEngine, items: list[ContextItem], text: str) -> list[dict]:
    cited = {i.index for i in items if f"[{i.index}]" in text}
    chosen = [i for i in items if i.index in cited] or items[:3]
    out = []
    for i in chosen:
        snippet, _ = engine.mask_for_storage(i.text[:280])
        out.append({
            "index": i.index, "title": i.title, "heading": i.heading, "document_id": i.document_id,
            "chunk_id": i.chunk_id, "kind": i.kind, "score": round(i.score, 3), "snippet": snippet,
            "cited": i.index in cited,
        })
    return out


def _build_context(db: Session, engine: GuardrailEngine, actor: Actor, query: str, target_people: list[str]) -> list[ContextItem]:
    items: list[ContextItem] = []
    for rec in directory.lookup(db, target_people):
        items.append(ContextItem(index=0, title=directory.DIRECTORY_TITLE, text=directory.describe(rec, actor.permissions),
                                 kind="directory", score=0.9, heading=rec.full_name))
    for r in retrieval.search(db, query):
        c = r.chunk
        items.append(ContextItem(index=0, title=c.title, text=c.text, document_id=c.document_id, chunk_id=c.chunk_id,
                                 heading=c.heading, score=r.score, trust_level=c.trust_level))
    for i, item in enumerate(items, start=1):
        item.index = i
    return items


# --------------------------------------------------------------------------- main entry
def process(
    db: Session,
    *,
    actor: Actor,
    prompt: str,
    app: ConnectedApp | None = None,
    conversation_id: int | None = None,
    persist: bool = True,
    extra_policies: list[PolicySnapshot] | None = None,
    provider: LLMProvider | None = None,
    now: datetime | None = None,
    source: str = "assistant",
) -> GatewayResult:
    t0 = time.perf_counter()
    request_id = uuid.uuid4().hex
    snapshots = policies.active_snapshots(db, include=extra_policies)
    engine = GuardrailEngine(snapshots, get_pii_detector(), directory.directory_names(db))

    inp = engine.run_input(prompt, actor)
    input_action = InputAction(inp.stage.action)
    context_stage = output_stage = None
    grounding = None
    citations: list[dict] = []
    draft_masked: str | None = None
    llm_called = False
    provider_name = model_name = None

    if input_action in (InputAction.BLOCK, InputAction.ESCALATE):
        output_action = None
        trust_status = trust_status_for(input_action, None)
        final_text = ESCALATION_MESSAGE if input_action == InputAction.ESCALATE else _block_text(inp.stage.matches)
    else:
        provider = provider or get_provider()
        targets = inp.analysis.topics.target_people if inp.analysis.topics else []
        items = _build_context(db, engine, actor, inp.sanitized_prompt, targets)
        ctx = engine.run_context(items, actor)
        context_stage = ctx.stage
        try:
            llm = provider.generate(inp.sanitized_prompt, [i.as_prompt_block() for i in ctx.kept])
        except LLMError as exc:
            if persist:
                audit.record(db, "assistant.provider_error", request_id=request_id, actor_user_id=actor.user_id,
                             actor_email=actor.email, actor_role=actor.primary_role, model_provider=provider.name,
                             model_name=provider.model, details={"error": str(exc)}, commit=True)
            raise AppError(502, "llm_unavailable", "The AI model is temporarily unavailable. Please try again shortly.") from exc
        llm_called = True
        provider_name, model_name = llm.provider, llm.model
        out = engine.run_output(
            llm.text, query=inp.sanitized_prompt, context=ctx.kept, actor=actor, input_action=input_action,
            input_risk=inp.stage.risk_score, context_matches=ctx.stage.matches,
        )
        output_stage, grounding = out.stage, out.grounding
        output_action = OutputAction(out.stage.action)
        trust_status = trust_status_for(input_action, output_action)
        draft_masked = out.final_text
        citations = _citations(engine, ctx.kept, out.final_text)
        if output_action == OutputAction.BLOCK:
            final_text, citations = OUTPUT_BLOCK_MESSAGE, []
        elif output_action == OutputAction.SEND_TO_REVIEW:
            final_text = REVIEW_HOLDING_MESSAGE
        else:
            final_text = out.final_text

    message_status = {"blocked": "blocked", "needs_review": "pending_review"}.get(trust_status, "delivered")
    result = GatewayResult(
        request_id=request_id, input_stage=inp.stage, context_stage=context_stage, output_stage=output_stage,
        input_action=input_action, output_action=output_action, trust_status=trust_status,
        message_status=message_status, final_text=final_text, sanitized_prompt=inp.sanitized_prompt,
        citations=citations if trust_status != "needs_review" else [], grounding=grounding, draft_masked=draft_masked,
        llm_called=llm_called, provider=provider_name, model=model_name,
    )
    result.explanation = _explain(inp.stage, output_stage, context_stage, trust_status, grounding)
    result.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    if persist:
        _persist(db, result, actor=actor, prompt=prompt, app=app, conversation_id=conversation_id,
                 now=now or utcnow(), source=source, review_sources=citations)
    return result


def _block_text(matches: list[RuleMatch]) -> str:
    blocking = [m for m in matches if m.action == "BLOCK"] or matches
    names = ", ".join(dict.fromkeys(m.policy_name for m in blocking[:2]))
    return f"I can't help with that request. It conflicts with NovaCorp's {names}."


# --------------------------------------------------------------------------- persistence
def _persist(
    db: Session, r: GatewayResult, *, actor: Actor, prompt: str, app: ConnectedApp | None,
    conversation_id: int | None, now: datetime, source: str, review_sources: list[dict],
) -> None:
    conv = db.get(Conversation, conversation_id) if conversation_id else None
    if conv is None or conv.user_id != actor.user_id:
        title = r.sanitized_prompt.strip().replace("\n", " ")
        conv = Conversation(user_id=actor.user_id, app_id=app.id if app else None,
                            title=(title[:72] + "…") if len(title) > 72 else title, created_at=now, updated_at=now)
        db.add(conv)
        db.flush()
    conv.updated_at = now

    user_msg = Message(conversation_id=conv.id, role="user", content=r.sanitized_prompt, content_hash=sha256_hex(prompt),
                       request_id=r.request_id, created_at=now, updated_at=now)
    assistant_msg = Message(
        conversation_id=conv.id, role="assistant", content=r.final_text, content_hash=sha256_hex(r.final_text),
        status=r.message_status, trust_status=r.trust_status, request_id=r.request_id, explanation=r.explanation,
        citations=r.citations, created_at=now + timedelta(seconds=1), updated_at=now + timedelta(seconds=1),
    )
    db.add_all([user_msg, assistant_msg])
    db.flush()

    for stage in (r.input_stage, r.context_stage, r.output_stage):
        if stage is None:
            continue
        db.add(GuardrailDecision(
            request_id=r.request_id, message_id=assistant_msg.id, stage=stage.stage, action=stage.action,
            risk_score=stage.risk_score, signals=stage.signals, matches=[m.to_dict() for m in stage.matches],
            redaction_count=stage.redaction_count, latency_ms=stage.latency_ms, created_at=now,
        ))

    case = None
    if r.trust_status == "needs_review":
        all_matches = r.all_matches
        escalated = r.input_action == InputAction.ESCALATE
        severity = "CRITICAL" if escalated else max_severity(
            [m for m in all_matches if m.action in ("REVIEW", "ESCALATE", "BLOCK")] or all_matches, default="MEDIUM")
        low_conf = bool(r.output_stage and any(m.rule_type == "confidence_threshold" for m in r.output_stage.matches))
        reasons = [m.policy_name for m in all_matches if m.action in ("REVIEW", "ESCALATE", "BLOCK")]
        if low_conf:
            reasons.append("Low grounding confidence")
        case = ReviewCase(
            request_id=r.request_id, conversation_id=conv.id, user_message_id=user_msg.id,
            assistant_message_id=assistant_msg.id, requester_id=actor.user_id, requester_role=actor.primary_role,
            status="ESCALATED" if escalated else "PENDING", priority=severity,
            origin="escalation" if escalated else ("input" if r.input_action == InputAction.REVIEW else "output"),
            reason="; ".join(dict.fromkeys(reasons)) or "Flagged for review",
            risk_score=max(r.input_stage.risk_score, r.output_stage.risk_score if r.output_stage else 0.0),
            confidence=r.grounding.confidence if r.grounding else None,
            policy_matches=[m.to_dict() for m in all_matches], prompt_masked=r.sanitized_prompt,
            draft_response=r.draft_masked, suggested_action=_suggest(r, escalated, low_conf),
            sources=review_sources, signals={"grounding": r.grounding.public() if r.grounding else None,
                                             "input": r.input_stage.signals.get("topics", {})},
            sla_due_at=now + timedelta(hours=SLA_HOURS.get(severity, 8)), created_at=now,
        )
        db.add(case)
        db.flush()
        r.review_case_id = case.id

    final_action = r.output_action.value if r.output_action else r.input_action.value
    audit.record(
        db, f"{source}.request", created_at=now, request_id=r.request_id, actor_user_id=actor.user_id,
        actor_email=actor.email, actor_role=actor.primary_role, app_id=app.id if app else None,
        policy_ids=sorted({m.policy_id for m in r.all_matches}), input_risk_score=r.input_stage.risk_score,
        output_risk_score=r.output_stage.risk_score if r.output_stage else None, input_action=r.input_action.value,
        output_action=r.output_action.value if r.output_action else None, final_action=final_action,
        redaction_count=r.redaction_count, review_case_id=case.id if case else None, model_provider=r.provider,
        model_name=r.model, latency_ms=r.latency_ms, content_hash=sha256_hex(prompt),
        details={
            "trust_status": r.trust_status, "llm_called": r.llm_called, "prompt_masked": r.sanitized_prompt[:500],
            "redacted_types": sorted(set(r.input_stage.redacted_entity_types) | set(r.output_stage.redacted_entity_types if r.output_stage else [])),
            "confidence": r.grounding.confidence if r.grounding else None,
            "rules": [f"{m.policy_name} › {m.rule_name}" for m in r.all_matches][:12],
            "quarantined_sources": r.context_stage.signals.get("quarantined", 0) if r.context_stage else 0,
        },
    )
    db.commit()
    r.conversation_id, r.user_message_id, r.assistant_message_id = conv.id, user_msg.id, assistant_msg.id


def _suggest(r: GatewayResult, escalated: bool, low_conf: bool) -> str:
    if escalated:
        return "REJECT"
    if r.context_stage and r.context_stage.signals.get("quarantined"):
        return "EDIT"
    if low_conf:
        return "EDIT"
    return "APPROVE"


def generate_for_review(db: Session, actor: Actor, sanitized_prompt: str) -> tuple[str, list[dict], str]:
    """Generate a response for an escalated case a reviewer approved. Output guardrails still apply.

    Returns (text, citations, output_action).
    """
    engine = GuardrailEngine(policies.active_snapshots(db), get_pii_detector(), directory.directory_names(db))
    items = _build_context(db, engine, actor, sanitized_prompt, [])
    ctx = engine.run_context(items, actor)
    llm = get_provider().generate(sanitized_prompt, [i.as_prompt_block() for i in ctx.kept])
    out = engine.run_output(llm.text, query=sanitized_prompt, context=ctx.kept, actor=actor,
                            input_action=InputAction.ALLOW, input_risk=0.0, context_matches=ctx.stage.matches)
    if out.stage.action == OutputAction.BLOCK.value:
        return OUTPUT_BLOCK_MESSAGE, [], out.stage.action
    return out.final_text, _citations(engine, ctx.kept, out.final_text), out.stage.action
