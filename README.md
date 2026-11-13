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

| Service | Default URL | Override in `.env` |
|---|---|---|
| Web app (landing, assistant, console) | http://localhost:3000 | `FRONTEND_PORT` |
| API + Swagger docs | http://localhost:8000/api/docs | `BACKEND_PORT` |
| PostgreSQL 15 (localhost only) | `postgresql://trustshield:trustshield@localhost:55432/trustshield` | `DB_PORT` |

On first start the backend runs Alembic migrations and seeds the demo tenant. Seeding replays about 14 days of traffic through the real gateway and runs the evaluation suite once.

**Port already in use?** If another project or a local Postgres holds 3000, 8000 or 55432, TrustShield's containers start but you reach *the other service* on that port. For example, `localhost:8000` returns `{"detail":"Not Found"}` from someone else's API. Run `scripts/check_ports.sh` to see who owns each port, then set free ports in `.env`:

```env
FRONTEND_PORT=3200
BACKEND_PORT=8200
DB_PORT=55433
PUBLIC_APP_URL=http://localhost:3200
```

`docker compose up -d` picks these up every time. The browser only needs the frontend port; it reaches the API through the frontend's `/api` proxy.

### Website, live demo, workspaces and docs

| Page | What it is |
|---|---|
| `/` | Product site with live decision counts and a Guard API snippet |
| `/demo` | Public guardrail playground against the NovaCorp workspace, plus NovaCorp accounts that open the sign-in form pre-filled (you still sign in) |
| `/signup` | An organization creates its own isolated workspace and becomes its first admin |
| `/console/setup` | Onboarding checklist, workspace settings and a ready-to-run Guard API call |
| `/docs` | 14-page documentation: quickstart, decisions, policies, review, agent actions, evidence, Guard API, Assistant API, Slack, self-hosting, roles, security |

Tenant isolation is enforced in the ORM (`app/core/tenancy.py`): every business table has `organization_id`; reads are filtered and inserts stamped automatically from the signed-in user or app key. Existing data becomes workspace 1 (NovaCorp) via migration `0006`.

### Authentication, roles and sign-in flow

TrustShield behaves like a standard SaaS sign-in. Nobody is ever signed in automatically.

1. Open http://localhost:3200 and click **Sign in** (or open a protected page — you're sent to `/login?next=<that page>`).
2. Enter email and password. The API sets three cookies:
   - `trustshield_access_token`: HTTP-only, 30 minutes.
   - `trustshield_refresh_token`: HTTP-only, 7 days.
   - `trustshield_csrf`: readable by the page, echoed as `X-CSRF-Token` on every write.
   No token is ever stored in `localStorage`.
3. You land on the page you asked for (if your role may open it) or on your role's home:

| Role | Lands on |
|---|---|
| Employee, HR Manager, Finance Analyst | `/assistant` |
| People Manager, Finance Head, Security Admin | `/console/agents` (approvals tab) |
| Compliance Reviewer | `/console/reviews` |
| Security Auditor | `/console/audit` |
| TrustShield Admin | `/console` |

4. **Refresh / come back later:** the middleware renews an expired access token from the refresh cookie before the page renders, so you stay signed in.
5. **Sign out:**
   - It revokes the server-side session, so every token from it stops working immediately, and clears the cookies.
   - Other open tabs sign out too, and the Back button can't show a protected page.
6. **Opening `/login` while signed in** shows *"Already signed in as …"* with **Continue** or **Sign out and use another account**. It never silently continues as whoever used the browser last.

**Route protection has three layers:**
- `middleware.ts` gives a fast redirect to sign-in;
- the server layouts (`ProtectedArea`) check the session with the API and the route's permission before rendering, and render "No access" for pages your role lacks;
- every API endpoint enforces permissions independently: 401 for no session, 403 `AUTHORIZATION_DENIED` for missing permissions. Denials are audited (`auth.access_denied`).

**Workspaces:**
- Every account belongs to exactly one workspace, and an email address can only exist once.
- The workspace is resolved on the server from the signed-in account on every request; it's never taken from the browser and never defaulted.
- So there is no workspace picker: a person never has more than one workspace to choose from (see `docs/BUG_AUDIT.md`, WS-2).

