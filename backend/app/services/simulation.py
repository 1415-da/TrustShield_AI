"""Policy simulation: run a prompt through the real gateway in dry-run mode for a chosen role,
optionally including an inactive or unsaved policy, and report exactly which rules fire."""

from __future__ import annotations

import dataclasses
from typing import Any

from sqlalchemy.orm import Session

from app.guardrails.pii import get_pii_detector
from app.guardrails.pipeline import GuardrailEngine
from app.guardrails.rules import PolicySnapshot, RuleSnapshot
from app.guardrails.types import StageResult
from app.services import directory, gateway, policies
from app.services.evaluation import actor_for_role

DRAFT_POLICY_ID = -1


def draft_snapshot(data: dict[str, Any]) -> PolicySnapshot:
    return PolicySnapshot(
        id=DRAFT_POLICY_ID, name=data["name"] + " (draft)", risk_category=data["risk_category"], action=data["action"],
        severity=data.get("severity", "MEDIUM"), threshold=data.get("threshold", 0.5), user_message=data.get("user_message", ""),
        applicable_roles=tuple(data.get("applicable_roles") or ()), is_active=True,
        rules=tuple(
            RuleSnapshot(id=-(i + 1), name=r.get("name") or r["rule_type"], rule_type=r["rule_type"], match_field=r["match_field"],
                         pattern=r.get("pattern"), keywords=tuple(r.get("keywords") or ()),
                         entity_types=tuple(r.get("entity_types") or ()), topic=r.get("topic"),
                         required_permission=r.get("required_permission"), threshold=r.get("threshold"), action=r.get("action"),
                         severity=r.get("severity"), applies_to_roles=tuple(r.get("applies_to_roles") or ()),
                         is_active=r.get("is_active", True))
            for i, r in enumerate(data["rules"])
        ),
    )


def _stage(st: StageResult | None) -> dict | None:
    if st is None:
        return None
    return {"stage": st.stage, "action": st.action, "risk_score": st.risk_score, "matches": [m.to_dict() for m in st.matches],
            "signals": st.signals, "redaction_count": st.redaction_count, "redacted_entity_types": st.redacted_entity_types,
            "latency_ms": st.latency_ms}


def simulate(db: Session, *, prompt: str, role: str, include_output: bool = True, focus: PolicySnapshot | None = None) -> dict:
    actor = actor_for_role(db, role)
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
        "sanitized_prompt": sanitized,
        "input": _stage(stages[0]),
        "context": _stage(stages[1]),
        "output": _stage(stages[2]),
        "final": final,
        "focus_policy": {"id": focus.id, "name": focus.name, "triggered": bool(focus_matches), "matches": focus_matches} if focus else None,
    }
