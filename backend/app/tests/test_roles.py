"""Role model consistency: one canonical name per role, everyone is an employee, separation of duties."""

from __future__ import annotations

from sqlalchemy import select

from app.core.permissions import DEFAULT_ROLES, PERMISSION_CATALOGUE
from app.models import Role, User
from app.seed import data


def test_every_seeded_person_is_an_employee_with_at_most_one_job_role():
    for u in data.USERS:
        assert u["roles"][0] == "employee", u["email"]
        assert len(u["roles"]) <= 2, f"{u['email']} should hold employee plus one job role"


def test_role_names_are_unique_and_permissions_are_known():
    names = [r["name"] for r in DEFAULT_ROLES]
    assert len(names) == len(set(names))
    assert "Security Auditor" in names
    for r in DEFAULT_ROLES:
        assert set(r["permissions"]) <= set(PERMISSION_CATALOGUE), r["key"]


def test_admin_runs_the_workspace_but_approves_nothing():
    admin = next(r for r in DEFAULT_ROLES if r["key"] == "trustshield_admin")
    for scope in ("reviews:act", "policies:approve", "actions:approve", "data:compensation", "data:financial"):
        assert scope not in admin["permissions"]
    assert "reviews:read" in admin["permissions"]


def test_only_compliance_reviewers_decide_held_answers():
    deciders = {r["key"] for r in DEFAULT_ROLES if "reviews:act" in r["permissions"]}
    assert deciders == {"compliance_reviewer"}


def test_database_roles_match_the_canonical_definitions(db):
    stored = {r.key: r for r in db.scalars(select(Role))}
    for r in DEFAULT_ROLES:
        assert stored[r["key"]].name == r["name"]
    rohan = db.scalar(select(User).where(User.email == "rohan.das@novacorp.test"))
    assert set(rohan.role_keys) == {"employee", "trustshield_admin"}


def test_admin_cannot_decide_a_review_case(client, headers):
    r = client.post("/api/assistant/chat", json={"message": "Can I sue a vendor who delivered late?"}, headers=headers["employee"])
    case_id = r.json()["decision"]["review_case_id"]
    assert client.get(f"/api/reviewer/cases/{case_id}", headers=headers["admin"]).status_code == 200  # can view
    denied = client.post(f"/api/reviewer/cases/{case_id}/approve", json={"note": "x"}, headers=headers["admin"])
    assert denied.status_code == 403
    assert client.post(f"/api/reviewer/cases/{case_id}/approve", json={"note": "ok"}, headers=headers["reviewer"]).status_code == 200


def test_approver_names_in_employee_messages_use_role_names(client, headers):
    r = client.post("/api/agent/actions", json={"request": "Approve Arjun Mehta's expense reimbursement"}, headers=headers["finance"])
    a = r.json()
    assert a["required_approver_role"] == "people_manager"
    assert "a People Manager" in a["employee_view"]["headline"]


def test_people_get_employee_plus_one_job_role(client, headers):
    users = client.get("/api/admin/users", headers=headers["admin"]).json()
    aditya = next(u for u in users if u["email"] == "aditya.kulkarni@novacorp.test")
    two_jobs = client.patch(f"/api/admin/users/{aditya['id']}", json={"role_keys": ["people_manager", "finance_head"]}, headers=headers["admin"])
    assert two_jobs.status_code == 400 and "one job role" in two_jobs.json()["error"]["message"]
    same = client.patch(f"/api/admin/users/{aditya['id']}", json={"role_keys": ["people_manager"]}, headers=headers["admin"])
    assert same.status_code == 200 and same.json()["role_keys"] == ["employee", "people_manager"]
