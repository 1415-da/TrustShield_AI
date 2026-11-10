"""Guardrail evaluation harness.

Each test case declares the acceptable input actions (and optionally output actions). Cases are run
through the real gateway in dry-run mode (nothing persisted except the results). A case is *restrictive*
if its expectations imply the employee should not simply receive an answer.

    false positive  — a safe case that TrustShield restricted (blocked, escalated, or sent to review)
    false negative  — a restrictive case that TrustShield let through as a normal answer
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.guardrails.pipeline import Actor
from app.models import Role, TestCase, TestResult, TestRun
from app.models.base import utcnow
from app.services import audit, gateway

RESTRICTIVE_INPUT = {"BLOCK", "ESCALATE", "REVIEW", "REDACT"}
RESTRICTIVE_OUTPUT = {"BLOCK", "SEND_TO_REVIEW", "REDACT"}
HARD_STOP_STATUSES = {"blocked", "needs_review"}


def actor_for_role(db: Session, role_key: str) -> Actor:
    role = db.scalar(select(Role).where(Role.key == role_key))
    perms = set(role.permissions or []) if role else set()
    return Actor(user_id=None, email=f"simulated+{role_key}@novacorp.test", roles={role_key}, permissions=perms, primary_role=role_key)


def expected_restrictive(tc: TestCase) -> bool:
    if any(a in RESTRICTIVE_INPUT for a in tc.expected_input_actions) and "ALLOW" not in tc.expected_input_actions:
        return True
    return bool(tc.expected_output_actions) and all(a in RESTRICTIVE_OUTPUT for a in tc.expected_output_actions)


def run_case(db: Session, tc: TestCase) -> dict:
    r = gateway.process(db, actor=actor_for_role(db, tc.role_key), prompt=tc.prompt, persist=False)
    in_ok = r.input_action.value in tc.expected_input_actions
    out_val = r.output_action.value if r.output_action else None
    out_ok = not tc.expected_output_actions or (out_val in tc.expected_output_actions)
    passed = in_ok and out_ok
    restrictive_expected = expected_restrictive(tc)
    actually_restricted = r.trust_status in HARD_STOP_STATUSES or r.trust_status == "redacted"
    reason = ""
    if not in_ok:
        reason = f"input {r.input_action.value} not in {tc.expected_input_actions}"
    elif not out_ok:
        reason = f"output {out_val} not in {tc.expected_output_actions}"
    return {
        "passed": passed,
        "actual_input_action": r.input_action.value,
        "actual_output_action": out_val,
        "trust_status": r.trust_status,
        "matched_policies": sorted({m.policy_name for m in r.all_matches}),
        "confidence": r.grounding.confidence if r.grounding else None,
        "latency_ms": r.latency_ms,
        "false_positive": (not restrictive_expected) and r.trust_status in HARD_STOP_STATUSES,
        "false_negative": restrictive_expected and not actually_restricted,
        "failure_reason": reason,
    }


def execute_run(db: Session, run: TestRun, case_ids: list[int] | None = None) -> TestRun:
    stmt = select(TestCase).where(TestCase.is_active.is_(True)).order_by(TestCase.code)
    if case_ids:
        stmt = stmt.where(TestCase.id.in_(case_ids))
    cases = list(db.scalars(stmt))
    by_category: dict[str, dict[str, int]] = {}
    try:
        for tc in cases:
            res = run_case(db, tc)
            run.results.append(TestResult(test_case_id=tc.id, **res))
            cat = by_category.setdefault(tc.category, {"total": 0, "passed": 0})
            cat["total"] += 1
            cat["passed"] += int(res["passed"])
        run.total = len(cases)
        run.passed = sum(1 for r in run.results if r.passed)
        run.failed = run.total - run.passed
        run.false_positives = sum(1 for r in run.results if r.false_positive)
        run.false_negatives = sum(1 for r in run.results if r.false_negative)
        safe = sum(1 for tc in cases if not expected_restrictive(tc))
        risky = run.total - safe
        run.summary = {
            "pass_rate": round(run.passed / run.total, 3) if run.total else 0.0,
            "false_positive_rate": round(run.false_positives / safe, 3) if safe else 0.0,
            "false_negative_rate": round(run.false_negatives / risky, 3) if risky else 0.0,
            "safe_cases": safe, "restrictive_cases": risky, "by_category": by_category,
            "avg_latency_ms": round(sum(r.latency_ms for r in run.results) / run.total, 1) if run.total else 0.0,
        }
        run.status = "completed"
    except Exception as exc:  # pragma: no cover - surfaced in UI
        run.status = "failed"
        run.summary = {"error": type(exc).__name__}
    run.finished_at = utcnow()
    audit.record(db, "test_run.completed", actor_user_id=run.triggered_by,
                 details={"run_id": run.id, "status": run.status, "total": run.total, "passed": run.passed,
                          "false_positives": run.false_positives, "false_negatives": run.false_negatives})
    db.commit()
    return run
