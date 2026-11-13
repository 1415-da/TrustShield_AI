export interface DocEntry {
  slug: string;
  title: string;
  group: string;
  summary: string;
}

export const DOCS: DocEntry[] = [
  { slug: "quickstart", group: "Getting started", title: "Quickstart", summary: "Create a workspace, upload policies, add a Compliance Reviewer and send your first governed request." },
  { slug: "concepts", group: "Getting started", title: "How the gateway decides", summary: "The pipeline, the five input decisions, the five output decisions and trust statuses." },
  { slug: "workspaces", group: "Getting started", title: "Workspaces & people", summary: "Organization isolation, inviting colleagues, and who should hold which role." },

  { slug: "policies", group: "Govern", title: "Policies & approvals", summary: "Rule types, versioning, two-person approval, simulation, rollback and exceptions." },
  { slug: "knowledge", group: "Govern", title: "Connecting knowledge sources", summary: "Upload the documents answers are grounded in and cite; trusted vs untrusted sources." },
  { slug: "review", group: "Govern", title: "Human review", summary: "What gets held, how reviewers decide, SLAs and how the employee is updated." },
  { slug: "agent-actions", group: "Govern", title: "Agent actions", summary: "Approval rules for actions agents take: thresholds, approver roles, execution and compensation." },
  { slug: "evidence", group: "Govern", title: "Compliance evidence", summary: "Immutable, reproducible reports for auditors, with schedules and exports." },

  { slug: "guard-api", group: "Developers", title: "Guard API", summary: "Put TrustShield in front of your own LLM app with two server-side calls." },
  { slug: "assistant-api", group: "Developers", title: "Assistant & actions API", summary: "Use TrustShield's hosted assistant and agent actions from your own front end." },
  { slug: "slack", group: "Developers", title: "Slack & team channels", summary: "Channel policy profiles, the built-in workspace, and connecting a real Slack app." },
  { slug: "self-hosting", group: "Developers", title: "Self-hosting", summary: "Docker Compose, ports, environment variables, model providers and upgrades." },

  { slug: "roles", group: "Reference", title: "Roles & permissions", summary: "Every built-in role and the permission and data scopes it carries." },
  { slug: "security", group: "Reference", title: "Security model", summary: "Invariants, data handling, audit integrity and what TrustShield does not claim." },
];

export const DOC_GROUPS = Array.from(new Set(DOCS.map((d) => d.group)));
