# TrustShield AI

**Ship AI your security team can trust.**

TrustShield is an installable AI governance gateway. It sits between employees and an internal AI assistant. It stops unsafe or unauthorised requests before they reach the model, validates answers before they reach a person, masks sensitive data, sends uncertain or high-risk cases to human reviewers, and keeps a tamper-evident audit trail of every decision.

This repository is a complete, portfolio-quality MVP built around a fictional company, **NovaCorp Technologies**. Every person, record, and identifier in it is synthetic.

```
Employee app ──► TrustShield gateway ──────────────────────────────► LLM provider
                 │ input guardrails → policy engine → retrieval       (OpenAI-compatible,
                 │ context scan → output validation                   Azure, or offline mock)
                 ├──► Human review queue (approve / edit / reject / escalate)
                 └──► Audit log (append-only, hash-chained)
```

Every request gets exactly one decision: **ALLOW · REDACT · BLOCK · REVIEW · ESCALATE**. Every answer gets exactly one outcome: **SHOW · SHOW_WITH_WARNING · REDACT · SEND_TO_REVIEW · BLOCK**. A blocked or escalated request never reaches the model, and an automated test enforces this.

**Release 2** adds four capabilities on the same gateway:

| | |
|---|---|
| **Policy versioning & approvals** | Policies are drafted, approved by a *different* person (with a diff and an impact analysis over the evaluation suite), then activated deliberately. Only the approved, active version is ever enforced; rollback creates a new version; every transition is audited. Time-boxed **policy exceptions** follow the same approval rules. |
| **Compliance Evidence Center** | Five audit-ready reports (governance summary, sensitive data, human oversight, policy changes, exceptions), generated from append-only records, hashed, **reproducible** (one-click verify), exportable as HTML, Markdown or a JSON evidence package, and schedulable. |
| **Slack & connected workspace** | Team channels (`/workspace`) answered through the same pipeline as the assistant, with channel policy profiles, privacy for refused requests, and reviewer decisions posted back to the thread. Real Slack via Slack Bolt when credentials are set. |
| **Agent action controls** | Agents request actions; TrustShield classifies them, checks the requester's permissions and configurable approval rules (amount thresholds, roles, external recipients), routes them to the right approver, and executes them **exactly once** through controlled executors. |

---

## Quick start (Docker)

```bash
cp .env.example .env          # optional; defaults run fully offline with the built-in model
docker compose up --build
```

| Service | URL |
|---|---|
| Web app (landing, assistant, console) | http://localhost:3000 |
| API + Swagger docs | http://localhost:8000/api/docs |
| PostgreSQL 15 | localhost:5433 |

On first start the backend runs Alembic migrations and seeds the demo tenant. Seeding replays about 14 days of traffic through the real gateway and runs the evaluation suite once. Port already taken? Set `FRONTEND_PORT`, `BACKEND_PORT`, or `DB_PORT`, e.g. `FRONTEND_PORT=3200 BACKEND_PORT=8200 docker compose up --build`.

### Demo accounts

Password for all accounts: `TrustShield-demo-2024` (set via `DEMO_USER_PASSWORD`). The login page also has one-click demo sign-in.

