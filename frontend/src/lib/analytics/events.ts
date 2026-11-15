export const ANALYTICS_EVENTS = {
  LANDING_PAGE_VIEWED: "landing_page_viewed",
  PRICING_VIEWED: "pricing_viewed",
  DOCS_VIEWED: "docs_viewed",
  DEMO_PLAYGROUND_RUN: "demo_playground_run",
  SIGNUP_STARTED: "signup_started",
  SIGNUP_COMPLETED: "signup_completed",
  WORKSPACE_CREATED: "workspace_created",
  LOGIN_STARTED: "login_started",
  LOGIN_COMPLETED: "login_completed",
  LOGIN_FAILED: "login_failed",
  LOGOUT_COMPLETED: "logout_completed",
} as const;

export const ASSISTANT_EVENTS = {
  ASSISTANT_OPENED: "assistant_opened",
  ASSISTANT_QUESTION_SUBMITTED: "assistant_question_submitted",
  ASSISTANT_RESPONSE_SHOWN: "assistant_response_shown",
  ASSISTANT_RESPONSE_WARNED: "assistant_response_warned",
  ASSISTANT_RESPONSE_REDACTED: "assistant_response_redacted",
  ASSISTANT_RESPONSE_BLOCKED: "assistant_response_blocked",
  ASSISTANT_RESPONSE_REVIEWED: "assistant_response_reviewed",
  SOURCE_CITATION_OPENED: "source_citation_opened",
} as const;

export const WORKSPACE_EVENTS = {
  WORKSPACE_OPENED: "workspace_opened",
  WORKSPACE_MESSAGE_SENT: "workspace_message_sent",
  WORKSPACE_MESSAGE_BLOCKED: "workspace_message_blocked",
  WORKSPACE_MESSAGE_REVIEWED: "workspace_message_reviewed",
} as const;

export const POLICY_EVENTS = {
  POLICY_STUDIO_OPENED: "policy_studio_opened",
  POLICY_CREATED: "policy_created",
  POLICY_SUBMITTED_FOR_APPROVAL: "policy_submitted_for_approval",
  POLICY_APPROVED: "policy_approved",
  POLICY_REJECTED: "policy_rejected",
  POLICY_ACTIVATED: "policy_activated",
  POLICY_DEACTIVATED: "policy_deactivated",
  POLICY_ROLLED_BACK: "policy_rolled_back",
  POLICY_SIMULATED: "policy_simulated",
} as const;

export const REVIEW_EVENTS = {
  REVIEW_QUEUE_OPENED: "review_queue_opened",
  REVIEW_CASE_OPENED: "review_case_opened",
  REVIEW_CASE_DECIDED: "review_case_decided",
} as const;

export const AGENT_EVENTS = {
  AGENT_CONTROL_CENTER_OPENED: "agent_control_center_opened",
  AGENT_ACTION_REQUESTED: "agent_action_requested",
  AGENT_ACTION_APPROVED: "agent_action_approved",
  AGENT_ACTION_REJECTED: "agent_action_rejected",
  AGENT_ACTION_EXECUTED: "agent_action_executed",
  AGENT_ACTION_BLOCKED: "agent_action_blocked",
} as const;

export const GOVERNANCE_EVENTS = {
  EVIDENCE_CENTER_OPENED: "evidence_center_opened",
  EVIDENCE_REPORT_GENERATED: "evidence_report_generated",
  EVIDENCE_REPORT_EXPORTED: "evidence_report_exported",
  AUDIT_LOG_OPENED: "audit_log_opened",
  AUDIT_CHAIN_VERIFIED: "audit_chain_verified",
  DOCUMENT_UPLOADED: "document_uploaded",
} as const;

export type AnalyticsEvent =
  | (typeof ANALYTICS_EVENTS)[keyof typeof ANALYTICS_EVENTS]
  | (typeof ASSISTANT_EVENTS)[keyof typeof ASSISTANT_EVENTS]
  | (typeof WORKSPACE_EVENTS)[keyof typeof WORKSPACE_EVENTS]
  | (typeof POLICY_EVENTS)[keyof typeof POLICY_EVENTS]
  | (typeof REVIEW_EVENTS)[keyof typeof REVIEW_EVENTS]
  | (typeof AGENT_EVENTS)[keyof typeof AGENT_EVENTS]
  | (typeof GOVERNANCE_EVENTS)[keyof typeof GOVERNANCE_EVENTS];
