export type InputAction = "ALLOW" | "REDACT" | "REVIEW" | "BLOCK" | "ESCALATE";
export type OutputAction = "SHOW" | "SHOW_WITH_WARNING" | "REDACT" | "SEND_TO_REVIEW" | "BLOCK";
export type TrustStatus = "verified" | "needs_review" | "redacted" | "blocked";
export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface User {
  id: number;
  email: string;
  full_name: string;
  department: string;
  title: string;
  is_active: boolean;
  role_keys: string[];
  primary_role: string;
  permissions: string[];
  created_at: string;
  last_login_at: string | null;
  organization: OrganizationRef | null;
}

export interface OrganizationRef {
  id: number;
  name: string;
  slug: string;
  is_demo: boolean;
}

export interface OnboardingStep {
  key: string;
  title: string;
  detail: string;
  done: boolean;
  href: string;
}

export interface OrganizationSummary extends OrganizationRef {
  industry: string;
  size: string;
  created_at: string;
  stats: { users: number; documents: number; active_policies: number; api_keys: number; requests: number; reviewers: number };
  onboarding: OnboardingStep[];
  onboarding_complete: boolean;
}

export interface PlaygroundMatch {
  policy_name: string;
  rule_name: string;
  action: string;
  severity: Severity;
  risk_category: string;
}

export interface PlaygroundStage {
  stage: "input" | "context" | "output";
  action: string;
  risk_score: number;
  latency_ms: number;
  redacted_entity_types: string[];
  matches: PlaygroundMatch[];
}

export interface PlaygroundResult {
  role: string;
  decision: InputAction;
  output_decision: OutputAction | null;
  trust_status: TrustStatus;
  llm_called: boolean;
  sanitized_prompt: string;
  response: string | null;
  explanation: Explanation | null;
  citations: { title: string; heading: string; snippet: string }[];
  stages: PlaygroundStage[];
  latency_ms: number;
}

export interface PublicStats {
  window_days: number;
  requests: number;
  by_decision: Record<string, number>;
  workspaces: number;
}

export interface Citation {
  index: number;
  title: string;
  heading: string;
  document_id: number | null;
  chunk_id: number | null;
  kind: "policy" | "directory";
  score: number;
  snippet: string;
  cited: boolean;
}

export interface ExplanationPolicy {
  id: number;
  name: string;
  severity: Severity;
  category: string;
  reason: string;
}

export interface Explanation {
  headline: string;
  detail: string | null;
  policies: ExplanationPolicy[];
  redactions: { entity_type: string; count: number }[];
  warning: string | null;
  suggestion: string | null;
  confidence: number | null;
  groundedness: number | null;
  confidence_label: string;
  quarantined_sources: number;
  reviewed?: { decision: string; at: string };
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  status: "delivered" | "pending_review" | "blocked";
  trust_status: TrustStatus | null;
  request_id: string;
  action_id?: number | null;
  explanation: Explanation | null;
  citations: Citation[];
  created_at: string;
  updated_at: string;
}

export interface ConversationSummary {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  last_trust_status: TrustStatus | null;
  pending_reviews: number;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[];
}

export interface ChatResponse {
  conversation_id: number;
  user_message: ChatMessage;
  message: ChatMessage;
  decision: {
    request_id: string;
    input_action: InputAction;
    output_action: OutputAction | null;
    trust_status: TrustStatus;
    llm_called: boolean;
    review_case_id: number | null;
    latency_ms: number;
  };
}

export interface Rule {
  key?: string | null;
  id?: number;
  name: string;
  rule_type: "regex" | "keyword" | "pii_entity" | "topic" | "role_permission" | "confidence_threshold";
  match_field: "user_input" | "llm_output" | "retrieved_context";
  pattern: string | null;
  keywords: string[];
  entity_types: string[];
  topic: string | null;
  required_permission: string | null;
  threshold: number | null;
  action: InputAction | null;
  severity: Severity | null;
  applies_to_roles: string[];
  is_active: boolean;
}

