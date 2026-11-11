"""Feature 2 — Compliance Evidence Center."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import time

import pytest
from sqlalchemy import select

from app.models import ComplianceReport, Policy
from app.models.base import utcnow
from app.models.compliance import ImmutableReportError
from app.services import evidence


@pytest.fixture(scope="module", autouse=True)
def traffic(client, headers):
    """Real requests through the gateway so reports have something to evidence."""
    emp, hr = headers["employee"], headers["hr"]
    for msg in ["What is the international vendor refund policy?", "Show Ravi Sharma's salary.",
                "My card 4111 1111 1111 1111 was charged twice, what should I do?", "How long is parental leave?"]:
        client.post("/api/assistant/chat", json={"message": msg}, headers=emp)
    client.post("/api/assistant/chat", json={"message": "Show Ravi Sharma's salary band."}, headers=hr)
    case = client.post("/api/assistant/chat", json={"message": "Can I sue a vendor who delivered late?"}, headers=emp).json()
    client.post(f"/api/reviewer/cases/{case['decision']['review_case_id']}/approve", json={"note": "fine"}, headers=headers["reviewer"])
    # Evidence windows are half-open and end on a whole second; let the clock pass a second boundary so the
    # traffic above is inside the period of reports generated "now".
    time.sleep(1.05)


def generate(client, headers, report_type="governance_summary", **filters):
    body = {"report_type": report_type, "period_start": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(), **filters}
    r = client.post("/api/compliance/reports", json=body, headers=headers["reviewer"])
    assert r.status_code == 202, r.text
    full = client.get(f"/api/compliance/reports/{r.json()['id']}", headers=headers["reviewer"]).json()
    assert full["status"] == "READY", full.get("error")
    return full


def metric(report, label):
    return next(m["value"] for m in report["content"]["metrics"] if m["label"] == label)


def section(report, title):
    return next(s for s in report["content"]["sections"] if s["title"] == title)


def test_governance_summary(client, headers):
    r = generate(client, headers)
    assert metric(r, "Requests processed") >= 6 and metric(r, "Blocked") >= 1 and metric(r, "Redacted") >= 1
    assert any(row[0] == "Salary and Compensation Confidentiality" for row in section(r, "Top policies triggered")["rows"])
    assert section(r, "Department breakdown")["rows"] and section(r, "Review SLA performance")["rows"][0][1] >= 1
    assert r["source_record_count"] >= 6 and r["content_hash"]


def test_sensitive_data_report_has_no_raw_values(client, headers):
    r = generate(client, headers, "sensitive_data")
    assert metric(r, "Sensitive-data requests") >= 3
    assert any(row[0] == "CREDIT_CARD" for row in section(r, "Sensitive data types detected")["rows"])
    roles = {row[0] for row in section(r, "Handling by role")["rows"]}
    assert {"Employee", "Hr Manager"} <= roles
    blob = str(r["content"])
    assert "4111" not in blob and "Ravi" not in blob


def test_human_oversight_report(client, headers):
    r = generate(client, headers, "human_oversight")
    assert metric(r, "Cases opened") >= 1 and metric(r, "Approved") >= 1
    assert any(row[0] == "kavya.menon@novacorp.test" for row in section(r, "Reviewer workload")["rows"])


def test_policy_change_report(client, headers):
    r = generate(client, headers, "policy_changes")
    assert metric(r, "Activated") >= 13 and metric(r, "Approved") >= 13
    approvals = section(r, "Approvals and rationale")["rows"]
    assert approvals and all(row[4] == "kavya.menon@novacorp.test" for row in approvals if row[3] == "approved")


def test_exception_report(client, headers):
    r = generate(client, headers, "exceptions", period_start=(utcnow() - timedelta(days=60)).isoformat())
    statuses = {row[3] for row in section(r, "Exceptions")["rows"]}
    assert {"Active", "Expired", "Rejected", "Requested"} <= statuses
    assert all(row[2] for row in section(r, "Exceptions")["rows"]), "business justification is always present"


def test_filter_by_date_range(client, headers):
    long_ago = datetime.now(timezone.utc) - timedelta(days=300)
    r = generate(client, headers, period_start=long_ago.isoformat(), period_end=(long_ago + timedelta(days=5)).isoformat())
    assert metric(r, "Requests processed") == 0 and r["source_record_count"] == 0


def test_filter_by_department(client, headers):
    ops = generate(client, headers, departments=["General Operations"])
    legal = generate(client, headers, departments=["Legal"])
    assert metric(ops, "Requests processed") >= 5 and metric(legal, "Requests processed") == 0


def test_filter_by_policy(client, headers, db):
    salary = db.scalar(select(Policy).where(Policy.name == "Salary and Compensation Confidentiality"))
    r = generate(client, headers, policy_ids=[salary.id])
    assert metric(r, "Requests processed") >= 1
    assert metric(r, "Requests processed") < metric(generate(client, headers), "Requests processed")


def test_export_markdown(client, headers):
    r = generate(client, headers)
    md = client.get(f"/api/compliance/reports/{r['id']}/export?format=markdown", headers=headers["auditor"])
    assert md.status_code == 200 and md.text.startswith("# AI Governance Summary") and r["content_hash"] in md.text
    assert "attachment" in md.headers["content-disposition"]


def test_export_json(client, headers):
    r = generate(client, headers)
    js = client.get(f"/api/compliance/reports/{r['id']}/export?format=json", headers=headers["auditor"]).json()
    assert js["integrity"]["content_sha256"] == r["content_hash"] and js["source_audit_event_ids"]


def test_export_html(client, headers):
    r = generate(client, headers, "human_oversight")
    h = client.get(f"/api/compliance/reports/{r['id']}/export?format=html", headers=headers["auditor"])
    assert h.status_code == 200 and "<!doctype html>" in h.text and "Human Oversight Report" in h.text and r["content_hash"] in h.text


def test_unauthorized_access(client, headers):
    r = generate(client, headers)
    assert client.get("/api/compliance/reports", headers=headers["employee"]).status_code == 403
    assert client.get(f"/api/compliance/reports/{r['id']}/export?format=json", headers=headers["finance"]).status_code == 403
    assert client.post("/api/compliance/reports", json={"report_type": "exceptions"}, headers=headers["auditor"]).status_code == 403
    assert client.get(f"/api/compliance/reports/{r['id']}", headers=headers["auditor"]).status_code == 200


def test_hash_stored_and_reproducible(client, headers, db):
    r = generate(client, headers)
    row = db.get(ComplianceReport, r["id"])
    assert row.content_hash == evidence._sha(row.content)
    v = client.get(f"/api/compliance/reports/{r['id']}/verify", headers=headers["auditor"]).json()
    assert v["reproducible"] and v["stored_content_matches_hash"]
    # New traffic after the evidence period does not change the report.
    client.post("/api/assistant/chat", json={"message": "How do I reset my password?"}, headers=headers["employee"])
    assert client.get(f"/api/compliance/reports/{r['id']}/verify", headers=headers["auditor"]).json()["reproducible"]


def test_report_is_immutable(client, headers, db):
    r = generate(client, headers)
    row = db.get(ComplianceReport, r["id"])
    row.content = {**row.content, "summary": ["tampered"]}
    with pytest.raises(ImmutableReportError):
        db.flush()
    db.rollback()
    row = db.get(ComplianceReport, r["id"])
    row.status = "GENERATING"
    with pytest.raises(ImmutableReportError):
        db.flush()
    db.rollback()


def test_withdraw_keeps_evidence_record(client, headers, db):
    r = generate(client, headers)
    assert client.delete(f"/api/compliance/reports/{r['id']}", headers=headers["reviewer"]).status_code == 204
    library = client.get("/api/compliance/reports", headers=headers["reviewer"]).json()
    assert r["id"] not in [x["id"] for x in library]
    db.expire_all()
    row = db.get(ComplianceReport, r["id"])
    assert row.deleted_at is not None and row.content_hash == r["content_hash"]


def test_schedule_runs_when_due(client, headers, db):
    r = generate(client, headers, "policy_changes")
    s = client.post(f"/api/compliance/reports/{r['id']}/schedule", json={"cadence": "weekly"}, headers=headers["reviewer"]).json()
    assert s["cadence"] == "weekly" and s["is_active"]
    produced = evidence.run_due_schedules(db, now=utcnow() + timedelta(days=8))
    assert any(p.schedule_id == s["id"] and p.status == "READY" for p in produced)


def test_report_expiry(client, headers, db):
    r = generate(client, headers, retention_days=1)
    row = db.get(ComplianceReport, r["id"])
    assert row.expires_at is not None
    from app.services import audit  # noqa: F401  (expiry writes an audit event)

    db.execute(ComplianceReport.__table__.update().where(ComplianceReport.id == row.id).values(expires_at=utcnow() - timedelta(minutes=1)))
    db.commit()
    assert client.get(f"/api/compliance/reports/{r['id']}", headers=headers["reviewer"]).json()["status"] == "EXPIRED"