**The "Live demo" accounts** on `/demo` and `/login` only *fill in* the sign-in form. You still press **Sign in**.

**Environment variables (auth):**

| Variable | Default | Purpose |
|---|---|---|
| `JWT_SECRET` | `change-me` | Token signing key. **Change it in any shared environment.** |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS so session cookies are marked `Secure`. |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | `30` / `7` | Token lifetimes. |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `trustshield` / `trustshield-app` | Validated on every token. |

**Troubleshooting sign-in:**
- **Sent back to sign-in on every page:** you're probably serving over plain HTTP with `COOKIE_SECURE=true`. Set it to `false`, or use HTTPS.
- **"Your session could not be verified" (403 `CSRF_FAILED`):** the CSRF cookie is missing. Refresh the page, or sign out and in again.
- **"Too many sign-in attempts" (429):** 10 failed attempts for one email in 5 minutes, or 20 from one network in a minute. Wait for the window to pass.
- **Server-to-server clients:** call `POST /api/auth/login` and send `Authorization: Bearer <access_token>`. Bearer requests aren't subject to CSRF.

### Demo accounts

Password for all accounts: `TrustShield-demo-2024` (set via `DEMO_USER_PASSWORD`). On the login page, choosing an account fills in the form; you still press **Sign in**.

Everyone holds **Employee** plus one job role. Each kind of approval belongs to exactly one role, and nobody approves their own request.

| Person | Job role | Approves | Lands on | What to try |
|---|---|---|---|---|
| ananya.rao@novacorp.test | Employee | — | Assistant | Ask policy questions; ask for a colleague's salary (blocked); ask a legal question (held for review) |
| neha.kapoor@novacorp.test | HR Manager | Salary changes | Assistant | Same salary question, different outcome (has `data:compensation`) |
| rahul.verma@novacorp.test | Finance Analyst | — | Assistant | Ask in `#finance-help`; request refunds and reimbursements |
| aditya.kulkarni@novacorp.test | People Manager | Reimbursements INR 5,000–50,000, leave and record updates | Agent approvals | Approve "Arjun Mehta's expense reimbursement" (INR 18,500) |
| vivek.raman@novacorp.test | Finance Head | Reimbursements > INR 50,000, vendor refunds > INR 10,000 | Agent approvals | Approve "Refund INV-2291" (INR 18,000) |
| tara.bose@novacorp.test | Security Admin | Access revocations, deletions, permission changes | Agent approvals | Approve "Revoke access for Vikram Singh" |
| kavya.menon@novacorp.test | Compliance Reviewer | Held answers, policy versions, exceptions, external messages | Review queue | Approve, edit or reject held answers; approve policy changes |
| sanjay.gupta@novacorp.test | Security Auditor | — (read-only) | Audit log | Verify the audit chain; read dashboards and evidence |
| rohan.das@novacorp.test | TrustShield Admin | — (runs the workspace, approves nothing) | Console | Draft policies, manage users, apps, Slack and agent approval rules |

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
- Sessions use HTTP-only, SameSite=Lax cookies with server-side revocation, CSRF double-submit tokens, `iss`/`aud`-validated JWTs, and rate-limited sign-in.

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
- No SSO or billing. One workspace per account (no cross-workspace membership).

### Roadmap
pgvector ANN retrieval → in-Slack approvals for agent actions → OIDC SSO and SCIM → shadow-mode policy versions → real system-of-record executors → pluggable ML classifiers → signed evidence packages and SIEM export.

Product docs: [One-pager](docs/PRODUCT_ONE_PAGER.md) · [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Test plan](docs/TEST_PLAN.md) · [Demo script](docs/DEMO_SCRIPT.md)

---

*Developer note: NovaCorp Technologies and every person, record and identifier in the seed data are fictional. Product UI copy never refers to this. Visual direction inspired by editorial SaaS design (cream, ink, forest green, lilac; EB Garamond + Figtree).*
