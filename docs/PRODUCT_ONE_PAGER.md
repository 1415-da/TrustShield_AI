# TrustShield AI — One-Pager

**Ship AI your security team can trust.**

TrustShield AI is an installable governance gateway that sits between employees and an internal AI assistant. It inspects every request before it reaches the model, validates every answer before it reaches the employee, routes uncertain cases to human reviewers, and records a tamper-evident decision trail.

---

### The problem

Internal AI assistants stall in security review. Employees paste sensitive data into prompts, models answer questions the asker isn't entitled to, answers aren't verifiably grounded in company policy, and nobody can reconstruct what happened after an incident.

### What TrustShield does

| Capability | What it means in practice |
|---|---|
| **Input guardrails** | Prompt-injection scoring, PII detection (Microsoft Presidio + custom recognizers), sensitive-topic classification, role-permission checks |
| **Output validation** | PII and sensitive-number leak detection, grounding risk signal against cited policy evidence |
| **Policy engine** | Rules stored in the database, versioned, editable in Policy Studio, testable in a simulator before activation |
| **Human review** | Prioritised queue with SLA aging; approve, edit, reject, or escalate with notes |
| **Audit trail** | Append-only, hash-chained events with request ID, role, policies triggered, risk scores, model, latency |
| **Role-based access** | Employees, reviewers, admins, and auditors each see exactly what their role allows |

### New in Release 2

| Capability | What it means in practice |
|---|---|
| **Policy versioning & approvals** | Drafts, a second-person approval with diff and impact analysis, deliberate activation, one-click rollback — production only runs approved versions |
| **Compliance Evidence Center** | Audit-ready governance reports in minutes: immutable, hashed, reproducible from audit records, exportable as HTML, Markdown or a JSON evidence package |
| **Slack & connected workspace** | Team channels answered through the same guardrails, review workflow and audit trail; channel-level policy profiles |
| **Agent action controls** | Agents request actions; TrustShield classifies, checks permissions and approval rules, routes to the right approver, and executes exactly once |

### Every request gets one of five decisions

`ALLOW` · `REDACT` · `BLOCK` · `REVIEW` · `ESCALATE`

…and every answer one of five outcomes: `SHOW` · `SHOW_WITH_WARNING` · `REDACT` · `SEND_TO_REVIEW` · `BLOCK`.

### Who it's for

- **Security & compliance leaders** who need to approve an AI rollout.
- **IT / platform teams** who own the assistant and need enforceable controls.
- **Employees** who want useful answers and clear explanations when something is off-limits.

### How it's built

Next.js 14 · FastAPI · PostgreSQL 15 · Presidio · OpenAI-compatible provider interface with an offline mock · Docker Compose.

### Measured, not claimed

The built-in Test Center runs 49 labelled scenarios (safe questions, salary access by role, card/bank requests, prompt injection, indirect injection, low-confidence answers, output leaks) and reports pass rate, false positives, and false negatives. All metrics shown in the product are computed from the seeded synthetic demo — there are no production performance claims.

### Trade-offs we chose deliberately

- **Deterministic heuristics over ML classifiers** — explainable, testable, and fast; pluggable later.
- **Grounding is a risk signal, not truth** — low scores route to humans instead of pretending to detect hallucinations.
- **Mask before storage** — even the employee's own message is stored with sensitive values masked.
- **Single-tenant, no SSO** — focus on the governance loop, not enterprise plumbing.

### Roadmap

pgvector ANN retrieval → streaming with incremental scanning → OIDC SSO → shadow-mode policies → ML classifier plugins → SIEM export.
