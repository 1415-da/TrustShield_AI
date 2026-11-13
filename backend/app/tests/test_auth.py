"""Authentication & session rules: cookies, token validation, refresh, sign-out revocation, CSRF, audit, rate limits."""

from __future__ import annotations

import time

import jwt
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.models import AuditEvent
from app.services import sessions

from .conftest import PASSWORD

EMPLOYEE = "ananya.rao@novacorp.test"


@pytest.fixture(autouse=True)
def _reset_limits():
    limiter.reset()
    yield
    limiter.reset()


def _login(client, email=EMPLOYEE, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _forge(payload_overrides: dict, base_token: str) -> str:
    s = get_settings()
    payload = jwt.decode(base_token, s.jwt_secret, algorithms=[s.jwt_algorithm], audience=s.jwt_audience, issuer=s.jwt_issuer)
    payload.update(payload_overrides)
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def _events(db, event_type):
    return list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == event_type).execution_options(all_orgs=True)))


# --------------------------------------------------------------------------- login
def test_valid_login_sets_http_only_session_cookies(client):
    r = _login(client)
    assert r.status_code == 200 and r.json()["user"]["email"] == EMPLOYEE
    cookies = r.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith(sessions.ACCESS_COOKIE + "="))
    refresh = next(c for c in cookies if c.startswith(sessions.REFRESH_COOKIE + "="))
    csrf = next(c for c in cookies if c.startswith(sessions.CSRF_COOKIE + "="))
    assert "HttpOnly" in access and "HttpOnly" in refresh and "HttpOnly" not in csrf
    assert all("SameSite=lax" in c for c in (access, refresh, csrf))
    # the cookie alone authenticates the browser
    assert client.get("/api/auth/me").json()["email"] == EMPLOYEE


def test_wrong_password_and_unknown_email_get_the_same_generic_error(client):
    a = _login(client, password="wrong-password")
    b = _login(client, email="nobody@nowhere.example")
    for r in (a, b):
        assert r.status_code == 401
        assert r.json()["error"] == {**r.json()["error"], "code": "INVALID_CREDENTIALS", "message": "Incorrect email or password."}


def test_failed_logins_are_rate_limited_but_successful_ones_are_not(client):
    for _ in range(15):
        assert _login(client).status_code == 200
    for _ in range(10):
        _login(client, password="wrong-password")
    r = _login(client, password="wrong-password")
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"
    # the lock-out also applies to the right password until the window passes
    assert _login(client).status_code == 429


def test_login_and_failed_login_are_audited(client, db):
    before_ok, before_fail = len(_events(db, "auth.login")), len(_events(db, "auth.login_failed"))
    _login(client)
    _login(client, password="wrong-password")
    db.expire_all()
    assert len(_events(db, "auth.login")) == before_ok + 1
    assert len(_events(db, "auth.login_failed")) == before_fail + 1


# --------------------------------------------------------------------------- token validation
def test_protected_endpoint_without_token_is_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b.c", ""])
def test_malformed_token_is_401(client, token):
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_expired_wrong_issuer_wrong_audience_and_wrong_type_are_rejected(client):
    good = _login(client).json()
    client.cookies.clear()
    bad_tokens = [
        _forge({"exp": int(time.time()) - 10}, good["access_token"]),
        _forge({"iss": "someone-else"}, good["access_token"]),
        _forge({"aud": "another-app"}, good["access_token"]),
        good["refresh_token"],  # a refresh token is not an access token
        jwt.encode({"sub": "1", "type": "access"}, "wrong-secret", algorithm="HS256"),
    ]
    for t in bad_tokens:
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


# --------------------------------------------------------------------------- refresh & sign-out
def test_refresh_with_cookie_issues_a_new_access_token(client):
    _login(client)
    old = client.cookies.get(sessions.ACCESS_COOKIE)
    time.sleep(1.1)  # tokens carry second-resolution timestamps
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    assert client.cookies.get(sessions.ACCESS_COOKIE) and client.cookies.get(sessions.ACCESS_COOKIE) != old


