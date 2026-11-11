"""Compliance Evidence Center: turn governance records into audit-ready, reproducible evidence reports.

Design rules
------------
* **Append-only sources only.** Reports read the hash-chained `audit_events`, `guardrail_decisions`, `review_actions`,
  `policy_audit_events` and creation-time fields of review cases, all bounded by `period_end`. Mutable state
  (a case's current status, an exception's current status) is never used, so regenerating a report later produces
  byte-identical content and the same SHA-256 hash.
* **No raw sensitive values.** Entity types and counts only; prompts never appear in report content.
* **Traceable.** Every report stores the ids of the audit events it was built from.
"""

from __future__ import annotations

import hashlib
import html
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, NotFound
from app.guardrails.decision import SLA_HOURS
from app.guardrails.types import SEVERITY_ORDER
from app.models import (AuditEvent, ComplianceReport, GuardrailDecision, Policy, PolicyAuditEvent, ReportSchedule, ReviewAction,
                        ReviewCase, User)
from app.models.base import utcnow
from app.services import audit

REQUEST_EVENT_TYPES = ("assistant.request", "workspace.request", "slack.request")
SENSITIVE_CATEGORIES = {"compensation", "financial_data", "pii", "credentials", "data_exfiltration"}
REPORT_TYPES: dict[str, str] = {
    "governance_summary": "AI Governance Summary",
    "sensitive_data": "Sensitive Data Access Report",
    "human_oversight": "Human Oversight Report",
    "policy_changes": "Policy Change Report",
    "exceptions": "Exception Report",
}
REPORT_DESCRIPTIONS: dict[str, str] = {
    "governance_summary": "Requests processed, decisions, top policies, risk categories, departments, review SLAs and policy changes.",
    "sensitive_data": "Requests touching compensation, financial, personal or credential data, and how each was handled.",
    "human_oversight": "Review queue volume, reviewer decisions, time to decision, SLA breaches and workload.",
    "policy_changes": "Every policy created, changed, approved, activated, deactivated or rolled back, with approvers and rationale.",
    "exceptions": "Policy exceptions requested, approved, rejected, revoked, expired and still active, with justification.",
}


# --------------------------------------------------------------------------- filters
@dataclass
class ReportFilters:
    period_start: datetime
    period_end: datetime
    departments: list[str] = field(default_factory=list)
    policy_ids: list[int] = field(default_factory=list)
    risk_levels: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)
    include_reviews: bool = True
    include_policy_changes: bool = True
    include_sensitive_events: bool = True

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        d["period_start"] = self.period_start.isoformat()
        d["period_end"] = self.period_end.isoformat()
        for k in ("departments", "risk_levels", "reviewers"):
            d[k] = sorted(d[k])
        d["policy_ids"] = sorted(d["policy_ids"])
        return d

    def digest(self, report_type: str) -> str:
        return _sha({"type": report_type, **{k: v for k, v in self.public().items() if k not in ("period_start", "period_end")},
                     "period_days": (self.period_end - self.period_start).days})


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _pct(n: int, d: int) -> str:
    return f"{(n / d * 100):.1f}%" if d else "—"


def _minutes(values: list[float]) -> str:
    if not values:
        return "—"
    m = sum(values) / len(values)
    return f"{m:.0f} min" if m < 120 else f"{m / 60:.1f} h"


def _section(title: str, columns: list[str], rows: list[list[Any]], description: str = "", empty: str = "No records in this period.") -> dict:
    return {"title": title, "description": description, "columns": columns, "rows": rows, "empty": empty}


# --------------------------------------------------------------------------- shared loaders
@dataclass
class _Ctx:
    db: Session
    f: ReportFilters
    sources: set[int] = field(default_factory=set)
    users: dict[int, User] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.users = {u.id: u for u in self.db.scalars(select(User))}

    def department(self, ev: AuditEvent) -> str:
        dep = (ev.details or {}).get("department")
        if dep:
            return dep
        u = self.users.get(ev.actor_user_id or -1)
        return u.department if u else "Unknown"

    def events(self, prefixes: tuple[str, ...]) -> list[AuditEvent]:
        rows = self.db.scalars(select(AuditEvent).where(
            AuditEvent.created_at >= self.f.period_start, AuditEvent.created_at < self.f.period_end).order_by(AuditEvent.id))
        return [e for e in rows if e.event_type.startswith(prefixes)]


def _decisions_by_request(db: Session, request_ids: set[str]) -> dict[str, list[GuardrailDecision]]:
    out: dict[str, list[GuardrailDecision]] = defaultdict(list)
    if not request_ids:
        return out
    ids = sorted(request_ids)
    for i in range(0, len(ids), 500):
        for d in db.scalars(select(GuardrailDecision).where(GuardrailDecision.request_id.in_(ids[i:i + 500])).order_by(GuardrailDecision.id)):
            out[d.request_id].append(d)
    return out


