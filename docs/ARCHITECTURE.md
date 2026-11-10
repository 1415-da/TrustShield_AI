# TrustShield AI — Architecture

## 1. System overview

```
 ┌──────────────────────────┐      same-origin /api/*      ┌──────────────────────────────────────────────┐
 │  Next.js 14 (frontend)   │ ───────────────────────────► │  FastAPI (backend) — TrustShield gateway      │
 │  • Landing               │   (Next rewrite → backend)   │                                              │
 │  • Employee assistant    │                              │  api/  ── thin routers, RBAC dependencies     │
 │  • Console (admin,       │  ◄── JSON, never raw PII ─── │  services/ ── gateway orchestration, reviews, │
 │    reviewer, auditor)    │                              │              policies, docs, audit, tests     │
 └──────────────────────────┘                              │  guardrails/ ── PII, injection, topics,       │
            ▲                                              │              rules, grounding, decision       │
            │ never calls an LLM                           │  services/llm ── provider abstraction ──────────┼──► OpenAI-compatible /
            │                                              └──────────────────────┬───────────────────────┘    Azure OpenAI / Mock
                                                                                  │ SQLAlchemy 2.0
                                                                                  ▼
                                                                       PostgreSQL 15 (Alembic)
```

The browser only ever calls `/api/*` on its own origin. `next.config.js` rewrites those calls to the backend. The model provider's credentials exist only in the backend container.

## 2. Request lifecycle (`POST /api/assistant/chat`)

```
1. Auth          JWT → user → roles → permission scopes
2. Input stage   ┌ PII detection (Presidio + custom recognizers)
                 ├ prompt-injection score (weighted signals)
                 ├ topic classification (salary, credit card, bank, PII, legal, credentials, …)
                 ├ directory lookup (does the prompt target a named employee?)
                 └ policy evaluation over active rules (match_field = user_input)
                 → input action: ALLOW | REDACT | BLOCK | REVIEW | ESCALATE
3. Short-circuit BLOCK / ESCALATE → no retrieval, no LLM call. Explanation returned.
4. Retrieval     sanitized prompt → hybrid search (embedding cosine + BM25) → top-5 chunks
                 each chunk scanned (match_field = retrieved_context):
                   REDACT rules mask values in the chunk (e.g. a card number in a wiki page)
                   any other hit quarantines the chunk (e.g. injected instructions)
5. Generation    LLMProvider.generate(prompt, context) — mock | openai | azure
6. Output stage  ┌ PII / sensitive-number leak detection on the draft
                 ├ grounding signals (semantic, lexical, citations, evidence coverage, contradictions)
                 ├ confidence risk signal
                 └ policy evaluation over active rules (match_field = llm_output)
                 → output action: SHOW | SHOW_WITH_WARNING | REDACT | SEND_TO_REVIEW | BLOCK
7. Persistence   messages (masked), guardrail_decisions (per stage), review_case (if needed),
                 audit_event (hash-chained)
8. Response      final text, trust status, citations, explanation
```

Invariant: step 5 is unreachable when step 3 short-circuits. This is asserted in `tests/test_gateway.py` with a spy provider.

## 3. Backend modules

| Path | Responsibility |
|---|---|
| `app/core/` | Settings (pydantic-settings), DB engine/session, JWT + bcrypt, RBAC dependencies, error handlers, request-ID logging middleware |
| `app/models/` | SQLAlchemy 2.0 typed models (all 19 required tables + `employee_records`) |
| `app/schemas/` | Pydantic v2 request/response models |
| `app/guardrails/pii.py` | Presidio analyzer + anonymizer with custom recognizers (salary, card, bank account, employee ID, test national ID). Regex-only fallback if Presidio/spaCy is unavailable |
| `app/guardrails/injection.py` | Weighted prompt-injection scorer (instruction override, system-prompt extraction, safety disable, role-play jailbreak, obfuscation) |
| `app/guardrails/topics.py` | Lexicon-based topic classifier with target/request/policy-meta modifiers |
| `app/guardrails/rules.py` | Generic evaluator for the six rule types against a `GuardrailContext` |
| `app/guardrails/grounding.py` | Groundedness + confidence risk signals |
| `app/guardrails/decision.py` | Action precedence and input→output mapping |
| `app/guardrails/pipeline.py` | `InputGuardrails`, `ContextGuardrails`, `OutputGuardrails` stages |
| `app/services/gateway.py` | Orchestrates one request end-to-end; used by chat, simulator, test harness and seed |
| `app/services/llm/` | `LLMProvider` protocol; `MockProvider`, `OpenAICompatibleProvider`, `AzureOpenAIProvider` |
| `app/services/retrieval.py`, `embeddings.py`, `documents.py` | Chunking, embeddings, hybrid retrieval |
| `app/services/reviews.py` | Approve / edit / reject / escalate with re-scan and delivery |
| `app/services/audit.py` | Append-only, hash-chained audit writer and verifier |
| `app/services/policies.py` | CRUD with automatic version snapshots |
| `app/services/evaluation.py` | Test harness runner and FP/FN scoring |
| `app/services/simulation.py` | Dry-run simulator, including inactive or unsaved draft policies |
| `app/seed/` | Synthetic NovaCorp data (users, directory, policies, documents, 49 test cases) |
| `app/workers/tasks.py` | FastAPI background tasks (reindex, test runs) |

