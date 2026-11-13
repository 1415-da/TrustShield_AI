"""Permission scopes and the default role → scope matrix.

Roles are stored in the database (admins can edit scopes); this module provides the defaults, which are
merged into existing role rows on upgrade (additive only — an admin's removals are respected for scopes
that already existed).
"""

from __future__ import annotations

PERMISSION_CATALOGUE: dict[str, str] = {
    "assistant:use": "Use the internal AI assistant and connected workspace",
    "reviews:read": "View the human-review queue and case details",
    "reviews:act": "Approve, edit, reject, or escalate review cases",
    "policies:read": "View policies, versions, approvals, and run simulations",
    "policies:write": "Create and edit policy drafts, activate, deactivate, roll back, archive",
    "policies:approve": "Approve, reject, or request changes on submitted policy versions",
    "documents:read": "View knowledge-source documents",
    "documents:write": "Upload, reindex, and delete documents",
    "analytics:read": "View governance dashboards",
    "audit:read": "View the audit log",
    "users:manage": "Manage users and role permissions",
    "apps:manage": "Manage connected apps and API keys",
    "tests:run": "Manage and run guardrail evaluation tests",
    "settings:read": "View gateway configuration",
    "compliance:read": "View compliance evidence reports",
    "compliance:write": "Generate, schedule, and withdraw compliance evidence reports",
    "integrations:read": "View workspace / Slack integration status and events",
    "integrations:manage": "Configure the Slack integration and channel policy mapping",
    "actions:request": "Ask an AI agent to perform an action",
    "actions:approve": "Approve agent actions routed to one of your roles",
    "agents:read": "View the Agent Control Center",
    "agents:manage": "Manage agent action policies and execute/compensate actions",
    "actions:finance": "Action scope: may initiate financial actions (reimbursements, refunds)",
    "actions:hr": "Action scope: may initiate HR record changes (leave, compensation)",
    "actions:it": "Action scope: may initiate access changes and destructive IT actions",
    "data:compensation": "Data scope: may receive compensation data (salary bands)",
    "data:financial": "Data scope: may receive financial account data",
}

# The admin runs the workspace but never decides on content or money: held answers, policy versions and agent
# actions are approved by the role accountable for that risk (separation of duties).
_ADMIN_EXCLUDED = {"reviews:act", "policies:approve", "actions:approve", "actions:finance", "actions:hr", "actions:it"}
_ADMIN = [p for p in PERMISSION_CATALOGUE if not p.startswith("data:") and p not in _ADMIN_EXCLUDED]

# Every person holds `employee` (use the assistant, request actions) plus at most one job role below.
# Names here are the canonical display names used everywhere — UI labels, docs and messages follow them.
DEFAULT_ROLES: list[dict] = [
    {"key": "employee", "name": "Employee",
     "description": "Everyone in the organization. Asks the assistant and requests agent actions; approves nothing.",
     "permissions": ["assistant:use", "actions:request"]},
    {"key": "hr_manager", "name": "HR Manager",
     "description": "Sees salary bands (compensation scope). Approves salary changes and sensitive HR look-ups.",
     "permissions": ["assistant:use", "actions:request", "actions:approve", "actions:hr", "data:compensation"]},
    {"key": "finance_analyst", "name": "Finance Analyst",
     "description": "Sees financial account data (financial scope). Requests financial actions; small ones run without approval.",
     "permissions": ["assistant:use", "actions:request", "actions:finance", "data:financial"]},
    {"key": "finance_head", "name": "Finance Head",
     "description": "Approves reimbursements above INR 50,000 and vendor refunds above INR 10,000. Reads compliance evidence.",
     "permissions": ["assistant:use", "actions:request", "actions:approve", "actions:finance", "data:financial", "compliance:read"]},
    {"key": "people_manager", "name": "People Manager",
     "description": "Approves reimbursements of INR 5,000–50,000, leave-balance changes and other record updates.",
     "permissions": ["assistant:use", "actions:request", "actions:approve", "actions:hr"]},
    {"key": "compliance_reviewer", "name": "Compliance Reviewer",
     "description": "Decides held answers in the review queue, approves policy versions and exceptions, approves messages "
                    "to external parties, and owns compliance evidence.",
     "permissions": ["assistant:use", "actions:request", "reviews:read", "reviews:act", "policies:read", "policies:approve",
                     "documents:read", "compliance:read", "compliance:write", "actions:approve"]},
    {"key": "security_admin", "name": "Security Admin",
     "description": "Approves access revocations, record deletions and permission changes. Reads the audit log.",
     "permissions": ["assistant:use", "actions:request", "actions:approve", "actions:it", "audit:read", "agents:read", "policies:read"]},
    {"key": "security_auditor", "name": "Security Auditor",
     "description": "Read-only oversight: audit log and chain verification, dashboards, policies, reviews, evidence, "
                    "integrations and agents. Approves nothing.",
     "permissions": ["audit:read", "analytics:read", "policies:read", "reviews:read", "documents:read", "settings:read",
                     "compliance:read", "integrations:read", "agents:read"]},
    {"key": "trustshield_admin", "name": "TrustShield Admin",
     "description": "Runs the workspace: policies, documents, users, apps, integrations and agents. Can view the review "
                    "queue but not decide it, has no data scopes, and cannot approve its own changes.",
     "permissions": _ADMIN},
]

ROLE_ORDER = ["trustshield_admin", "security_admin", "security_auditor", "compliance_reviewer", "finance_head", "hr_manager",
              "people_manager", "finance_analyst", "employee"]


def normalize_role_keys(keys: list[str]) -> list[str]:
    """Everyone is an employee plus at most one job role. Returns ["employee", <job role>?] or raises ValueError."""
    jobs = list(dict.fromkeys(k for k in keys if k != "employee"))
    if len(jobs) > 1:
        raise ValueError("Give each person one job role (plus Employee). Approvals are split by role, so one person "
                         "holding two job roles would weaken separation of duties.")
    return ["employee", *jobs]
