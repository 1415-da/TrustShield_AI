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

---

## Quick start (Docker)

```bash
cp .env.example .env          # optional; defaults run fully offline with the mock model
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
| rahul.verma@novacorp.test | Finance Analyst | Procurement questions; still blocked from card data |
| kavya.menon@novacorp.test | Compliance Reviewer | Work the review queue |
| sanjay.gupta@novacorp.test | Security / Audit Viewer | Audit log, analytics, chain verification (read-only) |
| rohan.das@novacorp.test | TrustShield Admin | Policy Studio, simulator, documents, users, apps, test center |

The full guided walkthrough is in **[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)**.

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
cd backend && .venv/bin/python -m pytest                 # 120 tests, ~7s, SQLite in-memory + mock model
scripts/run_tests.sh                                     # backend + guardrail evaluation → reports/TEST_REPORT.md
E2E_BASE_URL=http://localhost:3000 scripts/run_tests.sh --e2e   # + 8 Playwright tests (stack must be running)
```

| Suite | Count | Result |
|---|---|---|
| Backend pytest (unit, integration, API, evaluation) | 120 | all passing |
| Seeded guardrail scenarios | 49 | 49/49 · 0 false positives (12 safe) · 0 false negatives (31 restrictive) |
| Playwright end-to-end | 8 | all passing |

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
| **Console** | Overview analytics, Policy Studio, Simulator, Knowledge sources, Review queue, Audit log, Test center, Users & roles, Connected apps (hashed API keys), Settings |

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

### Roadmap
pgvector ANN retrieval → streaming with incremental output scanning → OIDC SSO and SCIM → shadow-mode policies (log without enforcing) → pluggable ML classifiers behind the same rule interface → SIEM export.

Product docs: [One-pager](docs/PRODUCT_ONE_PAGER.md) · [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Test plan](docs/TEST_PLAN.md) · [Demo script](docs/DEMO_SCRIPT.md)

---

*All demo data is synthetic. NovaCorp Technologies is fictional. Visual direction inspired by editorial SaaS design (cream, ink, forest green, lilac; EB Garamond + Figtree).*
