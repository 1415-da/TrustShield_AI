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

**Permissions** (the required one is listed per endpoint): `assistant:use`, `reviews:read`, `reviews:act`, `policies:read`, `policies:write`, `policies:approve`, `documents:read`, `documents:write`, `analytics:read`, `audit:read`, `users:manage`, `apps:manage`, `tests:run`, `settings:read`, `compliance:read`, `compliance:write`, `integrations:read`, `integrations:manage`, `actions:request`, `actions:approve`, `agents:read`, `agents:manage`. Scopes `data:compensation`, `data:financial`, `actions:finance`, `actions:hr`, `actions:it` don't gate endpoints; they change what guardrails allow a user to see or which agent actions they may initiate.

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

## Policies — versions, approvals, exceptions

A policy is a *family*; its behaviour lives in immutable **versions**. Only the `ACTIVE` version is enforced.
Lifecycle: `DRAFT → IN_REVIEW → APPROVED → ACTIVE → INACTIVE → ARCHIVED`, with `CHANGES_REQUESTED | REJECTED → DRAFT`.

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/admin/policies` | policies:read | Families with status, live version, working version status, owner, next review |
| GET | `/admin/policies/catalogue` | policies:read | Rule types, match fields, actions, severities, topics, entity types, channel profiles |
| POST | `/admin/policies` | policies:write | Create family + **v1 DRAFT** (never live). 201 → detail |
| GET | `/admin/policies/{id}` | policies:read | Detail: `active` version, `working` version, version summaries |
| PATCH | `/admin/policies/{id}` | policies:write | Alias of POST `/versions` (save draft) |
| DELETE | `/admin/policies/{id}` | policies:write | Archive the family (live version deactivated, open review withdrawn). 204 |
| GET | `/admin/policies/{id}/versions` | policies:read | All versions, newest first, with snapshots |
| GET | `/admin/policies/{id}/versions/{vid}?compare_to=active\|previous\|<vid>` | policies:read | Version + structured **diff** + approval record |
| POST | `/admin/policies/{id}/versions` | policies:write | Save the working draft, or start a new draft from the head version. 409 while a version is IN_REVIEW/APPROVED |
| POST | `/admin/policies/{id}/submit-for-review` | policies:write | `{note}` → version IN_REVIEW + pending approval |
| POST | `/admin/policies/{id}/approve` | policies:approve | `{note}`. **403** if you authored or submitted the version (separation of duties) |
| POST | `/admin/policies/{id}/request-changes` | policies:approve | `{note}` required (400 without) |
| POST | `/admin/policies/{id}/reject` | policies:approve | `{note}` required |
| POST | `/admin/policies/{id}/activate` | policies:write | `{version_id?, note}` — approved (or previously approved inactive) version goes live; previous live version → ARCHIVED. 409 if not approved |
| POST | `/admin/policies/{id}/deactivate` | policies:write | `{note}` → INACTIVE |
| POST | `/admin/policies/{id}/rollback` | policies:write | `{version_id, note, activate}` → **new** version copied from a previously approved one. 201 |
| POST | `/admin/policies/{id}/simulate` | policies:read | `{prompt, role, profile?, version_id?, include_output}` — runs with that version (default: working draft) forced in. `{suite: true}` runs the **impact analysis** |
| GET | `/admin/policies/{id}/audit-history` | policies:read | Every lifecycle event (each mirrored in `audit_events`, see `audit_event_id`) |
| GET/POST | `/admin/policies/{id}/comments` | read / write or approve | `{body, version_id?}` |
| GET | `/admin/policy-approvals?status=PENDING\|all` | policies:read | Approval inbox |
| POST | `/admin/simulate` | policies:read | Live policies, optional unsaved `draft_policy`, optional `profile` |
| GET | `/admin/policy-exceptions` | policies:read | Exceptions with `is_expired` |
| POST | `/admin/policy-exceptions` | policies:write | `{policy_id, subject_type: user\|role\|department, subject, justification, starts_at?, expires_at}` (≤ 365 days) |
| POST | `/admin/policy-exceptions/{id}/approve` / `reject` | policies:approve | Requester cannot decide their own |
| POST | `/admin/policy-exceptions/{id}/revoke` | policies:write | |

Version body (all of these are captured in the immutable snapshot):

```json
{
  "name": "Project Unicorn Confidentiality", "description": "…", "risk_category": "legal", "owner": "Legal",
  "review_cadence_days": 90, "effective_from": null, "effective_to": null, "sensitive_data_type": "none",
  "applicable_roles": [], "profiles": [], "action": "BLOCK", "severity": "HIGH", "threshold": 0.5,
  "user_message": "Project Unicorn is confidential.",
  "rules": [{ "key": "kw", "name": "Codename", "rule_type": "keyword", "match_field": "user_input", "keywords": ["unicorn"] }]
}
```

Diff response (`GET …/versions/{vid}`):

```json
{ "diff": { "fields": [{ "field": "threshold", "before": 0.5, "after": 0.8 }],
            "rules_added": [{ "name": "Ticket ids", "rule_type": "regex", "pattern": "\\bUNI-\\d+\\b", "…": "…" }],
            "rules_removed": [],
            "rules_changed": [{ "key": "kw", "name": "Codename", "changes": [{ "field": "action", "before": null, "after": "REVIEW" }] }],
            "has_changes": true } }
