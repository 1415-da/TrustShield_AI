"""Feature 1 — policy versioning and approval workflow."""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AuditEvent, PolicyAuditEvent, PolicyVersion
from app.models.policy import ImmutableVersionError
from app.services import gateway

from .conftest import PASSWORD, actor, login

_n = itertools.count()


def draft_body(**over):
    body = {
        "name": f"Project Unicorn Confidentiality {next(_n)}", "description": "Codename must not leak.",
        "risk_category": "legal", "owner": "Legal", "review_cadence_days": 90, "action": "BLOCK", "severity": "HIGH",
        "user_message": "Project Unicorn is confidential.",
        "rules": [{"key": "kw", "rule_type": "keyword", "match_field": "user_input", "keywords": ["unicorn"]}],
    }
    body.update(over)
    return body


def create(client, headers, **over):
    r = client.post("/api/admin/policies", json=draft_body(**over), headers=headers["admin"])
    assert r.status_code == 201, r.text
    return r.json()


def to_approved(client, headers, pid):
    assert client.post(f"/api/admin/policies/{pid}/submit-for-review", json={"note": "please review"}, headers=headers["admin"]).status_code == 200
    r = client.post(f"/api/admin/policies/{pid}/approve", json={"note": "ok"}, headers=headers["reviewer"])
    assert r.status_code == 200, r.text
    return r.json()


def blocks(db, prompt="Tell me about project unicorn"):
    return gateway.process(db, actor=actor("employee"), prompt=prompt, persist=False).input_action.value == "BLOCK"


def test_create_draft_does_not_affect_production(client, headers, db):
    p = create(client, headers)
    assert p["status"] == "DRAFT" and p["working"]["version"] == 1 and p["active"] is None
    assert not blocks(db)


def test_submit_for_review_creates_pending_approval(client, headers):
    p = create(client, headers)
    r = client.post(f"/api/admin/policies/{p['id']}/submit-for-review", json={"note": "ready"}, headers=headers["admin"]).json()
    assert r["status"] == "PENDING" and r["version"] == 1
    inbox = client.get("/api/admin/policy-approvals", headers=headers["reviewer"]).json()
    assert any(a["policy_id"] == p["id"] for a in inbox)


def test_approver_approves_and_policy_needs_activation(client, headers, db):
    p = create(client, headers)
    v = to_approved(client, headers, p["id"])
    assert v["status"] == "APPROVED" and v["approved_by_email"] == "kavya.menon@novacorp.test"
    assert not blocks(db), "approved-but-not-active must not be enforced"


def test_approver_requests_changes_then_author_edits_back_to_draft(client, headers):
    p = create(client, headers)
    client.post(f"/api/admin/policies/{p['id']}/submit-for-review", json={}, headers=headers["admin"])
    assert client.post(f"/api/admin/policies/{p['id']}/request-changes", json={}, headers=headers["reviewer"]).status_code == 400
    v = client.post(f"/api/admin/policies/{p['id']}/request-changes", json={"note": "Add the codename variants"}, headers=headers["reviewer"]).json()
    assert v["status"] == "CHANGES_REQUESTED"
    edited = client.post(f"/api/admin/policies/{p['id']}/versions", json={"rules": [
        {"key": "kw", "rule_type": "keyword", "match_field": "user_input", "keywords": ["unicorn", "uni-corn"]}]}, headers=headers["admin"]).json()
    assert edited["status"] == "DRAFT" and edited["version"] == 1 and "uni-corn" in edited["snapshot"]["rules"][0]["keywords"]


def test_approver_rejects(client, headers):
    p = create(client, headers)
    client.post(f"/api/admin/policies/{p['id']}/submit-for-review", json={}, headers=headers["admin"])
    v = client.post(f"/api/admin/policies/{p['id']}/reject", json={"note": "Out of scope"}, headers=headers["reviewer"]).json()
    assert v["status"] == "REJECTED"
    assert client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"]).status_code == 409


def test_activate_approved_policy_enforces_it(client, headers, db):
    p = create(client, headers)
    to_approved(client, headers, p["id"])
    v = client.post(f"/api/admin/policies/{p['id']}/activate", json={"note": "go live"}, headers=headers["admin"]).json()
    assert v["status"] == "ACTIVE" and v["activated_by_email"] == "rohan.das@novacorp.test"
    assert blocks(db)


def test_cannot_activate_without_approval(client, headers):
    p = create(client, headers)
    r = client.post(f"/api/admin/policies/{p['id']}/activate", json={"version_id": p["working"]["id"]}, headers=headers["admin"])
    assert r.status_code == 409