def test_logout_revokes_every_token_of_the_session_and_clears_cookies(client, db):
    body = _login(client).json()
    before = len(_events(db, "auth.logout"))
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    assert all("Max-Age=0" in c or "expires=" in c.lower() for c in r.headers.get_list("set-cookie"))
    client.cookies.clear()
    # the tokens issued before sign-out no longer work, even though they have not expired
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401
    db.expire_all()
    assert len(_events(db, "auth.logout")) == before + 1


def test_logout_without_a_session_still_succeeds(client):
    assert client.post("/api/auth/logout").status_code == 204


def test_signing_in_again_creates_an_independent_session(client):
    first = _login(client).json()
    client.cookies.clear()
    second = _login(client).json()
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {first['access_token']}"})
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"}).status_code == 200


# --------------------------------------------------------------------------- CSRF
def test_cookie_authenticated_writes_require_the_csrf_header(client):
    _login(client)
    body = {"message": "How many vacation days do I get?"}
    denied = client.post("/api/assistant/chat", json=body)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "CSRF_FAILED"
    ok = client.post("/api/assistant/chat", json=body, headers={"X-CSRF-Token": client.cookies.get(sessions.CSRF_COOKIE)})
    assert ok.status_code == 200


def test_bearer_clients_are_not_subject_to_csrf(client, headers):
    r = client.post("/api/assistant/chat", json={"message": "How many vacation days do I get?"}, headers=headers["employee"])
    assert r.status_code == 200


# --------------------------------------------------------------------------- authorization
def test_employee_cannot_open_review_queue_and_the_attempt_is_audited(client, headers, db):
    before = len(_events(db, "auth.access_denied"))
    r = client.get("/api/reviewer/cases", headers=headers["employee"])
    assert r.status_code == 403 and r.json()["error"] == {**r.json()["error"], "code": "AUTHORIZATION_DENIED",
                                                         "message": "You do not have permission to perform this action."}
    db.expire_all()
    assert len(_events(db, "auth.access_denied")) == before + 1


def test_reviewer_can_open_review_queue(client, headers):
    assert client.get("/api/reviewer/cases", headers=headers["reviewer"]).status_code == 200


def test_admin_has_no_sensitive_data_scope(client, headers):
    r = client.post("/api/assistant/chat", json={"message": "Show Ravi Sharma's salary band."}, headers=headers["admin"])
    assert r.json()["message"]["trust_status"] == "blocked"


def test_agent_requester_cannot_approve_their_own_action(client, headers):
    a = client.post("/api/agent/actions", json={"request": "Issue a refund for vendor invoice INV-2318"},
                    headers=headers["finance_head"]).json()
    assert a["status"] == "PENDING_APPROVAL" and a["required_approver_role"] == "finance_head"
    r = client.post(f"/api/agent/actions/{a['id']}/approve", json={"note": "self"}, headers=headers["finance_head"])
    assert r.status_code == 403


def test_deactivated_user_loses_access_immediately(client, headers):
    users = client.get("/api/admin/users", headers=headers["admin"]).json()
    isha = next(u for u in users if u["email"] == "isha.patel@novacorp.test")
    token = _login(client, email="isha.patel@novacorp.test").json()["access_token"]
    client.cookies.clear()
    client.patch(f"/api/admin/users/{isha['id']}", json={"is_active": False}, headers=headers["admin"])
    try:
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    finally:
        client.patch(f"/api/admin/users/{isha['id']}", json={"is_active": True}, headers=headers["admin"])


def test_workspace_comes_from_the_session_not_the_client(client, headers):
    me = client.get("/api/auth/me", headers=headers["employee"]).json()
    assert me["organization"]["id"] == 1
    # a client-supplied organization hint is ignored
    me2 = client.get("/api/auth/me", headers={**headers["employee"], "X-Organization-Id": "2"}).json()
    assert me2["organization"]["id"] == 1