```

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

## Compliance Evidence Center

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/compliance/options` | compliance:read | Report types, departments, policies, risk levels, reviewers |
| POST | `/compliance/reports` | compliance:write | Generate (202, `GENERATING` → `READY`/`FAILED` in the background) |
| GET | `/compliance/reports?report_type=&status=&include_withdrawn=` | compliance:read | Library |
| GET | `/compliance/reports/{id}` | compliance:read | Envelope + content |
| GET | `/compliance/reports/{id}/preview` | compliance:read | `{integrity, content}`; 409 unless READY/EXPIRED |
| GET | `/compliance/reports/{id}/verify` | compliance:read | Regenerates from the same records: `{stored_hash, regenerated_hash, reproducible}` |
| GET | `/compliance/reports/{id}/export?format=markdown\|json\|html` | compliance:read | Attachment download; export is audited |
| POST | `/compliance/reports/{id}/schedule` | compliance:write | `{cadence: weekly\|monthly, retention_days?}` |
| DELETE | `/compliance/reports/{id}` | compliance:write | Withdraw from the library (record retained, audited). 204 |
| GET | `/compliance/evidence/{id}/sources?page=&page_size=` | compliance:read | The audit events the report was built from |
| GET | `/compliance/schedules` · DELETE `/compliance/schedules/{id}` | read / write | |
| POST | `/compliance/schedules/run-due` | compliance:write | Run due schedules now (the scheduler does this every minute) |

Generate request:

```json
{ "report_type": "governance_summary", "period_start": "2026-10-01T00:00:00Z", "period_end": "2026-11-01T00:00:00Z",
  "departments": ["Finance"], "policy_ids": [], "risk_levels": ["HIGH", "CRITICAL"], "reviewers": [],
  "include_reviews": true, "include_policy_changes": true, "include_sensitive_events": true, "retention_days": 365 }
```

`report_type` ∈ `governance_summary | sensitive_data | human_oversight | policy_changes | exceptions`. Content shape: `{report_type, title, period, filters, summary[], metrics[{label, value}], sections[{title, columns, rows, description, empty}], evidence{audit_events, source_hash, statement}}`.

## Slack integration and connected workspace

Slack-facing (signed by Slack; no TrustShield auth):

| Method | Path | Notes |
|---|---|---|
| POST | `/integrations/slack/events` | Events API via Slack Bolt (signature + timestamp verified; `url_verification` answered). When Slack is not configured: `200 {"ok": false, "status": "not_configured"}` |
| POST | `/integrations/slack/interactions` | Interactive components (the "View in TrustShield" button) |

Admin:

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/integrations/slack/status` | integrations:read | Mode (`connected \| disabled \| not_configured`), missing env var *names*, required scopes, event counts. Never returns secrets |
| POST | `/integrations/slack/test` | integrations:manage | Calls `auth.test` when configured; otherwise reports the workspace health |
| GET | `/integrations/slack/channels` | integrations:read | Channels + policy profiles |
| PATCH | `/integrations/slack/channels/{id}` | integrations:manage | `{profile_key?, is_enabled?, policy_hint?, description?}` |
| GET | `/integrations/slack/events?status=&source=&limit=` | integrations:read | Delivery log (masked text, decision, deliveries, attempts, errors) |
| POST | `/integrations/slack/retry/{event_id}` | integrations:manage | Reprocess a FAILED event (409 otherwise) |

Employee-facing workspace (`assistant:use`):

| Method | Path | Notes |
|---|---|---|
| GET | `/workspace/channels` | Enabled internal channels with policy hints |
| GET | `/workspace/channels/{id}/messages` | Feed. Others' refused/held messages: `{withheld: true, text: null, reply: {kind: "private"}}` |
| POST | `/workspace/channels/{id}/messages` | `{text, client_msg_id?}` — `client_msg_id` is the idempotency key. 201 → feed item with TrustShield's reply |

## Agent actions

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/agent/actions` | actions:request | `{request}` (natural language) or `{action_type, params}`; optional `idempotency_key` (or `Idempotency-Key` header), `conversation_id`, `record_in_conversation`. Replays return the original with `idempotent_replay: true` |
| GET | `/agent/actions?scope=mine\|approvals` | actions:request (+ actions:approve for approvals) | `approvals` = waiting for one of your roles, excluding your own requests |
| GET | `/agent/actions/{id}` | requester, matching approver, or agents:read | Detail incl. approvals, executions, employee view |
| POST | `/agent/actions/{id}/approve` | actions:approve + required role | Approves **and executes**. 403 for the wrong role or your own request |
| POST | `/agent/actions/{id}/reject` | actions:approve + role | `{note}` required |
| POST | `/agent/actions/{id}/request-info` | actions:approve + role | `{note}` required → `NEEDS_INFO` |
| POST | `/agent/actions/{id}/escalate` | actions:approve + role | → `ESCALATED` for Security Admin |
| POST | `/agent/actions/{id}/execute` | requester or agents:manage | Runs/retries an `APPROVED` or `FAILED` action. 409 if not approved or already executed |
| POST | `/agent/actions/{id}/compensate` | agents:manage | Reverse an executed action via the executor's compensation step |
| GET | `/admin/agent/actions?status=&category=` | agents:read | All actions |
| GET | `/admin/agent/actions/{id}/audit` | agents:read | Every transition (each mirrored in `audit_events`) |
| GET | `/admin/agent/summary` · `/admin/agent/catalog` | agents:read | Counts; agents and action types |
| GET | `/admin/agent/action-policies` | agents:read | Approval rules |
| POST | `/admin/agent/action-policies` | agents:manage | `{name, action_type? \| category?, conditions{amount_gt/gte/lt/lte, requester_roles, external}, decision, approver_role?, priority}` |
| PATCH | `/admin/agent/action-policies/{id}` | agents:manage | Partial update; audited |