export type VersionStatus = "DRAFT" | "IN_REVIEW" | "CHANGES_REQUESTED" | "REJECTED" | "APPROVED" | "ACTIVE" | "INACTIVE" | "ARCHIVED";

/** The immutable definition captured by a policy version. */
export interface PolicyDefinition {
  name: string;
  description: string;
  risk_category: string;
  sensitive_data_type: string;
  owner: string;
  review_cadence_days: number;
  effective_from: string | null;
  effective_to: string | null;
  applicable_roles: string[];
  profiles: string[];
  action: InputAction;
  severity: Severity;
  threshold: number;
  user_message: string;
  rules: Rule[];
}

export interface PolicyVersion {
  id: number;
  policy_id: number;
  version: number;
  status: VersionStatus;
  snapshot: PolicyDefinition;
  snapshot_hash: string;
  change_summary: string;
  based_on_version_id: number | null;
  effective_from: string | null;
  effective_to: string | null;
  created_by_email: string;
  submitted_at: string | null;
  approved_by_email: string | null;
  approved_at: string | null;
  activated_by_email: string | null;
  activated_at: string | null;
  deactivated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PolicySummary {
  id: number;
  name: string;
  description: string;
  risk_category: string;
  owner: string;
  review_cadence_days: number;
  status: VersionStatus;
  action: string;
  severity: Severity;
  rules_count: number;
  active_version: number | null;
  latest_version: number;
  working_status: VersionStatus | null;
  pending_review: boolean;
  next_review_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PolicyDetail extends PolicySummary {
  active: PolicyVersion | null;
  working: PolicyVersion | null;
  versions: { id: number; version: number; status: VersionStatus; change_summary: string; created_by_email: string; approved_by_email: string | null; created_at: string; activated_at: string | null }[];
}

/** Kept for older call sites (simulator etc.). */
export type Policy = PolicySummary;

export interface FieldChange { field: string; before: unknown; after: unknown }

export interface PolicyDiff {
  fields: FieldChange[];
  rules_added: Rule[];
  rules_removed: Rule[];
  rules_changed: { key: string; name: string; changes: FieldChange[] }[];
  has_changes: boolean;
}

export interface ImpactChange {
  code: string; category: string; role: string; prompt: string;
  before: { input: string; output: string | null; trust_status: string };
  after: { input: string; output: string | null; trust_status: string };
  now_matches_expectation: boolean;
}

export interface Impact { computed_at: string; scenarios: number; triggered: number; changed: ImpactChange[]; regressions: number }

export interface PolicyApproval {
  id: number;
  policy_id: number;
  version_id: number;
  status: "PENDING" | "APPROVED" | "CHANGES_REQUESTED" | "REJECTED" | "WITHDRAWN";
  requested_by_email: string;
  request_note: string;
  requested_at: string;
  decided_by_email: string | null;
  decision_note: string;
  decided_at: string | null;
  impact: Impact | null;
  policy_name: string | null;
  version: number | null;
  risk_category: string | null;
}

export interface VersionDetail {
  version: PolicyVersion;
  compared_to: PolicyVersion | null;
  diff: PolicyDiff;
  approval: PolicyApproval | null;
}

export interface PolicyComment { id: number; policy_id: number; version_id: number | null; author_email: string; body: string; created_at: string }

export interface PolicyAuditItem {
  id: number; version_id: number | null; version_number: number | null; event_type: string; from_status: string | null;
  to_status: string | null; actor_email: string | null; actor_role: string | null; note: string; details: Record<string, unknown>;
  audit_event_id: number | null; created_at: string;
}

export interface PolicyExceptionItem {
  id: number; policy_id: number; policy_name: string | null; subject_type: "user" | "role" | "department"; subject: string;
  justification: string; status: "REQUESTED" | "APPROVED" | "REJECTED" | "REVOKED"; requested_by_email: string;
  decided_by_email: string | null; decision_note: string; starts_at: string; expires_at: string; created_at: string;
  decided_at: string | null; revoked_at: string | null; is_expired: boolean;
}

export interface Catalogue {
  profiles: string[];
  rule_types: string[];
  match_fields: string[];
  actions: string[];
  severities: string[];
  topics: string[];
  entity_types: string[];
}

export interface RuleMatch {
  policy_id: number;
  policy_name: string;
  rule_id: number | null;
  rule_name: string;
  rule_type: string;
  match_field: string;
  action: string;
  severity: Severity;
  risk_category: string;
  score: number;
  evidence: string;
  user_message: string;
  policy_version?: number;
}

export interface StageOut {
  stage: string;
  action: string;
  risk_score: number;
  matches: RuleMatch[];
  signals: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  redaction_count: number;
  redacted_entity_types: string[];
  latency_ms: number;
}

export interface SimulationResult {
  role: string;
  role_permissions: string[];
  sanitized_prompt: string;
  input: StageOut | null;
  context: StageOut | null;
  output: StageOut | null;
  final: {
    input_action: InputAction;
    output_action: OutputAction | null;
    trust_status: TrustStatus | null;
    llm_called: boolean;
    response_preview: string | null;
    explanation: Explanation | null;
    citations: Citation[];
  };
  focus_policy: { id: number; name: string; version?: number; triggered: boolean; matches: RuleMatch[] } | null;
}

export interface DocumentItem {
  id: number;
  title: string;
  filename: string;
  content_type: string;
  source: string;
  trust_level: "trusted" | "untrusted";
  status: "processing" | "indexed" | "failed";
  chunk_count: number;
  uploaded_by: number | null;
  created_at: string;
  indexed_at: string | null;
}

export interface DocumentDetail extends DocumentItem {
  content: string;
  chunks: { id: number; ordinal: number; heading: string; text: string; token_count: number }[];
}

export interface ReviewCase {
  id: number;
  request_id: string;
  requester_role: string;
  status: "PENDING" | "ESCALATED" | "APPROVED" | "EDITED" | "REJECTED";
  priority: Severity;
  origin: "input" | "output" | "escalation";
  reason: string;
  risk_score: number;
  confidence: number | null;
  prompt_masked: string;
  suggested_action: string;
  sla_due_at: string;
  created_at: string;
  resolved_at: string | null;
  policy_matches: RuleMatch[];
}

export interface ReviewCaseDetail extends ReviewCase {
  draft_response: string | null;
  final_response: string | null;
  sources: Citation[];
  signals: { grounding?: Record<string, any> | null; input?: Record<string, { score: number; signals: string[] }> }; // eslint-disable-line @typescript-eslint/no-explicit-any
  actions: { id: number; reviewer_id: number; reviewer_email: string; action: string; note: string; edited_response: string | null; created_at: string }[];
  requester_department: string | null;
  resolved_by_email: string | null;
}

export interface AuditEvent {
  id: number;
  event_type: string;
  request_id: string | null;
  actor_user_id: number | null;
  actor_email: string | null;
  actor_role: string | null;
  app_id: number | null;
  policy_ids: number[];
  input_risk_score: number | null;
  output_risk_score: number | null;
  input_action: string | null;
  output_action: string | null;
  final_action: string | null;
  redaction_count: number;
  review_case_id: number | null;
  model_provider: string | null;
  model_name: string | null;
  latency_ms: number | null;
  content_hash: string | null;
  details: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  created_at: string;
  prev_hash: string;
  event_hash: string;
}

export interface Overview {
  window_days: number;
  requests: number;
  allowed: number;
  blocked: number;
  escalated: number;
  redacted: number;
  sent_to_review: number;
  redactions: number;
  llm_calls_avoided: number;
  review_queue_open: number;
  avg_review_minutes: number | null;
  p50_latency_ms: number | null;
  timeline: { date: string; allowed: number; redacted: number; review: number; blocked: number; escalated: number }[];
  latest_test_run: TestRunSummary | null;
  data_label: string;
}

export interface TestRunSummary {
  id: number;
  finished_at: string | null;
  total: number;
  passed: number;
  failed: number;
  false_positives: number;
  false_negatives: number;
  pass_rate: number | null;
  false_positive_rate: number | null;
  false_negative_rate: number | null;
}

export interface GuardrailStats {
  policy_triggers: { policy: string; count: number }[];
  risk_categories: { category: string; count: number }[];
  rule_types: { rule_type: string; count: number }[];
  entities_detected: { entity_type: string; count: number }[];
  stage_actions: Record<string, Record<string, number>>;
  test_runs: TestRunSummary[];
}

export interface ReviewStats {
  total: number;
  open: number;
  breaching_sla: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  by_origin: Record<string, number>;
  avg_resolution_minutes: number | null;
  resolved: number;
  approval_rate: number | null;
}

export interface TestCase {
  id: number;
  code: string;
  name: string;
  category: string;
  role_key: string;
  prompt: string;
  expected_input_actions: string[];
  expected_output_actions: string[];
  notes: string;
  is_active: boolean;
}

export interface TestRun {
  id: number;
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  total: number;
  passed: number;
  failed: number;
  false_positives: number;
  false_negatives: number;
  summary: {
    pass_rate?: number;
    false_positive_rate?: number;
    false_negative_rate?: number;
    safe_cases?: number;
    restrictive_cases?: number;
    either_cases?: number;
    avg_latency_ms?: number;
    by_category?: Record<string, { total: number; passed: number }>;
  };
}

export interface TestResult {
  id: number;
  test_case_id: number;
  passed: boolean;
  actual_input_action: string;
  actual_output_action: string | null;
  trust_status: string;
  matched_policies: string[];
  confidence: number | null;
  latency_ms: number;
  false_positive: boolean;
  false_negative: boolean;
  failure_reason: string;
  code: string;
  name: string;
  category: string;
  role_key: string;
  prompt: string;
  expected_input_actions: string[];
  expected_output_actions: string[];
}

export interface Role {
  id: number;
  key: string;
  name: string;
  description: string;
  permissions: string[];
}

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ConnectedApp {
  id: number;
  name: string;
  slug: string;
  description: string;
  owner_team: string;
  status: "active" | "paused";
  created_at: string;
  keys: ApiKey[];
}

// ---------------------------------------------------------------- compliance evidence
export type ReportType = "governance_summary" | "sensitive_data" | "human_oversight" | "policy_changes" | "exceptions";

export interface ReportSection { title: string; description: string; columns: string[]; rows: (string | number)[][]; empty: string }

export interface ReportContent {
  report_type: ReportType;
  title: string;
  period: { start: string; end: string };
  filters: Record<string, unknown>;
  summary: string[];
  metrics: { label: string; value: string | number; hint?: string }[];
  sections: ReportSection[];
  evidence: { audit_events: number; source_hash: string; statement: string };
}

export interface ComplianceReport {
  id: number;
  report_type: ReportType;
  title: string;
  status: "GENERATING" | "READY" | "FAILED" | "EXPIRED";
  version: number;
  filters: Record<string, unknown>;
  period_start: string;
  period_end: string;
  content_hash: string | null;
  source_record_count: number;
  generated_by_email: string;
  schedule_id: number | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  expires_at: string | null;
  deleted_at: string | null;
  content?: ReportContent | null;
}

export interface ReportOptions {
  report_types: { key: ReportType; title: string; description: string }[];
  departments: string[];
  policies: { id: number; name: string }[];
  risk_levels: string[];
  reviewers: string[];
}

export interface ReportSchedule {
  id: number; report_type: ReportType; title: string; filters: Record<string, unknown>; cadence: "weekly" | "monthly";
  retention_days: number | null; is_active: boolean; created_by_email: string; source_report_id: number | null;
  next_run_at: string; last_run_at: string | null; last_report_id: number | null; created_at: string;
}

export interface VerifyResult {
  stored_hash: string; stored_content_matches_hash: boolean; regenerated_hash: string; reproducible: boolean;
  source_records: number; verified_at: string;
}

// ---------------------------------------------------------------- connected workspace / Slack
export interface WorkspaceChannel {
  id: number; external_id: string; name: string; description: string; policy_hint: string; profile_key: string;
  profile_name: string; source: "internal" | "slack"; is_enabled: boolean; updated_at: string;
}

export interface WorkspaceReply {
  kind: "answer" | "notice" | "private";
  text: string;
  trust_status: TrustStatus | null;
  status?: ChatMessage["status"];
  citations?: Citation[];
  explanation?: Explanation | null;
  message_id?: number;
  conversation_id?: number | null;
  request_id?: string | null;
  review_case_id?: number | null;
  updated_at?: string;
}

export interface WorkspaceItem {
  event_id: string; id: number; source: "workspace" | "slack"; created_at: string; is_mine: boolean;
  author: { name: string; department: string }; text: string | null; withheld: boolean; reply: WorkspaceReply;
}

export interface IntegrationStatus {
  slack: { mode: "connected" | "disabled" | "not_configured"; configured: boolean; enabled: boolean; missing: string[];
    workspace_name: string | null; events_endpoint: string; interactions_endpoint: string; required_bot_scopes: string[];
    socket_mode_token_configured: boolean };
  workspace: { enabled: boolean; channels: number; enabled_channels: number };
  events: { by_status: Record<string, number>; by_source: Record<string, number>; last_event_at: string | null };
  checked_at: string;
}

export interface IntegrationEvent {
  id: number; event_id: string; source: string; channel: string | null; user_email: string | null; status: string;
  deliveries: number; attempts: number; trust_status: string | null; input_action: string | null; request_id: string | null;
  review_case_id: number | null; text_masked: string; error: string | null; created_at: string; processed_at: string | null;
  response_updated_at: string | null;
}

// ---------------------------------------------------------------- agent actions
export type ActionStatus = "PENDING_APPROVAL" | "IN_REVIEW" | "ESCALATED" | "NEEDS_INFO" | "APPROVED" | "EXECUTING" | "EXECUTED"
  | "REJECTED" | "BLOCKED" | "FAILED" | "COMPENSATED";

export interface AgentActionItem {
  id: number;
  agent: { key: string; name: string } | null;
  requester_email: string;
  requester_role: string;
  action_type: string | null;
  category: string | null;
  status: ActionStatus;
  decision: string | null;
  summary: string;
  target_system: string;
  target_record: string;
  amount: number | null;
  currency: string | null;
  external: boolean;
  risk_score: number;
  required_approver_role: string | null;
  policy_basis: { policy_id: number | null; name: string; decision: string; approver_role?: string | null; reason: string }[];
  missing_info: string[];
  info_request_note: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  conversation_id: number | null;
  created_at: string;
  updated_at: string;
  decided_at: string | null;
  executed_at: string | null;
  employee_view: { headline: string; eta: string; reason: string; needs: string[]; note: string | null };
  audit_reference: string;
  request_text_masked?: string;
  params?: Record<string, unknown>;
  approvals?: { id: number; approver_role: string; status: string; decided_by_email: string | null; note: string; created_at: string; decided_at: string | null }[];
  executions?: { id: number; executor: string; attempt: number; status: string; result: Record<string, unknown> | null; error: string | null; executed_by_email: string; started_at: string; finished_at: string | null }[];
  idempotent_replay?: boolean;
}

export interface ActionAuditItem {
  id: number; event_type: string; from_status: string | null; to_status: string | null; actor_email: string | null;
  actor_role: string | null; note: string; details: Record<string, unknown>; audit_event_id: number | null; created_at: string;
}

export interface ActionPolicyItem {
  id: number; name: string; description: string; action_type: string | null; category: string | null;
  conditions: Record<string, unknown>; decision: string; approver_role: string | null; priority: number; is_active: boolean;
  created_by_email: string; updated_at: string;
}

export interface AgentCatalog {
  agents: { id: number; key: string; name: string; description: string; owner_team: string; status: string; allowed_action_types: string[] }[];
  action_types: { id: number; key: string; name: string; category: string; description: string; target_system: string; executor: string; required_permission: string | null; is_enabled: boolean }[];
  categories: string[];
  decisions: string[];
}