def test_only_one_active_version(client, headers, db):
    p = create(client, headers)
    to_approved(client, headers, p["id"])
    client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"])
    client.post(f"/api/admin/policies/{p['id']}/versions", json={"severity": "CRITICAL", "change_summary": "raise"}, headers=headers["admin"])
    to_approved(client, headers, p["id"])
    client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"])
    versions = client.get(f"/api/admin/policies/{p['id']}/versions", headers=headers["admin"]).json()
    assert [v["status"] for v in versions] == ["ACTIVE", "ARCHIVED"]
    # The database itself refuses a second ACTIVE version.
    v1 = db.scalar(select(PolicyVersion).where(PolicyVersion.policy_id == p["id"], PolicyVersion.version == 1))
    v1.status = "ACTIVE"
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_editing_active_policy_creates_new_draft(client, headers, db):
    p = create(client, headers)
    to_approved(client, headers, p["id"])
    client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"])
    d = client.patch(f"/api/admin/policies/{p['id']}", json={"action": "REVIEW", "change_summary": "soften"}, headers=headers["admin"]).json()
    assert d["version"] == 2 and d["status"] == "DRAFT" and d["snapshot"]["action"] == "REVIEW"
    detail = client.get(f"/api/admin/policies/{p['id']}", headers=headers["admin"]).json()
    assert detail["active"]["version"] == 1 and detail["active"]["snapshot"]["action"] == "BLOCK"
    assert blocks(db), "the live version keeps enforcing BLOCK while the draft waits"


def test_rollback_creates_new_version_from_prior_approved(client, headers):
    p = create(client, headers)
    to_approved(client, headers, p["id"])
    client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"])
    v1_id = client.get(f"/api/admin/policies/{p['id']}", headers=headers["admin"]).json()["active"]["id"]
    client.post(f"/api/admin/policies/{p['id']}/versions", json={"keywords": [], "rules": [
        {"key": "kw", "rule_type": "keyword", "match_field": "user_input", "keywords": ["pegasus"]}]}, headers=headers["admin"])
    to_approved(client, headers, p["id"])
    client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"])
    r = client.post(f"/api/admin/policies/{p['id']}/rollback", json={"version_id": v1_id, "note": "pegasus misfired", "activate": True},
                    headers=headers["admin"])
    assert r.status_code == 201
    versions = client.get(f"/api/admin/policies/{p['id']}/versions", headers=headers["admin"]).json()
    assert versions[0]["version"] == 3 and versions[0]["status"] == "ACTIVE"
    assert versions[0]["snapshot"]["rules"][0]["keywords"] == ["unicorn"] and versions[0]["based_on_version_id"] == v1_id
    assert versions[2]["status"] == "ARCHIVED" and versions[2]["snapshot"]["rules"][0]["keywords"] == ["unicorn"], "v1 untouched"


def test_simulation_uses_draft_version(client, headers):
    p = create(client, headers)
    sim = client.post(f"/api/admin/policies/{p['id']}/simulate", json={"prompt": "Status of project unicorn?", "role": "employee",
                                                                       "include_output": False}, headers=headers["admin"]).json()
    assert sim["focus_policy"]["triggered"] and sim["focus_policy"]["version"] == 1 and sim["final"]["input_action"] == "BLOCK"


def test_impact_analysis_runs_the_suite(client, headers):
    p = create(client, headers, rules=[{"key": "k", "rule_type": "keyword", "match_field": "user_input", "keywords": ["leave"]}])
    r = client.post(f"/api/admin/policies/{p['id']}/simulate", json={"suite": True}, headers=headers["admin"]).json()
    impact = r["impact"]
    assert impact["scenarios"] >= 40 and impact["triggered"] >= 2
    assert any(c["code"] == "T11" and c["after"]["input"] == "BLOCK" for c in impact["changed"])
    assert impact["regressions"] >= 1


def test_every_transition_is_audited(client, headers, db):
    p = create(client, headers)
    to_approved(client, headers, p["id"])
    client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"])
    client.post(f"/api/admin/policies/{p['id']}/deactivate", json={"note": "pause"}, headers=headers["admin"])
    history = client.get(f"/api/admin/policies/{p['id']}/audit-history", headers=headers["auditor"]).json()
    types = [h["event_type"] for h in reversed(history)]
    assert types == ["created", "submitted", "approved", "activated", "deactivated"]
    for h in history:
        ev = db.get(AuditEvent, h["audit_event_id"])
        assert ev is not None and ev.event_type == f"policy.{h['event_type']}" and p["id"] in ev.policy_ids


