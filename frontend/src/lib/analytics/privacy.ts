const ALLOWED_PROPERTY_KEYS = new Set([
  "workspace_id", "user_role", "surface", "channel", "policy_profile", "feature_area", "decision",
  "policy_categories", "input_risk_tier", "output_risk_tier", "confidence_bucket", "citation_count",
  "response_time_bucket", "model_called", "action_type", "amount_bucket", "approval_role", "report_type",
  "report_period", "record_count_bucket", "export_format", "document_type", "trust_status", "error_code",
  "success", "source", "referrer", "utm_source", "utm_medium", "utm_campaign", "priority", "origin",
  "verification_result", "review_decision", "agent_decision", "simulation_role", "policy_risk_category",
  "industry_bucket", "company_size_bucket",
]);

export const BLOCKED_PROPERTY_KEYS = new Set([
  "prompt", "question", "query", "answer", "response", "raw_text", "message", "content", "policy_text",
  "document_content", "review_note", "email", "phone", "card_number", "bank_account", "salary", "password",
  "token", "api_key", "name", "full_name", "employee_name", "user_email", "user_id", "person_id",
]);

export const ALLOWED_POLICY_CATEGORIES = [
  "pii_protection", "compensation_confidentiality", "payment_card_data", "bank_account_confidentiality",
  "credential_protection", "prompt_injection", "legal_routing", "grounding_confidence", "bulk_exfiltration",
  "system_prompt_leakage", "finance_channel_controls",
] as const;

const ROLES = new Set([
  "employee", "hr_manager", "finance_analyst", "people_manager", "finance_head", "security_admin",
  "compliance_reviewer", "security_auditor", "trustshield_admin",
]);
const CATEGORIES = new Set<string>(ALLOWED_POLICY_CATEGORIES);
const ENUMS: Record<string, Set<string>> = {
  surface: new Set(["public_site", "auth", "demo_playground", "web_assistant", "connected_workspace", "admin_console", "reviewer_console", "policy_studio", "agent_control_center", "evidence_center", "audit_log"]),
  channel: new Set(["general", "finance", "people", "it", "legal", "other"]),
  policy_profile: new Set(["general", "finance", "people", "it", "legal", "other"]),
  feature_area: new Set(["assistant", "workspace", "policy", "review", "agent", "evidence", "audit", "documents", "auth", "signup", "demo", "docs"]),
  decision: new Set(["allow", "redact", "review", "block", "escalate"]),
  input_risk_tier: new Set(["low", "medium", "high", "critical", "unknown"]),
  output_risk_tier: new Set(["low", "medium", "high", "critical", "unknown"]),
  confidence_bucket: new Set(["under_0_55", "0_55_to_0_74", "0_75_to_0_89", "0_90_plus", "unknown"]),
  response_time_bucket: new Set(["under_1s", "1_3s", "3_10s", "10s_plus", "unknown"]),
  action_type: new Set(["leave.view_own", "salary.view", "ticket.create", "leave.update", "salary.update", "expense.reimburse", "vendor.refund", "notify.send", "access.revoke", "record.delete", "permission.change", "other"]),
  amount_bucket: new Set(["under_5k", "5k_50k", "50k_250k", "250k_plus", "unknown"]),
  approval_role: ROLES,
  report_type: new Set(["governance_summary", "sensitive_data", "human_oversight", "policy_changes", "exceptions"]),
  report_period: new Set(["last_7_days", "last_30_days", "last_90_days", "custom"]),
  record_count_bucket: new Set(["zero", "1_10", "11_50", "51_100", "101_plus"]),
  export_format: new Set(["html", "markdown", "json"]),
  document_type: new Set(["pdf", "docx", "txt", "csv", "other"]),
  trust_status: new Set(["verified", "redacted", "needs_review", "blocked"]),
  source: new Set(["website", "navigation", "assistant", "workspace", "console", "slack", "other"]),
  referrer: new Set(["direct", "search", "social", "email", "partner", "other"]),
  utm_source: new Set(["google", "linkedin", "github", "direct", "referral", "other"]),
  utm_medium: new Set(["organic", "paid", "social", "email", "referral", "other"]),
  utm_campaign: new Set(["launch", "demo", "security_checklist", "other"]),
  priority: new Set(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
  origin: new Set(["input", "output", "escalation"]),
  verification_result: new Set(["verified", "failed", "tampered", "unknown"]),
  review_decision: new Set(["approve", "edit", "reject", "escalate", "needs_info"]),
  agent_decision: new Set(["allow", "review", "block", "escalate", "approved", "rejected", "executed"]),
  simulation_role: ROLES,
  policy_risk_category: CATEGORIES,
  industry_bucket: new Set(["technology", "finance", "healthcare", "retail", "manufacturing", "logistics", "public_sector", "professional_services", "other"]),
  company_size_bucket: new Set(["1_200", "201_1000", "1001_5000", "5001_plus", "other"]),
  error_code: new Set(["INVALID_CREDENTIALS", "RATE_LIMITED", "NETWORK_ERROR", "UNKNOWN"]),
};

const COUNT_KEYS = new Set(["citation_count"]);
const BOOLEAN_KEYS = new Set(["model_called", "success"]);
const ROLE_KEYS = new Set(["user_role", "approval_role", "simulation_role"]);

function safeScalar(key: string, value: unknown): string | number | boolean | undefined {
  if (BOOLEAN_KEYS.has(key)) return typeof value === "boolean" ? value : undefined;
  if (COUNT_KEYS.has(key)) return typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.min(100, Math.floor(value))) : undefined;
  if (ROLE_KEYS.has(key)) return typeof value === "string" && ROLES.has(value) ? value : undefined;
  if (key === "workspace_id") {
    return typeof value === "string" && /^(?:ws_)?[A-Za-z0-9_-]{1,80}$/.test(value) ? value : undefined;
  }
  const choices = ENUMS[key];
  if (choices) return typeof value === "string" && choices.has(value) ? value : undefined;
  return undefined;
}

/** Strict allowlist sanitizer. Rejected values are intentionally never logged. */
export function sanitizeAnalyticsProperties(input: Record<string, unknown>): Record<string, string | number | boolean | string[]> {
  const safe: Record<string, string | number | boolean | string[]> = {};
  for (const [key, value] of Object.entries(input)) {
    if (BLOCKED_PROPERTY_KEYS.has(key.toLowerCase()) || !ALLOWED_PROPERTY_KEYS.has(key)) continue;
    if (key === "policy_categories") {
      if (Array.isArray(value)) {
        const categories = value.filter((item): item is string => typeof item === "string" && CATEGORIES.has(item)).slice(0, 11);
        if (categories.length) safe[key] = [...new Set(categories)];
      }
      continue;
    }
    const sanitized = safeScalar(key, value);
    if (sanitized !== undefined) safe[key] = sanitized;
  }
  return safe;
}