def _max_severity(decisions: list[GuardrailDecision]) -> str:
    sev = [m.get("severity", "LOW") for d in decisions for m in d.matches or []]
    return max(sev, key=SEVERITY_ORDER.index) if sev else "NONE"


def _bucket(ev: AuditEvent) -> str:
    status = (ev.details or {}).get("trust_status")
    if ev.input_action == "ESCALATE":
        return "Escalated"
    return {"blocked": "Blocked", "needs_review": "Sent to review", "redacted": "Redacted"}.get(status, "Allowed")


def _requests(ctx: _Ctx) -> tuple[list[AuditEvent], dict[str, list[GuardrailDecision]]]:
    """Request events in scope after department / policy / risk-level filters."""
    events = [e for e in ctx.events(("assistant.request", "workspace.request", "slack.request")) if e.event_type in REQUEST_EVENT_TYPES]
    if ctx.f.departments:
        wanted = {d.lower() for d in ctx.f.departments}
        events = [e for e in events if ctx.department(e).lower() in wanted]
    if ctx.f.policy_ids:
        wanted_ids = set(ctx.f.policy_ids)
        events = [e for e in events if wanted_ids & set(e.policy_ids or [])]
    decisions = _decisions_by_request(ctx.db, {e.request_id for e in events if e.request_id})
    if ctx.f.risk_levels:
        levels = set(ctx.f.risk_levels)
        events = [e for e in events if _max_severity(decisions.get(e.request_id or "", [])) in levels]
    ctx.sources.update(e.id for e in events)
    return events, decisions


def _case_rows(ctx: _Ctx, case_ids: set[int] | None = None) -> list[ReviewCase]:
    stmt = select(ReviewCase).where(ReviewCase.created_at >= ctx.f.period_start, ReviewCase.created_at < ctx.f.period_end)
    cases = list(ctx.db.scalars(stmt.order_by(ReviewCase.id)))
    return [c for c in cases if case_ids is None or c.id in case_ids]


def _actions(ctx: _Ctx, cases: list[ReviewCase]) -> dict[int, list[ReviewAction]]:
    out: dict[int, list[ReviewAction]] = defaultdict(list)
    if not cases:
        return out
    for a in ctx.db.scalars(select(ReviewAction).where(ReviewAction.case_id.in_([c.id for c in cases]),
                                                       ReviewAction.created_at < ctx.f.period_end).order_by(ReviewAction.id)):
        out[a.case_id].append(a)
    return out


def _review_audit_ids(ctx: _Ctx, case_ids: set[int]) -> None:
    for e in ctx.events(("review.",)):
        if e.review_case_id in case_ids:
            ctx.sources.add(e.id)


TERMINAL = {"APPROVE", "EDIT", "REJECT"}


def _sla(cases: list[ReviewCase], actions: dict[int, list[ReviewAction]], period_end: datetime, reviewers: list[str]) -> dict[str, Any]:
    decided, durations, breaches, open_at_end = Counter(), [], 0, 0
    workload: dict[str, Counter] = defaultdict(Counter)
    minutes_by: dict[str, list[float]] = defaultdict(list)
    wanted = {r.lower() for r in reviewers}
    for c in cases:
        due = c.initial_sla_due_at or (c.created_at + timedelta(hours=SLA_HOURS.get(c.initial_priority or c.priority, 8)))
        acts = [a for a in actions.get(c.id, []) if not wanted or a.reviewer_email.lower() in wanted]
        for a in acts:
            workload[a.reviewer_email][a.action] += 1
            decided[a.action] += 1
        final = next((a for a in actions.get(c.id, []) if a.action in TERMINAL), None)
        if final:
            mins = (final.created_at - c.created_at).total_seconds() / 60
            durations.append(mins)
            if not wanted or final.reviewer_email.lower() in wanted:
                minutes_by[final.reviewer_email].append(mins)
            breaches += int(final.created_at > due)
        else:
            open_at_end += 1
            breaches += int(period_end > due)
    return {"decided": decided, "durations": durations, "breaches": breaches, "open": open_at_end, "workload": workload,
            "minutes_by": minutes_by}


