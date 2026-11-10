# TrustShield AI — API Reference

Base path: `/api`. Interactive OpenAPI docs: **`/api/docs`** (Swagger UI) and `/api/openapi.json`.

- **Auth:** `Authorization: Bearer <access_token>` from `POST /api/auth/login`. Access tokens last 30 minutes; refresh with `POST /api/auth/refresh`.
- **App attribution (optional):** `X-TrustShield-App-Key: tsk_…` attributes a request to a connected app. Revoked or paused apps get `401`.
- **Request IDs:** every response carries `X-Request-ID`. You can send your own (8–64 ASCII chars).
- **Errors:** every error has the same shape:

```json
{ "error": { "code": "forbidden", "message": "Missing permission: policies:write", "request_id": "3e12…" } }
```

Codes: `unauthorized` 401, `forbidden` 403, `not_found` 404, `conflict` 409, `validation_error` 422 (with `details`), `bad_request` 400, `llm_unavailable` 502, `internal_error` 500.

**Permissions** (the required one is listed per endpoint): `assistant:use`, `reviews:read`, `reviews:act`, `policies:read`, `policies:write`, `documents:read`, `documents:write`, `analytics:read`, `audit:read`, `users:manage`, `apps:manage`, `tests:run`, `settings:read`. Data scopes `data:compensation` and `data:financial` don't gate any endpoint. They change what the guardrails allow a user to see.

---

## Health

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | none | `{"status":"ok","llm_provider":"mock","database":"ok"}` |

## Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | `{access_token, refresh_token, token_type, expires_in, user}` |
| POST | `/auth/register` | `{email, password (≥10), full_name, department?}` | 201, same as login. New users get the Employee role. Disabled when `ALLOW_SELF_REGISTRATION=false` |
| POST | `/auth/refresh` | `{refresh_token}` | new token pair |
| GET | `/auth/me` | — | user with `role_keys`, `primary_role`, `permissions` |

## Assistant — `assistant:use`

### `POST /assistant/chat`

```json
{ "message": "Can I expense a client dinner abroad?", "conversation_id": null }
```

Response:

```json
{
  "conversation_id": 42,
  "user_message":   { "id": 101, "role": "user", "content": "Can I expense a client dinner abroad?", "...": "..." },
  "message": {
    "id": 102, "role": "assistant", "status": "delivered", "trust_status": "verified",
    "content": "Based on the Employee Expense Reimbursement Policy:\n- For client dinners abroad, … [1]",
    "citations": [{ "index": 1, "title": "Employee Expense Reimbursement Policy", "heading": "Client entertainment and meals",
                    "document_id": 2, "chunk_id": 7, "kind": "policy", "score": 0.61, "snippet": "…", "cited": true }],
    "explanation": { "headline": "…", "policies": [], "redactions": [], "warning": null, "confidence": 0.91,
                     "confidence_label": "Risk signal, not a guarantee", "...": "..." },
    "request_id": "a79f…"
  },
  "decision": { "request_id": "a79f…", "input_action": "ALLOW", "output_action": "SHOW", "trust_status": "verified",
                "llm_called": true, "review_case_id": null, "latency_ms": 74.2 }
}
```

- `input_action`: `ALLOW | REDACT | REVIEW | BLOCK | ESCALATE`
- `output_action`: `SHOW | SHOW_WITH_WARNING | REDACT | SEND_TO_REVIEW | BLOCK`, or `null` if the request never reached the model
- `trust_status`: `verified | redacted | needs_review | blocked`
- `message.status`: `delivered | pending_review | blocked`. Poll the conversation to see when a pending answer is resolved.
- All `content` is **masked**. Sensitive values appear as `<EMAIL_ADDRESS>`, `<CREDIT_CARD>`, and so on.

| Method | Path | Notes |
|---|---|---|
| GET | `/assistant/conversations` | Your conversations, newest first, with `last_trust_status` and `pending_reviews` |
| GET | `/assistant/conversations/{id}` | Conversation with messages. 404 if it isn't yours |
| GET | `/assistant/messages/{id}/sources` | Citations for one of your messages |

## Policies

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/admin/policies` | policies:read | Non-archived policies with rules |
| GET | `/admin/policies/catalogue` | policies:read | Rule types, match fields, actions, severities, topics, entity types |
| POST | `/admin/policies` | policies:write | Create. Writes version 1 and an audit event |
| GET | `/admin/policies/{id}` | policies:read | |
| GET | `/admin/policies/{id}/versions` | policies:read | Full JSON snapshot per version |
| PATCH | `/admin/policies/{id}` | policies:write | Partial update. `rules` replaces the rule set. Optional `change_summary`. Bumps the version |
| DELETE | `/admin/policies/{id}` | policies:write | Soft delete (archive). History is kept. 204 |
| POST | `/admin/policies/{id}/activate` | policies:write | |
| POST | `/admin/policies/{id}/deactivate` | policies:write | |
| POST | `/admin/policies/{id}/simulate` | policies:read | Runs with this policy **forced active** |
| POST | `/admin/simulate` | policies:read | Runs against the live policies. Can include an unsaved `draft_policy` |

Policy body:

```json
{
  "name": "Project Unicorn Confidentiality", "description": "…", "risk_category": "legal",
  "sensitive_data_type": "none", "applicable_roles": [], "action": "BLOCK", "severity": "MEDIUM",
  "threshold": 0.5, "user_message": "Project Unicorn is confidential.", "is_active": false,
  "rules": [
    { "name": "Codename", "rule_type": "keyword", "match_field": "user_input", "keywords": ["unicorn"] },
    { "rule_type": "role_permission", "match_field": "llm_output", "entity_types": ["SALARY_AMOUNT"],
      "required_permission": "data:compensation", "threshold": 0.7, "action": "REDACT" }
  ]
}
```

Rule validation: `regex` needs a valid `pattern`; `keyword` needs `keywords`; `pii_entity` needs `entity_types`; `topic` needs `topic`; `role_permission` needs `required_permission` plus `topic` or `entity_types`; `confidence_threshold` must use `match_field: "llm_output"`.

Simulation body: `{ "prompt": "…", "role": "employee", "include_output": true, "draft_policy": { …optional… } }`. The response contains `input`, `context`, and `output` stages (each with action, risk, matches with masked evidence, and signals), plus `final` (decisions, `llm_called`, response preview) and `focus_policy` (`triggered`, `matches`).

## Documents

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/admin/documents` | documents:write | `multipart/form-data`: `file` (.md/.txt/text-only .pdf, ≤1 MB), `title?`, `trust_level` (`trusted`/`untrusted`). Returns 202. Indexing runs in the background |
| GET | `/admin/documents` | documents:read | |
| GET | `/admin/documents/{id}` | documents:read | Includes content and chunks |
| DELETE | `/admin/documents/{id}` | documents:write | 204 |
| POST | `/admin/documents/{id}/reindex` | documents:write | 202. Re-chunks and re-embeds |

