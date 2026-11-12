"""Organization workspaces: self-service creation, provisioning, and the onboarding checklist.

A new organization gets an isolated workspace with:
  * its first admin (who can invite colleagues and assign roles),
  * the TrustShield baseline policy pack, already active,
  * channel policy profiles and team channels,
  * its own first-party web assistant app,
  * the agent action registry and default approval rules,
  * the restrictive scenarios from the evaluation suite, so the Test Center works on day one.

It starts with no knowledge sources and no people directory: those are the organization's own data.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.core.security import hash_password
from app.core.tenancy import ALL_ORGS, use_org
from app.models import (ApiKey, AuditEvent, ConnectedApp, Document, Organization, Policy, PolicyProfile, Role, TestCase, User,
                        WorkspaceChannel)
from app.services import audit, policies

# The founder is the workspace admin: policies, apps, users. They invite reviewers and approvers.
FOUNDER_ROLES = ("trustshield_admin",)

FIRST_PARTY_APP = {"name": "Web Assistant", "slug": "web-assistant", "owner_team": "IT",
                   "description": "Your employees' assistant, served by TrustShield."}

STARTER_CHANNELS = [
    {"external_id": "WS-GENERAL", "name": "general", "profile_key": "general", "description": "Company-wide questions.",
     "policy_hint": "General profile."},
    {"external_id": "WS-HRHELP", "name": "hr-help", "profile_key": "hr", "description": "Leave, onboarding, and HR policy questions.",
     "policy_hint": "HR profile · named colleagues' pay and personal details are never shared here."},
    {"external_id": "WS-FINHELP", "name": "finance-help", "profile_key": "finance",
     "description": "Expenses, refunds, procurement, and vendor payments.",
     "policy_hint": "Finance profile · requests to change payment or bank instructions are held for review."},
    {"external_id": "WS-ITSUP", "name": "it-support", "profile_key": "it_security",
     "description": "Access, passwords, devices, and security incidents.",
     "policy_hint": "IT security profile · credentials are never shared."},
]

RESTRICTIVE = {"BLOCK", "ESCALATE", "REVIEW", "REDACT"}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "workspace"


def _unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    slug, n = base, 2
    while db.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def baseline_policies() -> list[dict]:
    from app.seed import data

    specs = []
    for spec in data.POLICIES:
        if spec.get("seed_stage", "active") != "active":
            continue
        clean = {k: v for k, v in spec.items() if k not in ("seed_stage", "seed_history", "is_active")}
        clean["rules"] = [dict(r) for r in clean["rules"]]
        specs.append(clean)
    return specs


def baseline_test_cases() -> list[dict]:
    """Scenarios whose expected outcome is restrictive. They don't depend on a policy library or directory."""
    from app.seed import data

    return [dict(tc) for tc in data.TEST_CASES if set(tc["expected_input_actions"]) <= RESTRICTIVE]


def create_organization(db: Session, *, name: str, full_name: str, email: str, password: str, industry: str = "",
                        size: str = "") -> tuple[Organization, User]:
    from app.seed import data
    from app.seed.loader import ensure_roles
    from app.services import agent_actions

    email = email.strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email).execution_options(**ALL_ORGS)):
        raise Conflict("An account with this email already exists")

    roles = ensure_roles(db)
    org = Organization(name=name.strip(), slug=_unique_slug(db, name), industry=industry, size=size)
    db.add(org)
    db.flush()
    use_org(db, org.id)

    admin = User(email=email, full_name=full_name.strip(), department="IT", title="TrustShield Admin",
                 password_hash=hash_password(password), roles=[roles[k] for k in FOUNDER_ROLES])
    db.add(admin)
    db.flush()
    audit.record(db, "organization.created", **audit.actor_fields(admin),
                 details={"organization": org.name, "slug": org.slug, "industry": industry[:80], "size": size[:40]})

    for p in data.POLICY_PROFILES:
        db.add(PolicyProfile(**p))
    for c in STARTER_CHANNELS:
        db.add(WorkspaceChannel(**c, source="internal"))
    db.add(ConnectedApp(**FIRST_PARTY_APP))
    db.add(ConnectedApp(name="Connected Workspace", slug="connected-workspace", owner_team="IT",
                        description="TrustShield's built-in team channels."))
    for tc in baseline_test_cases():
        db.add(TestCase(**tc))
    db.commit()

    for spec in baseline_policies():
        policies.adopt_baseline(db, spec, admin)
    agent_actions.ensure_registry(db)
    db.commit()
    return org, admin


def invite_user(db: Session, inviter: User, *, email: str, full_name: str, role_keys: list[str], password: str,
                department: str = "General Operations", title: str = "") -> User:
    email = email.strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email).execution_options(**ALL_ORGS)):
        raise Conflict("An account with this email already exists")
    roles = list(db.scalars(select(Role).where(Role.key.in_(role_keys))))
    if not roles:
        roles = list(db.scalars(select(Role).where(Role.key == "employee")))
    user = User(email=email, full_name=full_name.strip(), department=department, title=title or roles[0].name,
                password_hash=hash_password(password), roles=roles)
    db.add(user)
    db.flush()
    audit.record(db, "user.invited", **audit.actor_fields(inviter),
                 details={"user_id": user.id, "roles": [r.key for r in roles], "email_domain": email.split("@")[-1]})
    db.commit()
    return user


def summary(db: Session, org: Organization) -> dict[str, Any]:
    """Organization profile plus the onboarding checklist, computed from real state."""
    count = lambda model, *where: db.scalar(select(func.count(model.id)).where(*where)) or 0  # noqa: E731
    users = count(User)
    documents = count(Document)
    keys = count(ApiKey, ApiKey.revoked_at.is_(None))
    active_policies = count(Policy, Policy.active_version_id.is_not(None))
    requests = count(AuditEvent, AuditEvent.event_type.like("%.request"))
    reviewers = db.scalar(select(func.count(User.id)).where(User.roles.any(Role.key.in_(("compliance_reviewer", "trustshield_admin")))))
    steps = [
        {"key": "policies", "title": "Baseline policies are active", "done": active_policies > 0,
         "detail": f"{active_policies} policies enforcing", "href": "/console/policies"},
        {"key": "documents", "title": "Upload your policy documents", "done": documents > 0,
         "detail": "Answers are grounded in and cite these sources", "href": "/console/documents"},
        {"key": "team", "title": "Invite a reviewer and your team", "done": users > 1,
         "detail": "Policy changes need a second approver", "href": "/console/users"},
        {"key": "first_request", "title": "Ask your first governed question", "done": requests > 0,
         "detail": "Try it in the assistant or a team channel", "href": "/assistant"},
        {"key": "api_key", "title": "Connect an app with an API key", "done": keys > 0,
         "detail": "Route your own assistant through the gateway", "href": "/console/apps"},
    ]
    return {
        "id": org.id, "name": org.name, "slug": org.slug, "industry": org.industry, "size": org.size, "is_demo": org.is_demo,
        "created_at": org.created_at,
        "stats": {"users": users, "documents": documents, "active_policies": active_policies, "api_keys": keys,
                  "requests": requests, "reviewers": reviewers},
        "onboarding": steps, "onboarding_complete": all(s["done"] for s in steps),
    }