# --------------------------------------------------------------------------- builders
def _governance_summary(ctx: _Ctx) -> dict:
    events, decisions = _requests(ctx)
    total = len(events)
    buckets = Counter(_bucket(e) for e in events)
    policies, categories = Counter(), Counter()
    for e in events:
        for d in decisions.get(e.request_id or "", []):
            for m in d.matches or []:
                policies[m.get("policy_name", "?")] += 1
                categories[m.get("risk_category", "other")] += 1
    by_dept: dict[str, Counter] = defaultdict(Counter)
    for e in events:
        by_dept[ctx.department(e)][_bucket(e)] += 1
    outcomes = ["Allowed", "Redacted", "Sent to review", "Blocked", "Escalated"]
    sections = [
        _section("Decision outcomes", ["Outcome", "Requests", "Share"], [[o, buckets[o], _pct(buckets[o], total)] for o in outcomes]),
        _section("Top policies triggered", ["Policy", "Rule matches"], [[p, n] for p, n in policies.most_common(10)]),
        _section("Risk-category breakdown", ["Risk category", "Rule matches"], [[c.replace("_", " ").title(), n] for c, n in categories.most_common()]),
        _section("Department breakdown", ["Department", "Requests", "Allowed", "Redacted", "Reviewed", "Blocked or escalated"],
                 [[d, sum(c.values()), c["Allowed"], c["Redacted"], c["Sent to review"], c["Blocked"] + c["Escalated"]]
                  for d, c in sorted(by_dept.items(), key=lambda kv: -sum(kv[1].values()))]),
    ]
    metrics = [
        {"label": "Requests processed", "value": total},
        {"label": "Allowed", "value": buckets["Allowed"]},
        {"label": "Redacted", "value": buckets["Redacted"]},
        {"label": "Sent to review", "value": buckets["Sent to review"]},
        {"label": "Blocked", "value": buckets["Blocked"]},
        {"label": "Escalated", "value": buckets["Escalated"]},
        {"label": "Model calls avoided", "value": sum(1 for e in events if not (e.details or {}).get("llm_called")),
         "hint": "Blocked or escalated before reaching the model"},
        {"label": "Values masked", "value": sum(e.redaction_count or 0 for e in events)},
    ]
    if ctx.f.include_reviews:
        case_ids = {e.review_case_id for e in events if e.review_case_id}
        cases = _case_rows(ctx, case_ids)
        sla = _sla(cases, _actions(ctx, cases), ctx.f.period_end, ctx.f.reviewers)
        _review_audit_ids(ctx, case_ids)
        sections.append(_section("Review SLA performance", ["Measure", "Value"], [
            ["Cases opened", len(cases)], ["Decided", len(sla["durations"])], ["Open at period end", sla["open"]],
            ["SLA breaches", sla["breaches"]], ["Within SLA", _pct(len(cases) - sla["breaches"], len(cases))],
            ["Average time to decision", _minutes(sla["durations"])]]))
    if ctx.f.include_policy_changes:
        changes = _policy_events(ctx)
        counts = Counter(c.event_type for c in changes)
        sections.append(_section("Policy changes during the period", ["Change", "Count"],
                                 [[k.replace("_", " ").capitalize(), v] for k, v in sorted(counts.items())]))
    summary = [
        f"TrustShield processed {total} AI requests in the evidence period.",
        f"{buckets['Blocked'] + buckets['Escalated']} were stopped before reaching the model; {buckets['Redacted']} had sensitive values masked; "
        f"{buckets['Sent to review']} were held for human review.",
    ]
    if policies:
        top, n = policies.most_common(1)[0]
        summary.append(f"The most frequently triggered policy was “{top}” ({n} rule matches).")
    return {"summary": summary, "metrics": metrics, "sections": sections}


def _sensitive_data(ctx: _Ctx) -> dict:
    events, decisions = _requests(ctx)
    in_scope, entities, rules, by_role = [], Counter(), Counter(), defaultdict(Counter)
    for e in events:
        ds = decisions.get(e.request_id or "", [])
        cats = {m.get("risk_category") for d in ds for m in d.matches or []}
        ents = [x.get("entity_type") for d in ds if d.stage == "input" for x in (d.signals or {}).get("entities", [])
                if x.get("entity_type") not in ("PERSON",)]
        topics = {k for d in ds if d.stage == "input" for k, v in ((d.signals or {}).get("topics") or {}).items()
                  if k != "prompt_injection" and (v or {}).get("score", 0) >= 0.6}
        if cats & SENSITIVE_CATEGORIES or ents or topics:
            in_scope.append(e)
            entities.update(ents)
            for d in ds:
                for m in d.matches or []:
                    if m.get("risk_category") in SENSITIVE_CATEGORIES:
                        rules[f"{m.get('policy_name')} › {m.get('rule_name')}"] += 1
            by_role[e.actor_role or "unknown"][_bucket(e)] += 1
    ctx.sources.intersection_update({e.id for e in in_scope})
    total = len(in_scope)
    b = Counter(_bucket(e) for e in in_scope)
    sections = [
        _section("Handling by role", ["Role", "Requests", "Allowed", "Redacted", "Reviewed", "Blocked or escalated"],
                 [[r.replace("_", " ").title(), sum(c.values()), c["Allowed"], c["Redacted"], c["Sent to review"], c["Blocked"] + c["Escalated"]]
                  for r, c in sorted(by_role.items())], description="“Allowed” for a sensitive request means the role holds the required data scope."),
        _section("Sensitive data types detected", ["Data type", "Occurrences"], [[t, n] for t, n in entities.most_common()],
                 description="Types and counts only. No values are stored in, or recoverable from, this report."),
        _section("Policy rules triggered", ["Policy › rule", "Matches"], [[r, n] for r, n in rules.most_common(15)]),
    ]
    if ctx.f.include_reviews:
        case_ids = {e.review_case_id for e in in_scope if e.review_case_id}
        cases = _case_rows(ctx, case_ids)
        acts = _actions(ctx, cases)
        _review_audit_ids(ctx, case_ids)
        decided = Counter(a.action for c in cases for a in acts.get(c.id, []) if a.action != "NOTE")
        sections.append(_section("Reviewer decisions on sensitive requests", ["Decision", "Count"],
                                 [[k.title(), v] for k, v in sorted(decided.items())]))
    metrics = [{"label": "Sensitive-data requests", "value": total}, {"label": "Blocked or escalated", "value": b["Blocked"] + b["Escalated"]},
               {"label": "Redacted", "value": b["Redacted"]}, {"label": "Allowed for an authorised role", "value": b["Allowed"]},
               {"label": "Held for review", "value": b["Sent to review"]}]
    summary = [f"{total} requests involved compensation, financial, personal or credential data.",
               f"{b['Blocked'] + b['Escalated']} were refused, {b['Redacted']} were answered with values masked, and "
               f"{b['Allowed']} were answered for roles holding the required data scope.",
               "No raw sensitive values are included in this report."]
    return {"summary": summary, "metrics": metrics, "sections": sections}