Example:

```bash
curl -s localhost:8000/api/agent/actions -H "authorization: Bearer $FINANCE" -H 'content-type: application/json' \
  -H 'Idempotency-Key: refund-inv-2291' -d '{"request":"Issue a refund for vendor invoice INV-2291"}' | jq '{status, decision, required_approver_role, amount, employee_view}'
# → { "status": "PENDING_APPROVAL", "decision": "REQUIRE_APPROVAL", "required_approver_role": "finance_head", "amount": 18000,
#     "employee_view": { "headline": "This action requires approval from Finance Head.", "eta": "Within 1 business day", … } }
```

Error codes added in Release 2: `403 forbidden` for separation-of-duties and wrong-approver-role, `409 conflict` for invalid lifecycle transitions (activating an unapproved version, executing an unapproved or already-executed action, acting on a resolved item).

## Organization workspaces, live demo, Guard API (Release 3)

Every business record belongs to one organization. Requests are scoped to the signed-in user's organization (or, for the Guard API, the app key's). Cross-organization ids return 404.

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/orgs/signup` | none (20/hour per client) | `{organization_name, full_name, email, password (≥10), industry?, size?}` → 201, same shape as login. Creates the workspace, its first TrustShield Admin, baseline policies (active), profiles, channels, web app, agent rules and restrictive test scenarios |
| GET | `/orgs/current` | any user | Organization profile, stats and onboarding checklist |
| PATCH | `/orgs/current` | users:manage | `{name?, industry?, size?}` |
| POST | `/admin/users` | users:manage | `{email, full_name, role_keys[], department?, temporary_password}` → 201. Audited as `user.invited` |
| PATCH | `/admin/roles/{id}` | users:manage | Now 403 outside the platform workspace: roles are shared by all workspaces |
| POST | `/public/playground` | none (30/min per client) | `{prompt, role: employee\|hr_manager\|finance_analyst}` → decision, stages (policy names only), sanitized prompt, answer. Runs against the NovaCorp workspace, nothing stored except a `playground.scan` audit event with a hash |
| GET | `/public/stats` | none | 30-day decision counts for the NovaCorp workspace and the number of workspaces |
| POST | `/v1/guard/input` | `X-TrustShield-App-Key` | `{text, subject{role, email?, department?, profile?}}` → `{request_id, decision, allow_model_call, hold_answer_for_review, sanitized_text, risk_score, redacted_entity_types, matches[], user_message}` |
| POST | `/v1/guard/output` | `X-TrustShield-App-Key` | `{text, prompt?, context[]?, subject}` → `{decision, show_to_user, sanitized_text, confidence, matches[], user_message}`. Grounding rules run only when `context` is supplied |

Guard API calls are audited as `api.guard_input` / `api.guard_output` with a hash of the text, never the text.

## Example: curl session

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"ananya.rao@novacorp.test","password":"TrustShield-demo-2024"}' | jq -r .access_token)

curl -s localhost:8000/api/assistant/chat -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"message":"Show Ravi Sharma'"'"'s salary."}' | jq .decision
# → { "input_action": "BLOCK", "output_action": null, "trust_status": "blocked", "llm_called": false, … }
```
