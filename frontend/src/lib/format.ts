export function timeAgo(iso: string, now: number = Date.now()): string {
  const diff = (now - new Date(iso).getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function pct(v: number | null | undefined, digits = 0): string {
  return v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;
}

export function minutes(m: number | null | undefined): string {
  if (m === null || m === undefined) return "—";
  const total = Math.round(m);
  if (total < 60) return `${total}m`;
  return `${Math.floor(total / 60)}h ${total % 60}m`;
}

export function slaRemaining(dueIso: string, now: number = Date.now()): { label: string; overdue: boolean; urgent: boolean } {
  const ms = new Date(dueIso).getTime() - now;
  const abs = Math.abs(ms) / 60000;
  const text = abs < 60 ? `${Math.round(abs)}m` : abs < 1440 ? `${Math.floor(abs / 60)}h ${Math.round(abs % 60)}m` : `${Math.floor(abs / 1440)}d`;
  return { label: ms < 0 ? `${text} overdue` : `${text} left`, overdue: ms < 0, urgent: ms >= 0 && ms < 60 * 60000 };
}

export const ROLE_LABELS: Record<string, string> = {
  employee: "Employee",
  hr_manager: "HR Manager",
  finance_analyst: "Finance Analyst",
  compliance_reviewer: "Compliance Reviewer",
  security_auditor: "Security / Audit",
  trustshield_admin: "TrustShield Admin",
};

export const ENTITY_LABELS: Record<string, string> = {
  EMAIL_ADDRESS: "Email address",
  PHONE_NUMBER: "Phone number",
  CREDIT_CARD: "Card number",
  BANK_ACCOUNT: "Bank account",
  IBAN_CODE: "IBAN",
  US_SSN: "SSN-like ID",
  TEST_NATIONAL_ID: "Test national ID",
  EMPLOYEE_ID: "Employee ID",
  SALARY_AMOUNT: "Salary figure",
  CREDENTIAL: "Credential",
  PERSON: "Person name",
  IP_ADDRESS: "IP address",
};

/** Replace masked placeholders like <EMAIL_ADDRESS> with readable text for compact UI (titles, lists). */
export function readableMasks(s: string): string {
  return s.replace(/<([A-Z_]+)>/g, (_, t: string) => `[${(ENTITY_LABELS[t] ?? t).toLowerCase()}]`);
}

export function humanize(s: string): string {
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\b(Llm|Pii|Ssn|Id|Api)\b/g, (w) => w.toUpperCase());
}