def _human_oversight(ctx: _Ctx) -> dict:
    cases = _case_rows(ctx)
    if ctx.f.departments:
        wanted = {d.lower() for d in ctx.f.departments}
        cases = [c for c in cases if (ctx.users.get(c.requester_id or -1) and ctx.users[c.requester_id].department.lower() in wanted)]
    acts = _actions(ctx, cases)
    sla = _sla(cases, acts, ctx.f.period_end, ctx.f.reviewers)
    case_ids = {c.id for c in cases}
    _review_audit_ids(ctx, case_ids)
    for e in ctx.events(REQUEST_EVENT_TYPES):
        if e.review_case_id in case_ids:
            ctx.sources.add(e.id)
    d = sla["decided"]
    reasons = Counter()
    for c in cases:
        if (c.initial_priority or c.priority) == "CRITICAL" or c.origin == "escalation":
            reasons[c.reason] += 1
        for a in acts.get(c.id, []):
            if a.action == "ESCALATE":
                reasons[f"Reviewer escalation: {a.note[:80] or 'no note'}"] += 1
    origin = Counter(c.origin for c in cases)
    priority = Counter(c.initial_priority or c.priority for c in cases)
    workload = [[r, sum(c.values()), c["APPROVE"], c["EDIT"], c["REJECT"], c["ESCALATE"], _minutes(sla["minutes_by"].get(r, []))]
                for r, c in sorted(sla["workload"].items(), key=lambda kv: -sum(kv[1].values()))]
    sections = [
        _section("Reviewer workload", ["Reviewer", "Actions", "Approved", "Edited", "Rejected", "Escalated", "Avg time to decision"], workload),
        _section("Cases by origin", ["Origin", "Cases"], [[{"input": "Input policy", "output": "Output check", "escalation": "Escalation"}.get(k, k), v]
                                                          for k, v in sorted(origin.items())]),
        _section("Cases by initial priority", ["Priority", "Cases", "SLA"], [[p.title(), priority[p], f"{SLA_HOURS[p]} h"]
                                                                            for p in ("CRITICAL", "HIGH", "MEDIUM", "LOW") if priority[p]]),
        _section("Escalation reasons", ["Reason", "Count"], [[r, n] for r, n in reasons.most_common(10)]),
    ]
    metrics = [{"label": "Cases opened", "value": len(cases)}, {"label": "Approved", "value": d["APPROVE"]},
               {"label": "Edited", "value": d["EDIT"]}, {"label": "Rejected", "value": d["REJECT"]},
               {"label": "Escalated", "value": d["ESCALATE"]}, {"label": "Average time to decision", "value": _minutes(sla["durations"])},
               {"label": "SLA breaches", "value": sla["breaches"]}, {"label": "Open at period end", "value": sla["open"]}]
    summary = [f"{len(cases)} answers were held for human review in the evidence period; {len(sla['durations'])} were decided.",
               f"Average time to decision was {_minutes(sla['durations'])}, with {sla['breaches']} SLA breach{'es' if sla['breaches'] != 1 else ''}."]
    return {"summary": summary, "metrics": metrics, "sections": sections}


def _policy_events(ctx: _Ctx) -> list[PolicyAuditEvent]:
    stmt = select(PolicyAuditEvent).where(PolicyAuditEvent.created_at >= ctx.f.period_start, PolicyAuditEvent.created_at < ctx.f.period_end)
    rows = [r for r in ctx.db.scalars(stmt.order_by(PolicyAuditEvent.id)) if not r.event_type.startswith("exception_")
            and r.event_type not in ("commented", "draft_saved")]
    if ctx.f.policy_ids:
        rows = [r for r in rows if r.policy_id in set(ctx.f.policy_ids)]
    ctx.sources.update(r.audit_event_id for r in rows if r.audit_event_id)
    return rows