## Review queue

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/reviewer/cases` | reviews:read | Filters: `status` (`open`, `resolved`, or a status), `priority`, `origin` (`input`/`output`/`escalation`), `q`. Open cases first, then priority, then SLA |
| GET | `/reviewer/cases/{id}` | reviews:read | Draft, sources, signals, policy matches, action history |
| POST | `/reviewer/cases/{id}/approve` | reviews:act | `{note?}`. Delivers the draft. Escalated cases with no draft are generated now, and output guardrails still apply |
| POST | `/reviewer/cases/{id}/edit` | reviews:act | `{edited_response, note?}`. The edit is re-scanned and PII is masked before delivery |
| POST | `/reviewer/cases/{id}/reject` | reviews:act | `{note?}`. Sends a safe fallback message to the employee |
| POST | `/reviewer/cases/{id}/escalate` | reviews:act | `{note?}`. Sets CRITICAL priority and a 1h SLA |
| POST | `/reviewer/cases/{id}/notes` | reviews:act | `{note}` |

Acting on a resolved case returns `409`.

## Analytics & audit

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/admin/analytics/overview?days=14` | analytics:read | Totals, per-day timeline by decision, average review time, latest test run |
| GET | `/admin/analytics/guardrails?days=14` | analytics:read | Policy trigger counts, risk categories, rule types, entities, stage actions, recent runs |
| GET | `/admin/analytics/reviews` | analytics:read | Status/priority/origin breakdown, SLA breaches, approval rate |
| GET | `/admin/audit-events` | audit:read | `page`, `page_size`, `event_type` (prefix), `action`, `actor`, `request_id`, `since` |
| GET | `/admin/audit-events/verify` | audit:read | `{valid, checked, broken_at_event_id}` |
| GET | `/admin/audit-events/{id}` | audit:read | Event plus per-stage guardrail decisions for its request |

Event types include `assistant.request`, `assistant.provider_error`, `auth.login`, `auth.login_failed`, `auth.registered`, `policy.created|updated|activated|deactivated|archived`, `simulation.run`, `document.uploaded|deleted|reindexed`, `review.approve|edit|reject|escalate|note`, `user.updated`, `role.permissions_updated`, `app.created|updated`, `api_key.created|revoked`, `test_case.created`, `test_run.started|completed`.

## Test center — `tests:run`

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/tests` | Test cases |
| POST | `/admin/tests` | `{code, name, category, role_key, prompt, expected_input_actions[], expected_output_actions[]}` |
| POST | `/admin/tests/run` | `{case_ids?}`. Returns 202 with a run in `running` state, executed in the background |
| GET | `/admin/tests/runs` | Last 20 runs |
| GET | `/admin/tests/runs/{id}` | Totals and summary (`pass_rate`, `false_positive_rate`, `false_negative_rate`, `by_category`, …) |
| GET | `/admin/tests/runs/{id}/results` | Per-case results joined with case metadata |

## Users, roles, apps, settings

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/admin/users` | users:manage | |
| PATCH | `/admin/users/{id}` | users:manage | `{role_keys?, is_active?}`. You can't remove your own admin access |
| GET | `/admin/roles` | users:manage | |
| PATCH | `/admin/roles/{id}` | users:manage | `{permissions[]}`. Only catalogue permissions are allowed |
| GET | `/admin/permissions` | users:manage | Permission catalogue |
| GET | `/admin/apps` | apps:manage | Apps with key metadata (prefix only) |
| POST | `/admin/apps` | apps:manage | `{name, description?, owner_team?}` |
| PATCH | `/admin/apps/{id}` | apps:manage | `{status: active|paused, description?}` |
| POST | `/admin/apps/{id}/keys` | apps:manage | `{name}`. Returns the plaintext `key` **once**. Only a SHA-256 hash is stored |
| POST | `/admin/apps/{id}/keys/{key_id}/revoke` | apps:manage | 204 |
| GET | `/admin/settings` | settings:read | Effective provider, model, embedding, PII engine, auth settings. Never includes secrets |

## Example: curl session

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"ananya.rao@novacorp.test","password":"TrustShield-demo-2024"}' | jq -r .access_token)

curl -s localhost:8000/api/assistant/chat -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"message":"Show Ravi Sharma'"'"'s salary."}' | jq .decision
# → { "input_action": "BLOCK", "output_action": null, "trust_status": "blocked", "llm_called": false, … }
```