def test_separation_of_duties(client, headers, db):
    p = create(client, headers)
    client.post(f"/api/admin/policies/{p['id']}/submit-for-review", json={}, headers=headers["admin"])
    # The TrustShield Admin authors policies but never approves them.
    r = client.post(f"/api/admin/policies/{p['id']}/approve", json={}, headers=headers["admin"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "AUTHORIZATION_DENIED"

    # Even someone holding both roles cannot approve a version they authored themselves.
    from app.core.security import hash_password
    from app.models import Role, User
    roles = {r.key: r for r in db.scalars(select(Role))}
    db.add(User(email="dual.role@novacorp.test", full_name="Dual Role", department="IT", title="Test",
                password_hash=hash_password(PASSWORD), roles=[roles["employee"], roles["trustshield_admin"], roles["compliance_reviewer"]]))
    db.commit()
    dual = login(client, "dual.role@novacorp.test")
    p2 = create(client, {"admin": dual})
    client.post(f"/api/admin/policies/{p2['id']}/submit-for-review", json={}, headers=dual)
    r = client.post(f"/api/admin/policies/{p2['id']}/approve", json={}, headers=dual)
    assert r.status_code == 403 and "Separation of duties" in r.json()["error"]["message"]


def test_permissions(client, headers):
    p = create(client, headers)
    assert client.post(f"/api/admin/policies/{p['id']}/approve", json={}, headers=headers["auditor"]).status_code == 403
    assert client.post("/api/admin/policies", json=draft_body(), headers=headers["reviewer"]).status_code == 403
    assert client.get(f"/api/admin/policies/{p['id']}/versions", headers=headers["employee"]).status_code == 403
    assert client.get(f"/api/admin/policies/{p['id']}/audit-history", headers=headers["auditor"]).status_code == 200


def test_submitted_snapshot_is_immutable(client, headers, db):
    p = create(client, headers)
    client.post(f"/api/admin/policies/{p['id']}/submit-for-review", json={}, headers=headers["admin"])
    v = db.scalar(select(PolicyVersion).where(PolicyVersion.policy_id == p["id"]))
    v.snapshot = {**v.snapshot, "action": "ALLOW"}
    with pytest.raises(ImmutableVersionError):
        db.flush()
    db.rollback()
    # and the API refuses to edit while in review
    r = client.post(f"/api/admin/policies/{p['id']}/versions", json={"severity": "LOW"}, headers=headers["admin"])
    assert r.status_code == 409


def test_diff_shows_rule_and_threshold_changes(client, headers):
    p = create(client, headers)
    to_approved(client, headers, p["id"])
    client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"])
    d = client.post(f"/api/admin/policies/{p['id']}/versions", json={"threshold": 0.8, "applicable_roles": ["employee"], "rules": [
        {"key": "kw", "rule_type": "keyword", "match_field": "user_input", "keywords": ["unicorn"], "action": "REVIEW"},
        {"rule_type": "regex", "match_field": "user_input", "pattern": r"\bUNI-\d+\b", "name": "Ticket ids"}]},
        headers=headers["admin"]).json()
    diff = client.get(f"/api/admin/policies/{p['id']}/versions/{d['id']}", headers=headers["reviewer"]).json()["diff"]
    fields = {f["field"] for f in diff["fields"]}
    assert {"threshold", "applicable_roles"} <= fields
    assert diff["rules_added"][0]["name"] == "Ticket ids"
    assert diff["rules_changed"][0]["changes"][0] == {"field": "action", "before": None, "after": "REVIEW"}


def test_policy_exception_exempts_subject(client, headers, db):
    p = create(client, headers, rules=[{"key": "z", "rule_type": "keyword", "match_field": "user_input", "keywords": ["zephyrcode"]}])
    to_approved(client, headers, p["id"])
    client.post(f"/api/admin/policies/{p['id']}/activate", json={}, headers=headers["admin"])
    ex = client.post("/api/admin/policy-exceptions", json={"policy_id": p["id"], "subject_type": "role", "subject": "hr_manager",
                                                           "justification": "HR runs the unicorn hiring plan.",
                                                           "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}, headers=headers["admin"]).json()
    hr = gateway.process(db, actor=actor("hr_manager"), prompt="zephyrcode hiring", persist=False)
    assert hr.input_action.value == "BLOCK", "requested exceptions do nothing until approved"
    client.post(f"/api/admin/policy-exceptions/{ex['id']}/approve", json={"note": "ok"}, headers=headers["reviewer"])
    hr = gateway.process(db, actor=actor("hr_manager"), prompt="zephyrcode hiring", persist=False)
    assert hr.input_action.value != "BLOCK" and p["name"] in hr.input_stage.signals["exceptions_applied"]
    assert blocks(db, "zephyrcode hiring"), "employees are still covered"
    assert db.scalar(select(PolicyAuditEvent).where(PolicyAuditEvent.event_type == "exception_approved"))