def _policy_changes(ctx: _Ctx) -> dict:
    rows = _policy_events(ctx)
    names = {p.id: p.name for p in ctx.db.scalars(select(Policy))}
    counts = Counter(r.event_type for r in rows)
    decisions = [r for r in rows if r.event_type in ("approved", "rejected", "changes_requested")]
    sections = [
        _section("Approvals and rationale", ["Date", "Policy", "Version", "Decision", "Approver", "Rationale"],
                 [[r.created_at.strftime("%Y-%m-%d"), names.get(r.policy_id, "?"), f"v{r.version_number}", r.event_type.replace("_", " "),
                   r.actor_email or "—", r.note or "—"] for r in decisions]),
        _section("Change log", ["Date", "Policy", "Version", "Event", "Actor", "Status change", "Note"],
                 [[r.created_at.strftime("%Y-%m-%d %H:%M"), names.get(r.policy_id, "?"), f"v{r.version_number}" if r.version_number else "—",
                   r.event_type.replace("_", " "), r.actor_email or "system", f"{r.from_status or '—'} → {r.to_status or '—'}", r.note or ""]
                  for r in rows]),
    ]
    metrics = [{"label": "Policies created", "value": counts["created"]},
               {"label": "Drafts started", "value": counts["draft_created"]},
               {"label": "Submitted for review", "value": counts["submitted"]},
               {"label": "Approved", "value": counts["approved"]},
               {"label": "Changes requested or rejected", "value": counts["changes_requested"] + counts["rejected"]},
               {"label": "Activated", "value": counts["activated"]},
               {"label": "Deactivated", "value": counts["deactivated"]},
               {"label": "Rolled back", "value": counts["rolled_back"]}]
    summary = [f"{len({r.policy_id for r in rows})} policies changed during the evidence period across {len(rows)} lifecycle events.",
               f"{counts['activated']} versions were activated, every one after approval by a second person."]
    return {"summary": summary, "metrics": metrics, "sections": sections}


def _exceptions(ctx: _Ctx) -> dict:
    """Exception state reconstructed from append-only lifecycle events up to period_end (never the mutable row)."""
    from app.models import PolicyException

    names = {p.id: p.name for p in ctx.db.scalars(select(Policy))}
    events = list(ctx.db.scalars(select(PolicyAuditEvent).where(PolicyAuditEvent.event_type.like("exception_%"),
                                                                PolicyAuditEvent.created_at < ctx.f.period_end).order_by(PolicyAuditEvent.id)))
    state: dict[int, dict] = {}
    for ev in events:
        ex_id = (ev.details or {}).get("exception_id")
        if ex_id is None:
            continue
        s = state.setdefault(ex_id, {"requested_at": None, "status": "REQUESTED", "approver": None, "note": "", "events": []})
        s["events"].append(ev)
        kind = ev.event_type.removeprefix("exception_")
        if kind == "requested":
            s["requested_at"] = ev.created_at
        else:
            s["status"], s["approver"], s["note"] = kind.upper(), ev.actor_email, ev.note
    rows_db = {e.id: e for e in ctx.db.scalars(select(PolicyException).where(PolicyException.id.in_(list(state) or [-1])))}
    counts, table = Counter(), []
    for ex_id, s in sorted(state.items()):
        ex = rows_db.get(ex_id)
        if ex is None or (ctx.f.policy_ids and ex.policy_id not in set(ctx.f.policy_ids)):
            continue
        relevant = (s["requested_at"] and s["requested_at"] >= ctx.f.period_start) or (ex.expires_at >= ctx.f.period_start)
        if not relevant:
            continue
        status = s["status"]
        if status == "APPROVED":
            status = "EXPIRED" if ex.expires_at <= ctx.f.period_end else "ACTIVE"
        if s["requested_at"] and s["requested_at"] >= ctx.f.period_start:
            counts["REQUESTED_IN_PERIOD"] += 1
        counts[status] += 1
        ctx.sources.update(e.audit_event_id for e in s["events"] if e.audit_event_id)
        table.append([names.get(ex.policy_id, "?"), f"{ex.subject_type}: {ex.subject}", ex.justification, status.replace("_", " ").title(),
                      s["approver"] or "—", f"{ex.starts_at:%Y-%m-%d} → {ex.expires_at:%Y-%m-%d}"])
    metrics = [{"label": "Requested in period", "value": counts["REQUESTED_IN_PERIOD"]},
               {"label": "Approved and still active", "value": counts["ACTIVE"]},
               {"label": "Expired", "value": counts["EXPIRED"]}, {"label": "Rejected", "value": counts["REJECTED"]},
               {"label": "Revoked", "value": counts["REVOKED"]}, {"label": "Awaiting decision", "value": counts["REQUESTED"]}]
    sections = [_section("Exceptions", ["Policy", "Subject", "Business justification", "Status at period end", "Approver", "Window"], table)]
    summary = [f"{len(table)} policy exceptions were in effect or decided during the evidence period.",
               f"{counts['ACTIVE']} remain active at period end; every approved exception has an expiry date and a named approver."]
    return {"summary": summary, "metrics": metrics, "sections": sections}


