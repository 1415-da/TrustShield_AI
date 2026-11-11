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

_ADMIN_EXCLUDED = {"policies:approve", "actions:approve", "actions:finance", "actions:hr", "actions:it"}
_ADMIN = [p for p in PERMISSION_CATALOGUE if not p.startswith("data:") and p not in _ADMIN_EXCLUDED]

DEFAULT_ROLES: list[dict] = [
    {"key": "employee", "name": "Employee", "description": "Standard NovaCorp employee.",
     "permissions": ["assistant:use", "actions:request"]},
    {"key": "hr_manager", "name": "HR Manager", "description": "HR leadership with compensation data scope; approves HR actions.",
     "permissions": ["assistant:use", "actions:request", "actions:approve", "actions:hr", "data:compensation"]},
    {"key": "finance_analyst", "name": "Finance Analyst", "description": "Finance team with financial data scope.",
     "permissions": ["assistant:use", "actions:request", "actions:finance", "data:financial"]},
    {"key": "finance_head", "name": "Finance Head", "description": "Approves high-value financial actions.",
     "permissions": ["assistant:use", "actions:request", "actions:approve", "actions:finance", "data:financial", "compliance:read"]},
    {"key": "people_manager", "name": "People Manager", "description": "Line manager; approves mid-value reimbursements and leave changes.",
     "permissions": ["assistant:use", "actions:request", "actions:approve", "actions:hr"]},
    {"key": "compliance_reviewer", "name": "Compliance Reviewer",
     "description": "Works the review queue, approves policy versions, and owns compliance evidence.",
     "permissions": ["assistant:use", "actions:request", "reviews:read", "reviews:act", "policies:read", "policies:approve",
                     "documents:read", "compliance:read", "compliance:write", "actions:approve"]},
    {"key": "security_admin", "name": "Security Admin", "description": "Approves access revocations and destructive actions.",
     "permissions": ["assistant:use", "actions:request", "actions:approve", "actions:it", "audit:read", "agents:read", "policies:read"]},
    {"key": "security_auditor", "name": "Security / Audit Viewer",
     "description": "Read-only oversight of audit logs, risk analytics, evidence, integrations, and agents.",
     "permissions": ["audit:read", "analytics:read", "policies:read", "reviews:read", "documents:read", "settings:read",
                     "compliance:read", "integrations:read", "agents:read"]},
    {"key": "trustshield_admin", "name": "TrustShield Admin",
     "description": "Owns policies, documents, users, integrations and agents. No data scopes and cannot approve its own changes.",
     "permissions": _ADMIN},
]

ROLE_ORDER = ["trustshield_admin", "security_admin", "security_auditor", "compliance_reviewer", "finance_head", "hr_manager",
              "people_manager", "finance_analyst", "employee"]