| Person | Role | What to try |
|---|---|---|
| ananya.rao@novacorp.test | Employee | Ask policy questions; try asking for a colleague's salary |
| neha.kapoor@novacorp.test | HR Manager | Same salary question, different outcome (has `data:compensation`) |
| rahul.verma@novacorp.test | Finance Analyst | Ask in `#finance-help`; request agent actions (refunds, reimbursements) |
| kavya.menon@novacorp.test | Compliance Reviewer | Review queue, **policy approvals**, Evidence Center |
| sanjay.gupta@novacorp.test | Security / Audit Viewer | Audit log, analytics, chain verification (read-only) |
| rohan.das@novacorp.test | TrustShield Admin | Draft and activate policies, Slack settings, agent approval rules (can't approve his own changes) |
| vivek.raman@novacorp.test | Finance Head | Approve high-value agent actions (refunds over INR 10,000, reimbursements over INR 50,000) |
| aditya.kulkarni@novacorp.test | People Manager | Approve mid-value reimbursements and record updates |
| tara.bose@novacorp.test | Security Admin | Approve access revocations, deletions and escalated actions |

The 5-minute walkthrough of every feature is in **[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)**.

### Upgrading an existing installation

`docker compose up --build` on an existing volume runs migrations `0002`–`0005` and then applies idempotent reference-data upgrades (new roles, approver accounts, workspace channels, the agent registry). Migration `0002` converts every existing policy into an immutable ACTIVE/INACTIVE version labelled "pre-workflow". It cannot be downgraded automatically, so take a `pg_dump` first. Conversation and audit history is kept.

### Connect real Slack (optional)

The built-in connected workspace needs nothing. For a real Slack workspace:

1. Create a Slack app. Under **OAuth & Permissions** add bot scopes `app_mentions:read`, `channels:history`, `chat:write`, `users:read`, `users:read.email`, then install it.
2. Under **Event Subscriptions** set the request URL to `https://<your-host>/api/integrations/slack/events` and subscribe to `message.channels` and `app_mention`. Under **Interactivity** use `https://<your-host>/api/integrations/slack/interactions`.
3. Set `SLACK_ENABLED=true`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` (and optionally `SLACK_WORKSPACE_NAME`, `PUBLIC_APP_URL`) in `.env`, then restart.
4. In **Console → Slack & workspace**, click *Test connection*. Channels the bot sees are registered **disabled** until you enable them and pick a policy profile.

Slack users are matched to TrustShield accounts by verified email (`users:read.email`). Unmatched users get a polite refusal. Requests are verified by Slack Bolt (signature + timestamp), processed once per event even when Slack retries, rate-limited per user, and stored masked.

### Use a real model

```env
LLM_PROVIDER=openai            # or: azure
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=               # blank = api.openai.com; any OpenAI-compatible endpoint works
OPENAI_MODEL=gpt-4o-mini       # Azure: the deployment name
```

If no key is set, TrustShield falls back to the deterministic mock provider. The guardrails are the same either way.

---

## Local development (without Docker)

**Requirements:** Python 3.11+, Node 20+, PostgreSQL 15+.

```bash
# Backend
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm
export DATABASE_URL=postgresql://trustshield:trustshield@localhost:5432/trustshield
.venv/bin/alembic upgrade head
.venv/bin/python ../scripts/seed_demo_data.py          # --reset to start over, --no-history for a lean seed
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (separate shell)
cd frontend
npm install
BACKEND_URL=http://127.0.0.1:8000 npm run dev            # http://localhost:3000
```

`BACKEND_URL` is used by the Next.js `/api/*` rewrite, which is compiled into production builds. Set it at **build** time for `npm run build`.

---

## Testing

```bash
cd backend && .venv/bin/python -m pytest                 # 197 tests, ~9s, SQLite in-memory + offline model
scripts/run_tests.sh                                     # backend + guardrail evaluation → reports/TEST_REPORT.md
E2E_BASE_URL=http://localhost:3000 scripts/run_tests.sh --e2e   # + 11 Playwright tests (stack must be running)
```

| Suite | Count | Result |
|---|---|---|
| Backend pytest (unit, integration, API, evaluation, 4 feature suites) | 197 | all passing |
| — of which Release 2: policy workflow / evidence / Slack & workspace / agent actions | 18 / 17 / 19 / 23 | all passing |
| Seeded guardrail scenarios | 49 | 49/49 · 0 false positives (12 safe) · 0 false negatives (31 restrictive) |
| Playwright end-to-end | 11 | all passing |

These numbers come from a labelled suite written together with the guardrails. They show the rules behave as designed. They are **not** a claim about real-world accuracy. See [docs/TEST_PLAN.md](docs/TEST_PLAN.md) for the method, the traceability matrix, and known limits.

---

## What's inside

| Area | Highlights |
|---|---|
| **Input guardrails** | Weighted prompt-injection scorer (de-obfuscates leetspeak). Microsoft Presidio plus custom recognizers for salary amounts, card-like numbers (Luhn-checked), bank accounts and IFSC codes, employee IDs, Aadhaar-like *test* identifiers, and inline credentials. Sensitive-topic classifier that tells "show Ravi's salary" apart from "what is the salary policy". Role data-scopes |
| **Policy engine** | Database-driven policies with six rule types (regex, keyword, PII entity, topic, role permission, confidence threshold) on three fields (input, retrieved context, output). Versioned on every change. Inactive or unsaved drafts can be simulated |
| **Retrieval** | Paragraph-aware chunking, local hashed embeddings (no downloads), hybrid cosine + BM25 ranking, citations with source title, heading, and chunk |
| **Context guardrails** | Retrieved chunks are scanned. Injected instructions are quarantined and the answer goes to review. Card numbers and secrets inside documents are masked before the model sees them |
| **Output validation** | PII and secret leak detection, salary redaction for roles without the scope, a grounding/confidence **risk signal**, and system-prompt leak detection |
| **Human review** | Prioritised queue with SLA aging. Side-by-side request, draft, evidence, and risk view. Approve, edit (re-scanned for PII), reject, escalate, or add notes. Decisions are delivered back to the employee |
| **Audit** | Append-only (Postgres trigger + ORM guard), SHA-256 hash chain with a verification endpoint. Every request records request ID, user and role, app, policies triggered, input and output risk, action, redaction count, review case, model, latency, and content hash |
| **Policy lifecycle** | Immutable versions, DB-enforced single active version, second-person approval, diff viewer, impact analysis, rollback, comments, exceptions, policy audit history |
| **Evidence** | Five report types, filters, hashing, verification, HTML/Markdown/JSON export, schedules, retention, source-record drawer |
| **Workspace & Slack** | Channel feed with trust badges and citations, channel policy profiles, Slack Bolt adapter, idempotent retries, delivery log with retry |
| **Agents** | Action catalogue (8 categories), approval rules, approvals inbox, controlled executors, compensation, request idempotency, action audit trail, employee action cards |
| **Console** | Overview, Policy Studio & approvals, Exceptions, Simulator, Knowledge sources, Review queue, Agent Control Center, Evidence Center, Audit log, Test center, Users & roles, Slack & workspace, Connected apps, Settings |

### Repository layout

```
backend/   FastAPI app (core, api, models, schemas, services, guardrails, workers, seed, tests), Alembic
frontend/  Next.js 14 App Router + Tailwind (shadcn-style components), Recharts, Playwright tests
scripts/   seed_demo_data.py · run_tests.sh · generate_test_report.py
docs/      PRODUCT_ONE_PAGER · PRD · ARCHITECTURE · API · TEST_PLAN · DEMO_SCRIPT
```

---

## Security and privacy notes

- The browser only calls same-origin `/api/*`. No frontend code path reaches an LLM, and provider keys exist only in the backend container.
- Messages, review cases, and audit details store **masked** text. Raw content is kept only as a SHA-256 hash.
- API keys are shown once and stored as hashes. Settings never return secrets.
- **Change `JWT_SECRET` before exposing a deployment.** The console shows a warning while it is still the default.
- MVP trade-off: JWTs are kept in `localStorage`. Production should use httpOnly SameSite cookies.

---

## Portfolio notes

### The product problem
Internal AI assistants stall in security review. TrustShield gives security a single control point with explainable decisions, and gives employees clear explanations instead of silent refusals.

### Design decisions and trade-offs

| Decision | Why | Cost |
|---|---|---|
| Transparent heuristics (weighted signals, lexicons, intent modifiers) instead of ML classifiers | Deterministic, explainable to auditors, testable offline, fast (≈60 ms per gateway pass with the mock) | Lower recall on novel phrasing. Mitigated by layered checks and admin-editable rules |
| Grounding is labelled a **risk signal** | Heuristic overlap isn't truth. Low scores go to people instead of producing confident claims | Some reviewer load. Thresholds can be tuned in Policy Studio |
| Mask before storage, even the employee's own message | Logs and history are where data leaks live | Employees see masked versions of their own past messages |
| ESCALATE ranks above BLOCK | Escalation is a block plus a mandatory human review | — |
| Embeddings stored as JSON and scored in-process | Zero extra infrastructure at MVP scale | Needs pgvector beyond roughly 100k chunks |
| Single-tenant, no SSO | Keeps focus on the governance loop | Enterprise plumbing is on the roadmap |

### What I would measure in a real pilot
Guardrail recall and false-positive rate on an expanding labelled set, gateway overhead (p50/p95, logged per request), review volume and time-to-resolution against SLA, share of requests answered without human touch, and the number of policy changes shipped without engineering.

### Known limitations

- Heuristic classifiers (input topics, injection, agent intent) are explainable but miss novel phrasing. Unrecognised agent requests ask for more information rather than guessing.
- Agent executors write to in-process systems of record. Real integrations (Jira, ERP, HRIS) implement the same `ActionExecutor` interface.
- The report scheduler runs in-process; run it on one backend replica (`SCHEDULER_ENABLED=false` on the others).
- Real Slack posting can only be verified with your own workspace credentials. Automated tests use signed requests through Bolt and a captured notifier.
- JWTs live in `localStorage`; production should use httpOnly cookies. No SSO, multi-tenancy, or billing by design.

### Roadmap
pgvector ANN retrieval → in-Slack approvals for agent actions → OIDC SSO and SCIM → shadow-mode policy versions → real system-of-record executors → pluggable ML classifiers → signed evidence packages and SIEM export.

Product docs: [One-pager](docs/PRODUCT_ONE_PAGER.md) · [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Test plan](docs/TEST_PLAN.md) · [Demo script](docs/DEMO_SCRIPT.md)

---

*Developer note: NovaCorp Technologies and every person, record and identifier in the seed data are fictional. Product UI copy never refers to this. Visual direction inspired by editorial SaaS design (cream, ink, forest green, lilac; EB Garamond + Figtree).*