BUILDERS = {"governance_summary": _governance_summary, "sensitive_data": _sensitive_data, "human_oversight": _human_oversight,
            "policy_changes": _policy_changes, "exceptions": _exceptions}


def build(db: Session, report_type: str, f: ReportFilters) -> tuple[dict, list[int]]:
    """Pure function of (type, filters, append-only records ≤ period_end). Returns (content, source audit-event ids)."""
    if report_type not in BUILDERS:
        raise BadRequest(f"Unknown report type '{report_type}'")
    ctx = _Ctx(db, f)
    body = BUILDERS[report_type](ctx)
    sources = sorted(i for i in ctx.sources if i)
    content = {
        "report_type": report_type,
        "title": REPORT_TYPES[report_type],
        "period": {"start": f.period_start.isoformat(), "end": f.period_end.isoformat()},
        "filters": f.public(),
        **body,
        "evidence": {"audit_events": len(sources), "source_hash": _sha(sources),
                     "statement": "Built only from append-only governance records dated within the evidence period [start, end)."},
    }
    return content, sources


# --------------------------------------------------------------------------- lifecycle
def parse_filters(data: dict[str, Any]) -> ReportFilters:
    end = data.get("period_end") or utcnow()
    start = data.get("period_start") or (end - timedelta(days=30))
    # Half-open window [start, end), end truncated to the second: records written after generation can never fall
    # inside a closed evidence period, which is what makes regeneration byte-identical.
    end = min(end.replace(tzinfo=None), utcnow()).replace(microsecond=0)
    start = start.replace(tzinfo=None)
    if start >= end:
        raise BadRequest("The evidence period must start before it ends")
    if (end - start).days > 366:
        raise BadRequest("The evidence period can be at most one year")
    return ReportFilters(period_start=start, period_end=end, departments=data.get("departments") or [],
                         policy_ids=data.get("policy_ids") or [], risk_levels=[r.upper() for r in data.get("risk_levels") or []],
                         reviewers=data.get("reviewers") or [], include_reviews=data.get("include_reviews", True),
                         include_policy_changes=data.get("include_policy_changes", True),
                         include_sensitive_events=data.get("include_sensitive_events", True))


def create_report(db: Session, report_type: str, filters: ReportFilters, user: User | None, retention_days: int | None = None,
                  schedule_id: int | None = None, title: str | None = None) -> ComplianceReport:
    if report_type not in REPORT_TYPES:
        raise BadRequest(f"Unknown report type '{report_type}'")
    digest = filters.digest(report_type)
    prior = db.scalars(select(ComplianceReport).where(ComplianceReport.filters_hash == digest)).all()
    r = ComplianceReport(
        report_type=report_type, title=title or f"{REPORT_TYPES[report_type]} · {filters.period_start:%d %b %Y} – {filters.period_end:%d %b %Y}",
        status="GENERATING", version=len(prior) + 1, filters_hash=digest, filters=filters.public(),
        period_start=filters.period_start, period_end=filters.period_end, generated_by=user.id if user else None,
        generated_by_email=user.email if user else "scheduler", schedule_id=schedule_id,
        expires_at=utcnow() + timedelta(days=retention_days) if retention_days else None,
    )
    db.add(r)
    db.flush()
    audit.record(db, "compliance.report_requested", **audit.actor_fields(user),
                 details={"report_id": r.id, "type": report_type, "period_start": r.period_start.isoformat(),
                          "period_end": r.period_end.isoformat(), "schedule_id": schedule_id})
    db.commit()
    return r


def generate(db: Session, report: ComplianceReport) -> ComplianceReport:
    try:
        content, sources = build(db, report.report_type, filters_of(report))
        report.content = content
        report.content_hash = _sha(content)
        report.source_event_ids = sources
        report.source_record_count = len(sources)
        report.completed_at = utcnow()
        report.status = "READY"
        audit.record(db, "compliance.report_generated", actor_user_id=report.generated_by, actor_email=report.generated_by_email,
                     content_hash=report.content_hash, details={"report_id": report.id, "type": report.report_type,
                                                                "source_records": len(sources), "version": report.version})
    except Exception as exc:  # pragma: no cover - surfaced as FAILED in the UI
        db.rollback()
        report = db.get(ComplianceReport, report.id)
        report.status, report.error = "FAILED", f"{type(exc).__name__}: {exc}"[:500]
        audit.record(db, "compliance.report_failed", details={"report_id": report.id, "error": report.error})
    db.commit()
    return report


def filters_of(report: ComplianceReport) -> ReportFilters:
    f = dict(report.filters)
    return ReportFilters(period_start=report.period_start, period_end=report.period_end, departments=f.get("departments", []),
                         policy_ids=f.get("policy_ids", []), risk_levels=f.get("risk_levels", []), reviewers=f.get("reviewers", []),
                         include_reviews=f.get("include_reviews", True), include_policy_changes=f.get("include_policy_changes", True),
                         include_sensitive_events=f.get("include_sensitive_events", True))


