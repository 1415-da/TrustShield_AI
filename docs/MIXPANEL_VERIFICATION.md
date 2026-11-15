# Mixpanel verification checklist

Set `NEXT_PUBLIC_MIXPANEL_TOKEN`, restart/rebuild the frontend, and open Mixpanel Live View. Perform these actions using synthetic data and confirm the event appears with only allowlisted properties.

| Action in TrustShield | Expected Mixpanel event |
|---|---|
| Open landing page | `landing_page_viewed` |
| Open signup | `signup_started` |
| Create workspace | `signup_completed`, `workspace_created` |
| Sign in / sign out | `login_completed` / `logout_completed` |
| Open assistant and ask a question | `assistant_opened`, `assistant_question_submitted`, response outcome event |
| Ask a synthetic prohibited salary question | `assistant_response_blocked` |
| Trigger a synthetic redaction | `assistant_response_redacted` |
| Open source citation | `source_citation_opened` |
| Send workspace message | `workspace_message_sent` and applicable outcome |
| Create/submit/approve/activate policy | Matching `policy_*` lifecycle events |
| Run policy simulation | `policy_simulated` |
| Open and decide review case | `review_queue_opened`, `review_case_opened`, `review_case_decided` |
| Request/approve/reject/execute agent action | Matching `agent_action_*` event |
| Generate/export evidence report | `evidence_report_generated`, `evidence_report_exported` |
| Verify audit chain | `audit_chain_verified` |
| Upload document | `document_uploaded` |

Inspect network payloads and confirm they contain no raw prompt, answer, card number, salary, email, note, document/policy content, or query string. Confirm DNT disables tracking and that a blocked Mixpanel request does not prevent the TrustShield operation. With no configured token, no Mixpanel requests should be made.

## Automated checks

- Frontend static typecheck: `cd frontend && npm run typecheck`.
- Backend metadata privacy tests: `cd backend && pytest -q app/tests/test_analytics_events.py`.
- Full browser interaction coverage requires the app and seeded API to be running; event interception should target the Mixpanel SDK endpoint and assert no forbidden content values in captured event properties.

Dashboard reports and Live View must be verified in the connected Mixpanel project; repository checks cannot confirm account-side setup.
