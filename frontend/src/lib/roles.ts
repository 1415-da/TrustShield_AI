/**
 * The single frontend source of truth for roles. Names mirror backend `app/core/permissions.py` (DEFAULT_ROLES);
 * every label, persona card, docs table and landing page on the site is derived from this list.
 *
 * Model: everyone holds `employee`, plus at most one job role. Each kind of approval belongs to exactly one role.
 */
export interface RoleInfo {
  key: string;
  label: string;
  /** Who typically holds it. */
  who: string;
  /** What the role is for, in one line. */
  purpose: string;
  /** What this role approves ("—" when it approves nothing). */
  approves: string;
  /** Key permission and data scopes, for the docs. */
  scopes: string;
  /** Where the person lands after signing in, and what that page is called. */
  home: string;
  homeLabel: string;
}

export const ROLES: RoleInfo[] = [
  {
    key: "employee", label: "Employee", who: "Everyone in the organization",
    purpose: "Asks the assistant and requests agent actions.", approves: "—",
    scopes: "assistant:use, actions:request", home: "/assistant", homeLabel: "Assistant",
  },
  {
    key: "hr_manager", label: "HR Manager", who: "HR leadership",
    purpose: "Sees salary bands in answers (compensation scope).", approves: "Salary changes and sensitive HR look-ups",
    scopes: "data:compensation, actions:hr, actions:approve", home: "/assistant", homeLabel: "Assistant",
  },
  {
    key: "finance_analyst", label: "Finance Analyst", who: "Finance staff",
    purpose: "Sees financial account data; requests financial actions (small ones run without approval).", approves: "—",
    scopes: "data:financial, actions:finance", home: "/assistant", homeLabel: "Assistant",
  },
  {
    key: "people_manager", label: "People Manager", who: "Team and line managers",
    purpose: "Approves day-to-day changes for their people.", approves: "Reimbursements of INR 5,000–50,000, leave and record updates",
    scopes: "actions:hr, actions:approve", home: "/console/agents", homeLabel: "Agent approvals",
  },
  {
    key: "finance_head", label: "Finance Head", who: "Head of Finance / CFO",
    purpose: "Approves high-value money movements; reads compliance evidence.", approves: "Reimbursements above INR 50,000 and vendor refunds above INR 10,000",
    scopes: "data:financial, actions:approve, compliance:read", home: "/console/agents", homeLabel: "Agent approvals",
  },
  {
    key: "security_admin", label: "Security Admin", who: "IT security",
    purpose: "Approves risky IT actions; reads the audit log.", approves: "Access revocations, record deletions and permission changes",
    scopes: "actions:it, actions:approve, audit:read", home: "/console/agents", homeLabel: "Agent approvals",
  },
  {
    key: "compliance_reviewer", label: "Compliance Reviewer", who: "Legal and compliance",
    purpose: "Works the review queue and owns compliance evidence.",
    approves: "Held answers, policy versions, policy exceptions and messages to external parties",
    scopes: "reviews:act, policies:approve, compliance:write, actions:approve", home: "/console/reviews", homeLabel: "Review queue",
  },
  {
    key: "security_auditor", label: "Security Auditor", who: "Internal audit / InfoSec",
    purpose: "Read-only oversight: audit log and chain verification, dashboards, reviews, evidence.", approves: "—",
    scopes: "audit:read, analytics:read, compliance:read (read-only)", home: "/console/audit", homeLabel: "Audit log",
  },
  {
    key: "trustshield_admin", label: "TrustShield Admin", who: "AI platform owner",
    purpose: "Runs the workspace: policies, documents, users, apps, integrations and agents. No data scopes.",
    approves: "— (cannot approve anything, including its own changes)",
    scopes: "policies:write, documents:write, users:manage, apps:manage, agents:manage", home: "/console", homeLabel: "Console overview",
  },
];

export const ROLE_BY_KEY: Record<string, RoleInfo> = Object.fromEntries(ROLES.map((r) => [r.key, r]));
export const ROLE_LABELS: Record<string, string> = Object.fromEntries(ROLES.map((r) => [r.key, r.label]));