def refresh_expiry(db: Session, report: ComplianceReport) -> ComplianceReport:
    if report.status == "READY" and report.expires_at and report.expires_at <= utcnow():
        report.status = "EXPIRED"
        audit.record(db, "compliance.report_expired", details={"report_id": report.id})
        db.commit()
    return report


def get_report(db: Session, report_id: int, include_withdrawn: bool = False) -> ComplianceReport:
    r = db.get(ComplianceReport, report_id)
    if r is None or (r.deleted_at and not include_withdrawn):
        raise NotFound("Report")
    return refresh_expiry(db, r)


def verify(db: Session, report: ComplianceReport) -> dict[str, Any]:
    """Regenerate from the same records and compare hashes — proves the evidence is reproducible and untampered."""
    if report.status not in ("READY", "EXPIRED") or not report.content:
        raise BadRequest("Only generated reports can be verified")
    stored = _sha(report.content) == report.content_hash
    content, sources = build(db, report.report_type, filters_of(report))
    regenerated = _sha(content)
    return {"stored_hash": report.content_hash, "stored_content_matches_hash": stored, "regenerated_hash": regenerated,
            "reproducible": regenerated == report.content_hash, "source_records": len(sources), "verified_at": utcnow().isoformat() + "Z"}


def withdraw(db: Session, report: ComplianceReport, user: User) -> None:
    report.deleted_at, report.deleted_by_email = utcnow(), user.email
    audit.record(db, "compliance.report_withdrawn", **audit.actor_fields(user), content_hash=report.content_hash,
                 details={"report_id": report.id, "note": "Withdrawn from the library; the evidence record is retained."})
    db.commit()


# --------------------------------------------------------------------------- exports
def integrity_block(report: ComplianceReport) -> dict[str, Any]:
    return {"report_id": report.id, "version": report.version, "status": report.status, "generated_at": _iso(report.completed_at),
            "generated_by": report.generated_by_email, "period_start": _iso(report.period_start), "period_end": _iso(report.period_end),
            "source_record_count": report.source_record_count, "content_sha256": report.content_hash, "expires_at": _iso(report.expires_at)}


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() + "Z" if d else None


def export_json(report: ComplianceReport) -> dict[str, Any]:
    return {"integrity": integrity_block(report), "report": report.content, "source_audit_event_ids": report.source_event_ids}


