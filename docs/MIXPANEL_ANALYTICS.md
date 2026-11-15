# Mixpanel analytics

TrustShield uses `mixpanel-browser` for product usage analytics. Set `NEXT_PUBLIC_MIXPANEL_TOKEN` to the Mixpanel **project token** in the frontend build environment. The token is public by design, but keep the local `.env.local` file ignored and configure production/preview variables in the hosting dashboard. Docker builds accept the same variable as a build argument.

## Privacy contract

- The browser uses a random analytics-only subject ID. It never identifies Mixpanel users with TrustShield user IDs, names, or email addresses. Workspace group and role are the only identity context registered.
- Every event passes through the strict allowlist in `frontend/src/lib/analytics/privacy.ts`, both before tracking and in the SDK send hook. Unknown properties are discarded. Backend analytics metadata contains categorical decisions, risk/confidence/latency buckets, citation counts, and static policy categories.
- Prompts, answers, document/policy text, review notes, identifiers, raw amounts, and query strings are excluded. Attribution values are normalized to finite categories.
- Mixpanel respects Do Not Track. Analytics failures do not interrupt product actions.
- The Mixpanel SDK necessarily includes the public project ingest token and an SDK/random analytics `distinct_id` in its transport protocol. The send hook preserves only those required protocol fields; neither value is a TrustShield credential or account identifier.

## Event catalog

The event constants in `frontend/src/lib/analytics/events.ts` cover landing/docs/demo/auth, assistant, connected workspace, policy lifecycle and simulation, reviews, agent actions, evidence reports, audit verification, and document uploads. `pricing_viewed` is reserved until a pricing page exists. Events are sent only after successful product actions where applicable.

## Suggested Mixpanel dashboard

Create a dashboard named **TrustShield Product Analytics** and add these reports. Use unique users for adoption funnels and event totals for operational volume.

1. **Activation funnel:** `landing_page_viewed` → `signup_completed` → `workspace_created` → `assistant_question_submitted`.
2. **Demo engagement:** `demo_playground_run`, broken down by `success` and `decision`.
3. **Assistant usage:** `assistant_question_submitted` and response events, broken down by `decision`, `input_risk_tier`, and `output_risk_tier`.
4. **Workspace usage:** `workspace_message_sent`, split by categorical `channel` and `decision`.
5. **Policy lifecycle:** `policy_created`, submitted, approved, rejected, activated, deactivated, rolled back, simulated.
6. **Human oversight:** `review_case_opened` and `review_case_decided`, broken down by `review_decision` and `priority`.
7. **Agent governance:** `agent_action_requested`, approved, rejected, executed, and blocked by `action_type`, `approval_role`, and `agent_decision`.
8. **Evidence usage:** reports generated/exported by `report_type`, `report_period`, `record_count_bucket`, and `export_format`.
9. **Governance operations:** `audit_chain_verified` and `document_uploaded` by verification result and document type.
10. **Latency and risk:** response event counts by `response_time_bucket` and risk tiers.
11. **Retention:** weekly returning users grouped by `user_role` and (if later collected with a consented onboarding flow) coarse industry/company-size buckets.
12. **Acquisition:** landing page views by normalized `utm_source`, `utm_medium`, and `utm_campaign`.

Do not add event properties outside the allowlist or enable autocapture/session replay without a separate privacy review. Verify ingestion in Mixpanel Live View with a synthetic prompt and confirm no prompt, answer, email, or raw URL appears. Keep screenshots or a dashboard export in `docs/` when the Mixpanel project is connected.

## Local verification

Set the token in `frontend/.env.local`, restart the dev server, open the app, and inspect browser network requests for Mixpanel's `/track` endpoint. The payload should contain only the named events and allowlisted properties. With no token configured, the app makes no analytics calls.
