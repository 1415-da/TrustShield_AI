import { AlertCircle, CheckCircle2, EyeOff, Hourglass, ShieldAlert, ShieldX } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/badge";
import type { Severity, TrustStatus } from "@/lib/types";

const TRUST: Record<TrustStatus, { label: string; tone: BadgeTone; Icon: typeof CheckCircle2 }> = {
  verified: { label: "Verified", tone: "sage", Icon: CheckCircle2 },
  redacted: { label: "Redacted", tone: "lilac", Icon: EyeOff },
  needs_review: { label: "Needs review", tone: "amber", Icon: Hourglass },
  blocked: { label: "Blocked", tone: "crimson", Icon: ShieldX },
};

export function TrustBadge({ status, warning }: { status: TrustStatus; warning?: boolean }) {
  // An unrecognised status (e.g. from a newer backend) shows as "Needs review" rather than breaking the page.
  const t = TRUST[status] ?? TRUST.needs_review;
  return (
    <Badge tone={warning && status === "verified" ? "amber" : t.tone} data-testid="trust-badge" data-status={status}>
      {warning && status === "verified" ? <AlertCircle className="h-3.5 w-3.5" /> : <t.Icon className="h-3.5 w-3.5" />}
      {t.label}
      {warning && status === "verified" && <span className="font-normal opacity-80">· limited evidence</span>}
    </Badge>
  );
}

const ACTION_TONE: Record<string, BadgeTone> = {
  ALLOW: "sage", SHOW: "sage", APPROVED: "sage", APPROVE: "sage", verified: "sage",
  REDACT: "lilac", EDITED: "lilac", EDIT: "lilac", redacted: "lilac",
  REVIEW: "amber", SEND_TO_REVIEW: "amber", SHOW_WITH_WARNING: "amber", PENDING: "amber", needs_review: "amber",
  BLOCK: "crimson", REJECTED: "crimson", REJECT: "crimson", blocked: "crimson",
  ESCALATE: "ink", ESCALATED: "ink",
  // policy lifecycle
  DRAFT: "neutral", IN_REVIEW: "amber", CHANGES_REQUESTED: "amber", ACTIVE: "sage", INACTIVE: "neutral",
  ARCHIVED: "neutral", WITHDRAWN: "neutral", REQUESTED: "amber", REVOKED: "neutral", EXPIRED: "neutral",
  // reports & integrations & agent actions
  READY: "sage", GENERATING: "amber", FAILED: "crimson", PROCESSED: "sage", RECEIVED: "amber", DUPLICATE: "neutral",
  RATE_LIMITED: "amber", REJECTED_UNLINKED: "crimson", EXECUTE: "sage", EXECUTED: "sage", REQUIRE_APPROVAL: "amber",
  PENDING_APPROVAL: "amber", NEEDS_INFO: "lilac", INFO_REQUESTED: "lilac", BLOCKED: "crimson", EXECUTING: "amber", COMPENSATED: "lilac",
  SUCCEEDED: "sage",
};

export function ActionBadge({ action, className }: { action: string | null | undefined; className?: string }) {
  if (!action) return <span className="text-ink-400">—</span>;
  return (
    <Badge tone={ACTION_TONE[action] ?? "neutral"} className={className}>
      {action === "ESCALATE" || action === "ESCALATED" ? <ShieldAlert className="h-3 w-3" /> : null}
      {action.replace(/_/g, " ")}
    </Badge>
  );
}

const SEV_TONE: Record<Severity, BadgeTone> = { LOW: "neutral", MEDIUM: "amber", HIGH: "crimson", CRITICAL: "ink" };

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge tone={SEV_TONE[severity]}>{severity.charAt(0) + severity.slice(1).toLowerCase()}</Badge>;
}

export function ScoreBar({ value, tone = "forest", label }: { value: number; tone?: "forest" | "amber" | "crimson"; label?: string }) {
  const color = { forest: "bg-forest", amber: "bg-amber", crimson: "bg-crimson" }[tone];
  return (
    <div className="flex items-center gap-2" aria-label={label ? `${label}: ${Math.round(value * 100)}%` : undefined}>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink/[0.07]">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }} />
      </div>
      <span className="num w-9 text-right text-[12px] text-ink-500">{value.toFixed(2)}</span>
    </div>
  );
}