## 4. Data model

```
users ─< user_roles >─ roles (permissions: JSON scopes)
policies ─< policy_rules          policies ─< policy_versions (JSON snapshot per change)
documents ─< document_chunks (embedding JSON, token counts)
conversations ─< messages ─< guardrail_decisions (stage: input | context | output)
messages ── review_cases ─< review_actions
audit_events (append-only, prev_hash → event_hash)
connected_apps ─< api_keys (sha256 hash + prefix only)
test_cases, test_runs ─< test_results
employee_records (synthetic directory: names, titles, salary bands, test IDs)
```

### Policy rule types

| `rule_type` | Config fields | Triggers when |
|---|---|---|
| `regex` | `pattern` | pattern matches the field |
| `keyword` | `keywords[]` | any keyword appears (word-boundary, case-insensitive) |
| `pii_entity` | `entity_types[]`, `threshold` | an entity of those types is detected at ≥ threshold |
| `topic` | `topic`, `threshold` | topic score ≥ threshold (`prompt_injection` is a topic scored by the injection detector) |
| `role_permission` | `required_permission`, plus `topic` or `entity_types` | the condition holds **and** the user lacks the permission scope |
| `confidence_threshold` | `threshold` | grounding confidence < threshold (output only) |

A baseline also applies regardless of policy: card numbers, bank numbers, government-style IDs, emails, phone numbers and inline credentials are always masked before a prompt leaves the gateway or a message is stored.

Each rule has `match_field` (`user_input` / `llm_output` / `retrieved_context`), `action`, `severity`, `applies_to_roles` (empty = all), and `is_active`. On the output side, a triggered `ALLOW` rule means "allowed, but flag it" → `SHOW_WITH_WARNING`.

## 5. Retrieval and grounding

- **Chunking:** paragraph-aware, ~700 characters with one-paragraph overlap; headings kept with their body.
- **Embeddings:** `EMBEDDING_PROVIDER=local` uses a deterministic hashed unigram+bigram vector (768-d, L2-normalised) — zero downloads, works offline. `sentence-transformers` and `openai` are optional providers behind the same interface.
- **Vector storage:** embeddings are stored as JSON on `document_chunks` and scored in-process. At MVP corpus sizes (hundreds of chunks) this is faster than a network round-trip. pgvector is on the roadmap; the interface is ready for it.
- **Ranking:** `0.55 × cosine + 0.45 × saturated BM25`; chunks below half the best score are dropped; top-5.
- **Groundedness (risk signal):** `0.30 semantic + 0.20 lexical support + 0.15 citation presence + 0.15 evidence coverage + 0.20 query-term support − contradiction penalty`. Contradiction signals: numbers in the answer absent from evidence, hedging language, explicit "no policy found" statements. Masked placeholders and generic question modifiers ("minimum", "how long") are ignored.
- **Confidence (risk signal):** `0.6 groundedness + 0.2 retrieval similarity + 0.1 length sanity + 0.1 (1 − input risk)`.

These are heuristics. The product labels them as risk signals and routes low scores to humans rather than claiming to detect hallucinations.

## 6. Security and privacy

- **AuthN:** short-lived JWT access tokens (30 min) + refresh tokens (7 days), HS256, secret from `JWT_SECRET`.
- **AuthZ:** permission scopes per role (`assistant:use`, `reviews:act`, `policies:write`, `audit:read`, `data:compensation`, …). Routers declare `require_permission(...)`.
- **Masking before persistence:** user messages, review cases, and audit details store masked text (`<CREDIT_CARD>`, `<EMAIL_ADDRESS>`). Raw content is represented only by a SHA-256 hash.
- **API keys:** shown once, stored as SHA-256 with an 8-char prefix.
- **Audit immutability:** ORM `before_update`/`before_delete` guards and a PostgreSQL trigger reject modification; `prev_hash`/`event_hash` chain allows verification (`GET /api/admin/audit-events/verify`).
- **Token storage trade-off:** the MVP stores JWTs in `localStorage` for simplicity. Production should use httpOnly, SameSite cookies.

## 7. Deployment

`docker compose up --build` starts `db` (postgres:15-alpine), `backend` (runs `alembic upgrade head`, seeds if empty, starts uvicorn), and `frontend` (Next.js standalone). No Redis/Celery: background work uses FastAPI `BackgroundTasks`.

## 8. Key trade-offs

| Decision | Why | Cost |
|---|---|---|
| Heuristic classifiers | Explainable, deterministic, testable offline | Lower recall on novel phrasing than an ML model |
| In-process vector scoring | No extra infra, fast at small scale | Won't scale past ~100k chunks without pgvector |
| Mask user messages at rest | Strong privacy default | Employees see masked versions of their own past messages |
| Single gateway service | Simple to deploy and reason about | Guardrail and admin APIs scale together |
| SQLite in unit tests | Fast, hermetic CI | Postgres-only features (trigger) tested via ORM guard instead |
