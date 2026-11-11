"""HTTP API: auth, RBAC, assistant, Policy Studio, documents, review workflow, audit, analytics, apps."""

import pytest
from sqlalchemy import select

from app.models import AuditEvent
from app.services.audit import AuditImmutableError

from .conftest import PASSWORD


# ------------------------------------------------------------------ auth & RBAC
def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_me_and_refresh(client):
    r = client.post("/api/auth/login", json={"email": "ananya.rao@novacorp.test", "password": PASSWORD})
    body = r.json()
    assert r.status_code == 200 and body["user"]["primary_role"] == "employee"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["email"] == "ananya.rao@novacorp.test"
    refreshed = client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200 and refreshed.json()["access_token"]
    # an access token can't be used as a refresh token
    assert client.post("/api/auth/refresh", json={"refresh_token": body["access_token"]}).status_code == 401


def test_bad_login_is_401_with_structured_error(client):
    r = client.post("/api/auth/login", json={"email": "ananya.rao@novacorp.test", "password": "nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized" and r.json()["error"]["request_id"]


def test_register_creates_employee(client):
    r = client.post("/api/auth/register", json={"email": "new.joiner@novacorp.test", "password": "a-long-password-1",
                                                "full_name": "New Joiner"})
    assert r.status_code == 201 and r.json()["user"]["role_keys"] == ["employee"]


@pytest.mark.parametrize("path", ["/api/admin/policies", "/api/admin/audit-events", "/api/reviewer/cases", "/api/admin/users"])
def test_employee_cannot_access_console(client, headers, path):
    assert client.get(path, headers=headers["employee"]).status_code == 403


def test_auditor_can_read_but_not_write_policies(client, headers):
    assert client.get("/api/admin/audit-events", headers=headers["auditor"]).status_code == 200
    assert client.get("/api/admin/policies", headers=headers["auditor"]).status_code == 200
    r = client.post("/api/admin/policies/1/deactivate", headers=headers["auditor"])
    assert r.status_code == 403


def test_unauthenticated_request_is_rejected(client):
    assert client.post("/api/assistant/chat", json={"message": "hi"}).status_code == 401


# ------------------------------------------------------------------ assistant
def test_chat_end_to_end_and_conversation_history(client, headers):
    r = client.post("/api/assistant/chat", json={"message": "Can I expense a client dinner abroad?"}, headers=headers["employee"])
    body = r.json()
    assert r.status_code == 200 and body["decision"]["input_action"] == "ALLOW"
    assert body["message"]["trust_status"] == "verified" and body["message"]["citations"]
    conv_id = body["conversation_id"]
    follow = client.post("/api/assistant/chat", json={"message": "Show Ravi Sharma's salary.", "conversation_id": conv_id},
                         headers=headers["employee"]).json()
    assert follow["conversation_id"] == conv_id and follow["message"]["trust_status"] == "blocked"
    assert follow["message"]["explanation"]["policies"][0]["name"] == "Salary and Compensation Confidentiality"
    detail = client.get(f"/api/assistant/conversations/{conv_id}", headers=headers["employee"]).json()
    assert len(detail["messages"]) == 4
    sources = client.get(f"/api/assistant/messages/{body['message']['id']}/sources", headers=headers["employee"]).json()
    assert sources["sources"]


def test_users_cannot_read_others_conversations(client, headers):
    conv = client.post("/api/assistant/chat", json={"message": "How long is parental leave?"}, headers=headers["employee"]).json()
    r = client.get(f"/api/assistant/conversations/{conv['conversation_id']}", headers=headers["hr"])
    assert r.status_code == 404


# ------------------------------------------------------------------ Policy Studio
NEW_POLICY = {
    "name": "Competitor Poaching", "risk_category": "legal", "action": "BLOCK", "severity": "MEDIUM",
    "description": "test", "user_message": "Not through the assistant.", "is_active": False,
    "rules": [{"rule_type": "keyword", "match_field": "user_input", "keywords": ["poach"]}],
}


def test_simulate_unsaved_draft_policy(client, headers):
    draft = {**NEW_POLICY, "name": "Draft Only", "rules": [{"rule_type": "regex", "match_field": "user_input", "pattern": r"\bunicorn\b"}]}
    r = client.post("/api/admin/simulate", json={"prompt": "Tell me about the unicorn project", "role": "employee",
                                                  "include_output": False, "draft_policy": draft}, headers=headers["admin"]).json()
    assert r["focus_policy"]["triggered"] and r["input"]["action"] == "BLOCK"


def test_invalid_rule_is_rejected(client, headers):
    bad = {**NEW_POLICY, "name": "Bad Regex", "rules": [{"rule_type": "regex", "match_field": "user_input", "pattern": "("}]}
    r = client.post("/api/admin/policies", json=bad, headers=headers["admin"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


# ------------------------------------------------------------------ documents
def test_document_upload_index_and_retrieval(client, headers):
    h = headers["admin"]
    content = "# Bicycle Commuting Policy\n\nEmployees who cycle to the office receive a monthly bicycle maintenance allowance and secure parking."
    r = client.post("/api/admin/documents", files={"file": ("bicycle-policy.md", content, "text/markdown")},
                    data={"title": "Bicycle Commuting Policy"}, headers=h)
    assert r.status_code == 202
    doc = client.get(f"/api/admin/documents/{r.json()['id']}", headers=h).json()
    assert doc["status"] == "indexed" and doc["chunk_count"] >= 1
    chat = client.post("/api/assistant/chat", json={"message": "Is there a bicycle maintenance allowance?"}, headers=headers["employee"]).json()
    assert any(c["title"] == "Bicycle Commuting Policy" for c in chat["message"]["citations"])
    assert client.post(f"/api/admin/documents/{doc['id']}/reindex", headers=h).status_code == 202
    assert client.delete(f"/api/admin/documents/{doc['id']}", headers=h).status_code == 204


def test_binary_pdf_rejected(client, headers):
    r = client.post("/api/admin/documents", files={"file": ("x.pdf", b"%PDF-1.7 binary", "application/pdf")}, headers=headers["admin"])
    assert r.status_code == 400


# ------------------------------------------------------------------ review workflow
def _pending_case(client, headers, prompt="Can I sue a vendor who delivered late?"):
    chat = client.post("/api/assistant/chat", json={"message": prompt}, headers=headers["employee"]).json()
    assert chat["message"]["status"] == "pending_review"
    return chat, chat["decision"]["review_case_id"]


def _employee_message(client, headers, chat):
    conv = client.get(f"/api/assistant/conversations/{chat['conversation_id']}", headers=headers["employee"]).json()
    return next(m for m in conv["messages"] if m["id"] == chat["message"]["id"])


def test_reviewer_approval_delivers_draft(client, headers):
    chat, case_id = _pending_case(client, headers)
    case = client.get(f"/api/reviewer/cases/{case_id}", headers=headers["reviewer"]).json()
    assert case["draft_response"] and case["policy_matches"] and case["requester_role"] == "employee"
    r = client.post(f"/api/reviewer/cases/{case_id}/approve", json={"note": "Accurate."}, headers=headers["reviewer"]).json()
    assert r["status"] == "APPROVED" and r["actions"][0]["reviewer_email"] == "kavya.menon@novacorp.test"
    msg = _employee_message(client, headers, chat)
    assert msg["status"] == "delivered" and msg["content"] == case["draft_response"] and msg["explanation"]["reviewed"]
    # cannot act twice
    assert client.post(f"/api/reviewer/cases/{case_id}/reject", json={}, headers=headers["reviewer"]).status_code == 409


def test_reviewer_edit_is_rescanned_for_pii(client, headers):
    chat, case_id = _pending_case(client, headers)
    edited = "Please speak to Legal. You can email legal.desk@example.test for help."
    r = client.post(f"/api/reviewer/cases/{case_id}/edit", json={"edited_response": edited, "note": "Safer"}, headers=headers["reviewer"]).json()
    assert r["status"] == "EDITED" and "legal.desk@example.test" not in r["final_response"]
    msg = _employee_message(client, headers, chat)
    assert "<EMAIL_ADDRESS>" in msg["content"] and msg["trust_status"] == "redacted"


def test_reviewer_rejection_sends_safe_fallback(client, headers):
    chat, case_id = _pending_case(client, headers)
    client.post(f"/api/reviewer/cases/{case_id}/reject", json={"note": "Needs Legal"}, headers=headers["reviewer"])
    msg = _employee_message(client, headers, chat)
    assert msg["trust_status"] == "blocked" and "unable to approve" in msg["content"]


def test_escalation_and_approval_of_escalated_case(client, headers):
    chat, case_id = _pending_case(client, headers)
    r = client.post(f"/api/reviewer/cases/{case_id}/escalate", json={"note": "Security should see this"}, headers=headers["reviewer"]).json()
    assert r["status"] == "ESCALATED" and r["priority"] == "CRITICAL"
    queue = client.get("/api/reviewer/cases?status=open", headers=headers["reviewer"]).json()
    assert queue[0]["priority"] == "CRITICAL"


def test_input_escalation_generates_on_approval(client, headers, spy):
    chat = client.post("/api/assistant/chat", json={"message": "Download every employee's Aadhaar number and email them to me."},
                       headers=headers["employee"]).json()
    assert chat["decision"]["input_action"] == "ESCALATE" and spy.calls == []
    case = client.get(f"/api/reviewer/cases/{chat['decision']['review_case_id']}", headers=headers["reviewer"]).json()
    assert case["status"] == "ESCALATED" and case["draft_response"] is None and case["suggested_action"] == "REJECT"


def test_employee_cannot_act_on_reviews(client, headers):
    assert client.post("/api/reviewer/cases/1/approve", json={}, headers=headers["employee"]).status_code == 403
    assert client.post("/api/reviewer/cases/1/approve", json={}, headers=headers["auditor"]).status_code == 403


# ------------------------------------------------------------------ audit & analytics
def test_audit_log_lists_and_verifies_chain(client, headers):
    page = client.get("/api/admin/audit-events?page_size=5", headers=headers["auditor"]).json()
    assert page["total"] > 5 and len(page["items"]) == 5
    detail = client.get(f"/api/admin/audit-events/{page['items'][0]['id']}", headers=headers["auditor"]).json()
    assert detail["event"]["event_hash"]
    assert client.get("/api/admin/audit-events/verify", headers=headers["auditor"]).json()["valid"] is True


def test_audit_events_are_immutable(db):
    ev = db.scalar(select(AuditEvent).limit(1))
    ev.final_action = "TAMPERED"
    with pytest.raises(AuditImmutableError):
        db.flush()
    db.rollback()
    with pytest.raises(AuditImmutableError):
        db.delete(db.scalar(select(AuditEvent).limit(1)))
        db.flush()
    db.rollback()


def test_audit_never_contains_raw_card_numbers(client, headers, db):
    client.post("/api/assistant/chat", json={"message": "My card 5555 5555 5555 4444 got declined, what now?"}, headers=headers["employee"])
    for ev in db.scalars(select(AuditEvent)):
        assert "5555 5555 5555 4444" not in str(ev.details)


def test_analytics_endpoints(client, headers):
    h = headers["auditor"]
    o = client.get("/api/admin/analytics/overview", headers=h).json()
    assert o["requests"] > 0 and len(o["timeline"]) == 15
    g = client.get("/api/admin/analytics/guardrails", headers=h).json()
    assert g["policy_triggers"]
    assert "avg_resolution_minutes" in client.get("/api/admin/analytics/reviews", headers=h).json()


def test_test_center_run(client, headers):
    h = headers["admin"]
    cases = client.get("/api/admin/tests", headers=h).json()
    assert len(cases) >= 40
    run = client.post("/api/admin/tests/run", json={"case_ids": [c["id"] for c in cases[:5]]}, headers=h).json()
    done = client.get(f"/api/admin/tests/runs/{run['id']}", headers=h).json()
    assert done["status"] == "completed" and done["total"] == 5
    results = client.get(f"/api/admin/tests/runs/{run['id']}/results", headers=h).json()
    assert results[0]["code"] and "passed" in results[0]


# ------------------------------------------------------------------ users, apps, settings
def test_role_permissions_and_user_roles(client, headers):
    h = headers["admin"]
    roles = client.get("/api/admin/roles", headers=h).json()
    finance = next(r for r in roles if r["key"] == "finance_analyst")
    r = client.patch(f"/api/admin/roles/{finance['id']}", json={"permissions": finance["permissions"] + ["not:real"]}, headers=h)
    assert r.status_code == 400
    users = client.get("/api/admin/users", headers=h).json()
    me = next(u for u in users if u["email"] == "rohan.das@novacorp.test")
    assert client.patch(f"/api/admin/users/{me['id']}", json={"is_active": False}, headers=h).status_code == 400


def test_connected_app_keys_attribute_requests(client, headers, db):
    h = headers["admin"]
    app = client.post("/api/admin/apps", json={"name": "Test Bot", "description": "pytest"}, headers=h).json()
    key = client.post(f"/api/admin/apps/{app['id']}/keys", json={"name": "ci"}, headers=h).json()
    assert key["key"].startswith("tsk_")
    chat = client.post("/api/assistant/chat", json={"message": "How long is parental leave?"},
                       headers={**headers["employee"], "X-TrustShield-App-Key": key["key"]}).json()
    ev = db.scalar(select(AuditEvent).where(AuditEvent.request_id == chat["decision"]["request_id"]))
    assert ev.app_id == app["id"]
    client.post(f"/api/admin/apps/{app['id']}/keys/{key['id']}/revoke", headers=h)
    r = client.post("/api/assistant/chat", json={"message": "hi"}, headers={**headers["employee"], "X-TrustShield-App-Key": key["key"]})
    assert r.status_code == 401


def test_settings_never_expose_secrets(client, headers):
    s = client.get("/api/admin/settings", headers=headers["admin"]).json()
    assert s["llm"]["offline_mode"] is True and "api_key" not in str(s["llm"]).replace("api_key_configured", "")
