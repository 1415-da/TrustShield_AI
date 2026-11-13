"use client";

import { Ban, CheckCircle2, CircleHelp, Clock, ShieldAlert, Zap } from "lucide-react";

import { ActionBadge } from "@/components/trust/badges";
import { useApi } from "@/hooks/useApi";
import { money, ROLE_LABELS } from "@/lib/format";
import type { AgentActionItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const OPEN = ["PENDING_APPROVAL", "IN_REVIEW", "ESCALATED", "APPROVED", "EXECUTING"];

/** Employee view of an agent action: what was asked, the decision, who must approve, and the audit reference. */
export function ActionCard({ actionId, initial }: { actionId: number; initial?: AgentActionItem }) {
  const live = useApi<AgentActionItem>(`/agent/actions/${actionId}`, initial && !OPEN.includes(initial.status) ? undefined : 6000);
  const a = live.data ?? initial;
  if (!a) return <div className="h-28 animate-pulse rounded-2xl bg-ink/[0.05]" />;
  const tone = a.status === "EXECUTED" ? "sage" : ["BLOCKED", "REJECTED", "FAILED"].includes(a.status) ? "crimson" : a.status === "NEEDS_INFO" ? "lilac" : "amber";
  const Icon = a.status === "EXECUTED" ? CheckCircle2 : ["BLOCKED", "REJECTED", "FAILED"].includes(a.status) ? Ban : a.status === "NEEDS_INFO" ? CircleHelp : a.status === "ESCALATED" ? ShieldAlert : Clock;
  return (
    // Keyed by status so the card is redrawn cleanly when an approver acts (no stale "pending" text).
    <div key={a.status} className={cn("rounded-[22px] rounded-tl-md border px-4 py-3.5 text-[14px]", {
      sage: "border-sage/40 bg-sage-100/50", crimson: "border-crimson/20 bg-crimson-100/40", lilac: "border-lilac-400/60 bg-lilac-200/60", amber: "border-amber/30 bg-amber-100/50",
    }[tone])} data-testid="action-card" data-status={a.status}>
      <div className="flex flex-wrap items-center gap-2">
        <Zap className="h-3.5 w-3.5 text-forest" /><span className="eyebrow">Agent action</span>
        <ActionBadge action={a.status} />
        {a.agent && <span className="text-[11.5px] text-ink-500">{a.agent.name}</span>}
      </div>
      <p className="mt-2 flex items-start gap-2 font-medium"><Icon className="mt-0.5 h-4 w-4 shrink-0" />{a.employee_view?.headline ?? a.summary}</p>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[12.5px] sm:grid-cols-4">
        <div className="col-span-2"><dt className="text-ink-500">Action</dt><dd>{a.summary}</dd></div>
        <div><dt className="text-ink-500">Target</dt><dd>{a.target_record || a.target_system || "—"}</dd></div>
        <div><dt className="text-ink-500">Amount</dt><dd className="num">{money(a.amount, a.currency)}</dd></div>
        <div><dt className="text-ink-500">Approval</dt><dd>{a.required_approver_role ? (ROLE_LABELS[a.required_approver_role] ?? a.required_approver_role) : a.status === "EXECUTED" ? "Not required" : "—"}</dd></div>
        <div><dt className="text-ink-500">Expected</dt><dd>{a.employee_view?.eta ?? "—"}</dd></div>
        <div className="col-span-2"><dt className="text-ink-500">Policy reason</dt><dd>{a.employee_view?.reason || a.policy_basis?.[0]?.name || "—"}</dd></div>
      </dl>
      {(a.employee_view?.needs?.length ?? 0) > 0 && <p className="mt-2 text-[12.5px] text-lilac-700">Please provide: {a.employee_view!.needs.join("; ")}.</p>}
      {a.employee_view?.note && <p className="mt-2 text-[12.5px] text-lilac-700">Approver asked: “{a.employee_view.note}”</p>}
      {a.result && typeof a.result.outcome === "string" && <p className="mt-2 text-[12.5px] text-sage-700">{a.result.outcome} · ref {String(a.result.reference ?? "")}</p>}
      <p className="mt-2 font-mono text-[10.5px] text-ink-400">audit {a.audit_reference}</p>
    </div>
  );
}
