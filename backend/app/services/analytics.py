"""Governance analytics computed from audit events, guardrail decisions, review cases and test runs.

Aggregation is done in Python for portability across PostgreSQL and SQLite; at MVP volumes (thousands of
rows) this is well under 100 ms.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, GuardrailDecision, ReviewCase, TestRun
from app.models.base import utcnow

REQUEST_EVENTS = ("assistant.request",)


def _bucket(ev: AuditEvent) -> str:
    status = (ev.details or {}).get("trust_status")
    if ev.input_action == "ESCALATE":
        return "escalated"
    if status == "blocked":
        return "blocked"
    if status == "needs_review":
        return "review"
    if status == "redacted":
        return "redacted"
    return "allowed"


def overview(db: Session, days: int = 14) -> dict:
    since = utcnow() - timedelta(days=days)
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.event_type.in_(REQUEST_EVENTS), AuditEvent.created_at >= since)))
    buckets = Counter(_bucket(e) for e in events)
    series: dict[str, Counter] = defaultdict(Counter)
    for e in events:
        series[e.created_at.date().isoformat()][_bucket(e)] += 1
    timeline = []
    for i in range(days, -1, -1):
        day = (utcnow() - timedelta(days=i)).date().isoformat()
        c = series.get(day, Counter())
        timeline.append({"date": day, **{k: c.get(k, 0) for k in ("allowed", "redacted", "review", "blocked", "escalated")}})

    latencies = sorted(e.latency_ms for e in events if e.latency_ms is not None)
    reviews = review_stats(db)
    latest_run = db.scalar(select(TestRun).where(TestRun.status == "completed").order_by(TestRun.id.desc()).limit(1))
    return {
        "window_days": days,
        "requests": len(events),
        "allowed": buckets["allowed"],
        "blocked": buckets["blocked"],
        "escalated": buckets["escalated"],
        "redacted": buckets["redacted"],
        "sent_to_review": buckets["review"],
        "redactions": sum(e.redaction_count or 0 for e in events),
        "llm_calls_avoided": sum(1 for e in events if not (e.details or {}).get("llm_called")),
        "review_queue_open": reviews["open"],
        "avg_review_minutes": reviews["avg_resolution_minutes"],
        "p50_latency_ms": latencies[len(latencies) // 2] if latencies else None,
        "timeline": timeline,
        "latest_test_run": _run_summary(latest_run),
        "data_label": "Synthetic demo data",
    }


def guardrail_stats(db: Session, days: int = 14) -> dict:
    since = utcnow() - timedelta(days=days)
    decisions = list(db.scalars(select(GuardrailDecision).where(GuardrailDecision.created_at >= since)))
    policy_counts: Counter = Counter()
    category_counts: Counter = Counter()
    rule_type_counts: Counter = Counter()
    stage_actions: dict[str, Counter] = defaultdict(Counter)
    entity_counts: Counter = Counter()
    for d in decisions:
        stage_actions[d.stage][d.action] += 1
        for m in d.matches or []:
            policy_counts[m.get("policy_name", "?")] += 1
            category_counts[m.get("risk_category", "other")] += 1
            rule_type_counts[m.get("rule_type", "?")] += 1
        if d.stage == "input":
            for ent in (d.signals or {}).get("entities", []):
                entity_counts[ent.get("entity_type")] += 1
    return {
        "policy_triggers": [{"policy": k, "count": v} for k, v in policy_counts.most_common(12)],
        "risk_categories": [{"category": k, "count": v} for k, v in category_counts.most_common()],
        "rule_types": [{"rule_type": k, "count": v} for k, v in rule_type_counts.most_common()],
        "entities_detected": [{"entity_type": k, "count": v} for k, v in entity_counts.most_common()],
        "stage_actions": {stage: dict(c) for stage, c in stage_actions.items()},
        "test_runs": [_run_summary(r) for r in db.scalars(select(TestRun).where(TestRun.status == "completed").order_by(TestRun.id.desc()).limit(8))],
    }


def review_stats(db: Session) -> dict:
    cases = list(db.scalars(select(ReviewCase)))
    now = utcnow()
    open_cases = [c for c in cases if c.status in ("PENDING", "ESCALATED")]
    resolved = [c for c in cases if c.resolved_at]
    durations = [(c.resolved_at - c.created_at).total_seconds() / 60 for c in resolved]
    reviewer_counts = Counter(c.resolved_by for c in resolved if c.resolved_by)
    return {
        "total": len(cases),
        "open": len(open_cases),
        "breaching_sla": sum(1 for c in open_cases if c.sla_due_at < now),
        "by_status": dict(Counter(c.status for c in cases)),
        "by_priority": dict(Counter(c.priority for c in open_cases)),
        "by_origin": dict(Counter(c.origin for c in cases)),
        "avg_resolution_minutes": round(sum(durations) / len(durations), 1) if durations else None,
        "resolved": len(resolved),
        "reviewer_throughput": [{"reviewer_id": k, "resolved": v} for k, v in reviewer_counts.most_common()],
        "approval_rate": round(sum(1 for c in resolved if c.status in ("APPROVED", "EDITED")) / len(resolved), 3) if resolved else None,
    }


def _run_summary(run: TestRun | None) -> dict | None:
    if run is None:
        return None
    return {"id": run.id, "finished_at": run.finished_at.isoformat() + "Z" if run.finished_at else None, "total": run.total,
            "passed": run.passed, "failed": run.failed, "false_positives": run.false_positives,
            "false_negatives": run.false_negatives, **{k: run.summary.get(k) for k in ("pass_rate", "false_positive_rate", "false_negative_rate")}}


def counts(db: Session) -> dict:
    return {"audit_events": db.scalar(select(func.count(AuditEvent.id))) or 0}
