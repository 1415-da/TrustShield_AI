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

export interface Policy {
  id: number;
  name: string;
  description: string;
  risk_category: string;
  sensitive_data_type: string;
  applicable_roles: string[];
  action: InputAction;
  severity: Severity;
  threshold: number;
  user_message: string;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  rules: Rule[];
}

export interface PolicyVersion {
  id: number;
  version: number;
  change_summary: string;
  changed_by: number | null;
  created_at: string;
  snapshot: Record<string, unknown>;
}

export interface Catalogue {
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
  focus_policy: { id: number; name: string; triggered: boolean; matches: RuleMatch[] } | null;
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
