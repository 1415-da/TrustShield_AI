"""Permission scopes and the default role → scope matrix.

Roles are stored in the database (admins can edit scopes); this module only provides the seed defaults
and the catalogue shown in the Users & Roles screen.
"""

from __future__ import annotations

PERMISSION_CATALOGUE: dict[str, str] = {
    "assistant:use": "Use the internal AI assistant",
    "reviews:read": "View the human-review queue and case details",
    "reviews:act": "Approve, edit, reject, or escalate review cases",
    "policies:read": "View policies and run simulations",
    "policies:write": "Create, edit, activate, and archive policies",
    "documents:read": "View knowledge-source documents",
    "documents:write": "Upload, reindex, and delete documents",
    "analytics:read": "View governance dashboards",
    "audit:read": "View the audit log",
    "users:manage": "Manage users and role permissions",
    "apps:manage": "Manage connected apps and API keys",
    "tests:run": "Manage and run guardrail evaluation tests",
    "settings:read": "View gateway configuration",
    "data:compensation": "Data scope: may receive compensation data (salary bands)",
    "data:financial": "Data scope: may receive financial account data",
}

_ADMIN = [p for p in PERMISSION_CATALOGUE if not p.startswith("data:")]

DEFAULT_ROLES: list[dict] = [
    {"key": "employee", "name": "Employee", "description": "Standard NovaCorp employee.",
     "permissions": ["assistant:use"]},
    {"key": "hr_manager", "name": "HR Manager", "description": "HR leadership with compensation data scope.",
     "permissions": ["assistant:use", "data:compensation"]},
    {"key": "finance_analyst", "name": "Finance Analyst", "description": "Finance team with financial data scope.",
     "permissions": ["assistant:use", "data:financial"]},
    {"key": "compliance_reviewer", "name": "Compliance Reviewer",
     "description": "Works the human-in-the-loop review queue.",
     "permissions": ["assistant:use", "reviews:read", "reviews:act", "policies:read", "documents:read"]},
    {"key": "security_auditor", "name": "Security / Audit Viewer",
     "description": "Read-only oversight of audit logs and risk analytics.",
     "permissions": ["audit:read", "analytics:read", "policies:read", "reviews:read", "documents:read", "settings:read"]},
    {"key": "trustshield_admin", "name": "TrustShield Admin",
     "description": "Owns policies, documents, users, and connected apps. No sensitive-data scopes by default.",
     "permissions": _ADMIN},
]
