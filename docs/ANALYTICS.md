# Product analytics specification

## Goals

Measure public acquisition, workspace activation, feature adoption by role, assistant/workspace governance outcomes, policy and review workflows, agent approvals, evidence usage, and returning use. Events support the product questions in the project analytics brief without recording user content.

## Identity and privacy

Mixpanel uses a random browser-local analytics subject. TrustShield account IDs, names, emails, prompts, answers, document/policy text, review notes, raw audit content, raw monetary amounts, credentials, and arbitrary URLs are never sent. The SDK transport necessarily includes the public Mixpanel project token and random analytics `distinct_id`; the send hook only retains those required protocol fields and does not use TrustShield account identity. `workspace_id` is a workspace grouping identifier and `user_role` is an approved role enum. Backend metadata is derived in `backend/app/services/analytics_events.py`; frontend event properties pass through the strict allowlist in `frontend/src/lib/analytics/privacy.ts` before the SDK send hook applies it again. DNT is respected. Analytics failure is isolated from product actions.

## Event taxonomy

| Area | Events |
|---|---|
| Acquisition and auth | `landing_page_viewed`, `pricing_viewed` (reserved), `docs_viewed`, `demo_playground_run`, `signup_started`, `signup_completed`, `workspace_created`, `login_started`, `login_completed`, `login_failed`, `logout_completed` |
| Assistant | `assistant_opened`, `assistant_question_submitted`, `assistant_response_shown`, `assistant_response_warned`, `assistant_response_redacted`, `assistant_response_blocked`, `assistant_response_reviewed`, `source_citation_opened` |
| Workspace | `workspace_opened`, `workspace_message_sent`, `workspace_message_blocked`, `workspace_message_reviewed` |
| Policy | `policy_studio_opened`, `policy_created`, `policy_submitted_for_approval`, `policy_approved`, `policy_rejected`, `policy_activated`, `policy_deactivated`, `policy_rolled_back`, `policy_simulated` |
| Reviews | `review_queue_opened`, `review_case_opened`, `review_case_decided` |
| Agents | `agent_control_center_opened`, `agent_action_requested`, `agent_action_approved`, `agent_action_rejected`, `agent_action_executed`, `agent_action_blocked` |
| Governance | `evidence_center_opened`, `evidence_report_generated`, `evidence_report_exported`, `audit_log_opened`, `audit_chain_verified`, `document_uploaded` |

Successful route visits emit the relevant `*_opened` / public page event. Mutating events emit after the API action succeeds. `assistant_question_submitted` is emitted with safe backend outcome metadata once the response arrives, so decision and policy category breakdowns are meaningful.

## Property dictionary

Common properties: `workspace_id`, `user_role`, `surface`, and `feature_area`. Outcome properties: `decision`, `policy_categories`, `input_risk_tier`, `output_risk_tier`, `confidence_bucket`, `citation_count`, `response_time_bucket`, `model_called`, and `trust_status`. Workflow properties: `channel`, `policy_profile`, `action_type`, `amount_bucket`, `approval_role`, `agent_decision`, `report_type`, `report_period`, `record_count_bucket`, `export_format`, `document_type`, `priority`, `origin`, `review_decision`, `simulation_role`, `verification_result`, `success`, `error_code`, and normalized attribution (`source`, `referrer`, `utm_source`, `utm_medium`, `utm_campaign`). All fields are validated against finite enums/buckets; arbitrary strings and arrays are dropped.

## Funnel and retention definitions

- Workspace activation: landing → signup started → signup completed → workspace created → first assistant question, within 7 days. Break down by normalized UTM source/referrer.
- Policy governance: login → policy created → submitted → approved → activated, within 7 days. Break down by role.
- Human review: assistant response reviewed → case opened → case decided, within 7 days. Break down by priority.
- New workspace retention: workspace created → assistant question within 7 days; workspace identity is available as a group. Industry/company size are not currently collected by onboarding, so omit those breakdowns until a consented categorical source exists.
- Reviewer engagement: login → review case decided within 7 days, by role.

## Dashboard definitions

Create **TrustShield Product Analytics** with these reports: weekly active users by role; workspace activation funnel; assistant usage by role; guardrail decision mix; policy trigger frequency; feature adoption by role; policy governance funnel; human review workflow; agent action adoption; compliance evidence usage; new workspace retention; and compliance reviewer engagement retention. Suggested event names, report setup, and privacy operating instructions are in [MIXPANEL_ANALYTICS.md](MIXPANEL_ANALYTICS.md). Reports require events to arrive in a connected Mixpanel project.

## Setup and debugging

Set `NEXT_PUBLIC_MIXPANEL_TOKEN` in `frontend/.env.local` for local builds, or in the deployment provider's frontend build environment. Docker passes it as a build argument. Restart/rebuild after changing it. Check the browser network tab for Mixpanel `/track` requests; with no token there should be none. For Live View checks, use synthetic data only and inspect payloads for unexpected properties. See [MIXPANEL_VERIFICATION.md](MIXPANEL_VERIFICATION.md).