def export_markdown(report: ComplianceReport) -> str:
    c = report.content or {}
    i = integrity_block(report)
    lines = [f"# {report.title}", "", f"**Evidence period:** {c['period']['start'][:10]} – {c['period']['end'][:10]}  ",
             f"**Report ID:** {report.id} (version {report.version}) · **Generated:** {i['generated_at']} by {i['generated_by']}  ",
             f"**Included records:** {report.source_record_count} audit events · **SHA-256:** `{report.content_hash}`", "", "## Summary", ""]
    lines += [f"- {s}" for s in c.get("summary", [])]
    lines += ["", "## Key figures", "", "| Measure | Value |", "|---|---|"]
    lines += [f"| {m['label']} | {m['value']} |" for m in c.get("metrics", [])]
    for s in c.get("sections", []):
        lines += ["", f"## {s['title']}", ""]
        if s.get("description"):
            lines += [f"_{s['description']}_", ""]
        if not s["rows"]:
            lines.append(s.get("empty", "No records."))
            continue
        lines += ["| " + " | ".join(s["columns"]) + " |", "|" + "---|" * len(s["columns"])]
        lines += ["| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in row) + " |" for row in s["rows"]]
    lines += ["", "---", f"_{c.get('evidence', {}).get('statement', '')}_ Source-record hash `{c.get('evidence', {}).get('source_hash', '')}`."]
    return "\n".join(lines) + "\n"


def export_html(report: ComplianceReport) -> str:
    c = report.content or {}
    e = html.escape
    metrics = "".join(f"<div class='m'><div class='v'>{e(str(m['value']))}</div><div class='l'>{e(m['label'])}</div></div>" for m in c.get("metrics", []))
    sections = []
    for s in c.get("sections", []):
        body = (f"<p class='empty'>{e(s.get('empty', 'No records.'))}</p>" if not s["rows"] else
                "<table><thead><tr>" + "".join(f"<th>{e(col)}</th>" for col in s["columns"]) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td>{e(str(v))}</td>" for v in row) + "</tr>" for row in s["rows"]) + "</tbody></table>")
        desc = f"<p class='desc'>{e(s['description'])}</p>" if s.get("description") else ""
        sections.append(f"<section><h2>{e(s['title'])}</h2>{desc}{body}</section>")
    summary = "".join(f"<li>{e(x)}</li>" for x in c.get("summary", []))
    i = integrity_block(report)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(report.title)}</title><style>
:root{{--cream:#FFFFEB;--ink:#1A1A1A;--forest:#034F46;--lilac:#F0D7FF;--hair:rgba(26,26,26,.12)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--cream);color:var(--ink);font:15px/1.55 -apple-system,"Segoe UI",Figtree,sans-serif}}
main{{max-width:960px;margin:0 auto;padding:48px 24px}}h1,h2{{font-family:"EB Garamond",Georgia,serif;font-weight:500;letter-spacing:-.01em}}
h1{{font-size:40px;line-height:1.1;margin:8px 0 12px}}h2{{font-size:24px;margin:36px 0 10px}}.eyebrow{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#6B6A62}}
.meta{{color:#3A3A36;font-size:13px}}.integrity{{margin-top:20px;border:1px solid var(--hair);border-radius:16px;padding:14px 18px;background:#fff8;font-size:12.5px}}
.integrity code{{font-size:11.5px;word-break:break-all}}.metrics{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin-top:20px}}
.m{{border-left:2px solid var(--forest);padding:4px 12px}}.v{{font-family:"EB Garamond",Georgia,serif;font-size:30px;color:var(--forest)}}.l{{font-size:12.5px;color:#3A3A36}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th{{text-align:left;font-weight:600;color:#6B6A62;border-bottom:1px solid var(--hair);padding:8px 10px 8px 0}}
td{{border-bottom:1px solid var(--hair);padding:8px 10px 8px 0;vertical-align:top}}.desc,.empty{{color:#6B6A62;font-size:13px}}ul{{padding-left:18px}}
footer{{margin-top:48px;font-size:12px;color:#6B6A62;border-top:1px solid var(--hair);padding-top:14px}}@media print{{body{{background:#fff}}}}
</style></head><body><main>
<p class="eyebrow">TrustShield AI · Compliance Evidence Center</p><h1>{e(report.title)}</h1>
<p class="meta">Evidence period {e(c['period']['start'][:10])} – {e(c['period']['end'][:10])} · Report {report.id} v{report.version} · Generated {e(i['generated_at'] or '')} by {e(i['generated_by'])}</p>
<div class="integrity"><strong>Evidence integrity.</strong> Included records: {report.source_record_count} audit events. SHA-256 of report content: <code>{e(report.content_hash or '')}</code></div>
<h2>Summary</h2><ul>{summary}</ul><div class="metrics">{metrics}</div>{''.join(sections)}
<footer>{e(c.get('evidence', {}).get('statement', ''))} Source-record hash <code>{e(c.get('evidence', {}).get('source_hash', ''))}</code>.</footer>
</main></body></html>"""


# --------------------------------------------------------------------------- schedules
CADENCE_DAYS = {"weekly": 7, "monthly": 30}


def create_schedule(db: Session, report: ComplianceReport, user: User, cadence: str, retention_days: int | None) -> ReportSchedule:
    if cadence not in CADENCE_DAYS:
        raise BadRequest("Cadence must be weekly or monthly")
    period_days = max(1, (report.period_end - report.period_start).days)
    s = ReportSchedule(report_type=report.report_type, title=REPORT_TYPES[report.report_type], cadence=cadence, retention_days=retention_days,
                       filters={**{k: v for k, v in report.filters.items() if k not in ("period_start", "period_end")}, "period_days": period_days},
                       created_by=user.id, created_by_email=user.email, source_report_id=report.id,
                       next_run_at=utcnow() + timedelta(days=CADENCE_DAYS[cadence]))
    db.add(s)
    db.flush()
    audit.record(db, "compliance.schedule_created", **audit.actor_fields(user),
                 details={"schedule_id": s.id, "type": s.report_type, "cadence": cadence, "from_report": report.id})
    db.commit()
    return s


def run_due_schedules(db: Session, now: datetime | None = None) -> list[ComplianceReport]:
    now = now or utcnow()
    out = []
    for s in db.scalars(select(ReportSchedule).where(ReportSchedule.is_active.is_(True), ReportSchedule.next_run_at <= now)):
        f = dict(s.filters)
        window_end = min(now, utcnow())
        filters = parse_filters({**f, "period_start": window_end - timedelta(days=int(f.get("period_days", 30))), "period_end": window_end})
        report = generate(db, create_report(db, s.report_type, filters, None, s.retention_days, schedule_id=s.id))
        s.last_run_at, s.last_report_id = now, report.id
        s.next_run_at = now + timedelta(days=CADENCE_DAYS[s.cadence])
        db.commit()
        out.append(report)
    return out


def options(db: Session) -> dict[str, Any]:
    users = list(db.scalars(select(User)))
    reviewers = sorted({u.email for u in users if u.has("reviews:act")})
    return {"report_types": [{"key": k, "title": v, "description": REPORT_DESCRIPTIONS[k]} for k, v in REPORT_TYPES.items()],
            "departments": sorted({u.department for u in users if u.department}),
            "policies": [{"id": p.id, "name": p.name} for p in db.scalars(select(Policy).order_by(Policy.name))],
            "risk_levels": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"], "reviewers": reviewers}
