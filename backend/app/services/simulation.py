"""Policy simulation (dry run, nothing persisted).

* `simulate` — one prompt, one role, with an optional focus policy (a draft version, an inactive version, or an
  unsaved definition) forced active in place of that family's live version.
* `impact_analysis` — replays the evaluation suite with and without the focus policy and lists every scenario whose
  decision would change. Shown to approvers next to the diff.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.guardrails.pii import get_pii_detector
from app.guardrails.pipeline import GuardrailEngine
from app.guardrails.rules import PolicySnapshot
from app.guardrails.types import StageResult
from app.models import TestCase
from app.models.base import utcnow
from app.services import directory, gateway, policies
from app.services.evaluation import actor_for_role

DRAFT_POLICY_ID = -1


def draft_snapshot(data: dict[str, Any], policy_id: int = DRAFT_POLICY_ID) -> PolicySnapshot:
    definition = policies.normalize_definition(data)
    if policy_id == DRAFT_POLICY_ID:
        definition = {**definition, "name": definition["name"] + " (draft)"}
    return PolicySnapshot.from_definition(policy_id, definition, version=0, active=True)


def _stage(st: StageResult | None) -> dict | None:
    if st is None:
        return None
    return {"stage": st.stage, "action": st.action, "risk_score": st.risk_score, "matches": [m.to_dict() for m in st.matches],
            "signals": st.signals, "redaction_count": st.redaction_count, "redacted_entity_types": st.redacted_entity_types,
            "latency_ms": st.latency_ms}


def simulate(db: Session, *, prompt: str, role: str, include_output: bool = True, focus: PolicySnapshot | None = None,
             profile: str | None = None) -> dict:
    actor = dataclasses.replace(actor_for_role(db, role), profile=profile)
    extra = [dataclasses.replace(focus, is_active=True)] if focus else None
    if include_output:
        r = gateway.process(db, actor=actor, prompt=prompt, persist=False, extra_policies=extra)
        stages = [r.input_stage, r.context_stage, r.output_stage]
        final = {"input_action": r.input_action.value, "output_action": r.output_action.value if r.output_action else None,
                 "trust_status": r.trust_status, "llm_called": r.llm_called, "response_preview": r.final_text,
                 "explanation": r.explanation, "citations": r.citations}
        sanitized = r.sanitized_prompt
    else:
        engine = GuardrailEngine(policies.active_snapshots(db, include=extra), get_pii_detector(), directory.directory_names(db))
        inp = engine.run_input(prompt, actor)
        stages = [inp.stage, None, None]
        final = {"input_action": inp.stage.action, "output_action": None, "trust_status": None, "llm_called": False,
                 "response_preview": None, "explanation": None, "citations": []}
        sanitized = inp.sanitized_prompt
    focus_matches = [m.to_dict() for st in stages if st for m in st.matches if focus and m.policy_id == focus.id]
    return {
        "role": role,
        "role_permissions": sorted(actor.permissions),
        "profile": profile,
        "sanitized_prompt": sanitized,
        "input": _stage(stages[0]),
        "context": _stage(stages[1]),
        "output": _stage(stages[2]),
        "final": final,
        "focus_policy": {"id": focus.id, "name": focus.name, "version": focus.version, "triggered": bool(focus_matches),
                         "matches": focus_matches} if focus else None,
    }


def impact_analysis(db: Session, focus: PolicySnapshot) -> dict:
    """Run every active evaluation scenario twice — live policies vs. live policies with `focus` — and diff outcomes."""
    cases = list(db.scalars(select(TestCase).where(TestCase.is_active.is_(True)).order_by(TestCase.code)))
    forced = [dataclasses.replace(focus, is_active=True)]
    changed, triggered = [], 0
    for tc in cases:
        actor = actor_for_role(db, tc.role_key)
        before = gateway.process(db, actor=actor, prompt=tc.prompt, persist=False)
        after = gateway.process(db, actor=actor, prompt=tc.prompt, persist=False, extra_policies=forced)
        hit = any(m.policy_id == focus.id for m in after.all_matches)
        triggered += int(hit)
        b = (before.input_action.value, before.output_action.value if before.output_action else None, before.trust_status)
        a = (after.input_action.value, after.output_action.value if after.output_action else None, after.trust_status)
        if b != a:
            changed.append({"code": tc.code, "category": tc.category, "role": tc.role_key, "prompt": tc.prompt,
                            "before": {"input": b[0], "output": b[1], "trust_status": b[2]},
                            "after": {"input": a[0], "output": a[1], "trust_status": a[2]},
                            "expected_input": tc.expected_input_actions, "expected_output": tc.expected_output_actions,
                            "now_matches_expectation": a[0] in tc.expected_input_actions and
                            (not tc.expected_output_actions or a[1] in tc.expected_output_actions)})
    return {"computed_at": utcnow().isoformat() + "Z", "scenarios": len(cases), "triggered": triggered,
            "changed": changed, "regressions": sum(1 for c in changed if not c["now_matches_expectation"])}
