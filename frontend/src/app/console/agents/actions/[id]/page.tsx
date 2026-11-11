"use client";

import { ArrowLeft, Ban, Check, CircleHelp, Play, RotateCcw, ShieldAlert, Undo2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Section } from "@/components/console/shell";
import { ActionBadge, ScoreBar } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { dateTime, humanize, money, ROLE_LABELS } from "@/lib/format";
import type { ActionAuditItem, AgentActionItem } from "@/lib/types";

type Verb = "approve" | "reject" | "request-info" | "escalate" | "execute" | "compensate";
const COPY: Record<Verb, { title: string; desc: string; label: string; danger?: boolean; noteRequired?: boolean }> = {
  approve: { title: "Approve and execute this action?", desc: "TrustShield runs it through the controlled executor immediately. This is recorded with your identity.", label: "Approve & execute" },
  reject: { title: "Reject this action?", desc: "The requester is told it was not approved, with your reason.", label: "Reject", danger: true, noteRequired: true },
  "request-info": { title: "Ask for more information?", desc: "The action pauses until the requester resubmits with what you need.", label: "Request information", noteRequired: true },
  escalate: { title: "Escalate to Security?", desc: "A Security Admin must decide. Use for anything unusual or high-impact.", label: "Escalate" },
  execute: { title: "Run this approved action now?", desc: "Runs (or retries) the executor. Duplicate execution is prevented.", label: "Run action" },
  compensate: { title: "Reverse this executed action?", desc: "The executor applies its compensating step (e.g. voids the refund).", label: "Reverse", danger: true },
};

export default function ActionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { can, user } = useAuth();
  const toast = useToast();
  const action = useApi<AgentActionItem>(`/agent/actions/${id}`);
  const trail = useApi<ActionAuditItem[]>(can("agents:read") ? `/admin/agent/actions/${id}/audit` : null);
  const [verb, setVerb] = useState<Verb | null>(null);

  if (action.loading) return <LoadingRows rows={6} />;
  const a = action.data;
  if (action.error || !a) return <ErrorState message={action.error?.message ?? "Action not found"} onRetry={action.reload} />;
  const awaiting = ["PENDING_APPROVAL", "IN_REVIEW", "ESCALATED"].includes(a.status);
  const myRole = !!a.required_approver_role && !!user?.role_keys.includes(a.required_approver_role) && user.email !== a.requester_email;
  const canDecide = awaiting && can("actions:approve") && myRole;

  const run = async (note: string) => {
    if (!verb) return;
    try {
      await api(`/agent/actions/${a.id}/${verb}`, { method: "POST", body: verb === "execute" ? undefined : { note } });
      toast({ tone: "success", title: { approve: "Approved and executed", reject: "Action rejected", "request-info": "Information requested", escalate: "Escalated to Security", execute: "Action run", compensate: "Action reversed" }[verb] });
      await action.reload();
      void trail.reload();
    } catch (e) {
      toast({ tone: "error", title: "Not completed", body: e instanceof ApiError ? e.message : undefined });
      throw e;
    }
  };

  return (
    <>
      <Link href="/console/agents" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-ink-500 hover:text-ink"><ArrowLeft className="h-3.5 w-3.5" />Agent Control Center</Link>
      <div className="mb-6 flex flex-col gap-4 border-b border-hair pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="eyebrow mb-2">Agent action #{a.id} · {a.agent?.name ?? "no agent"} · {humanize((a.category ?? "unclassified").toLowerCase())}</p>
          <h1 className="text-[30px] leading-tight sm:text-[36px]">{a.summary}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px] text-ink-500">
            <ActionBadge action={a.status} />{a.decision && <ActionBadge action={a.decision} />}
            <span>Requested by {a.requester_email} ({ROLE_LABELS[a.requester_role] ?? a.requester_role}) · {dateTime(a.created_at)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2" data-testid="action-controls">
          {canDecide && <>
            <Button onClick={() => setVerb("approve")} data-testid="approve-action"><Check className="h-4 w-4" />Approve</Button>
            <Button variant="secondary" onClick={() => setVerb("reject")}><Ban className="h-4 w-4" />Reject</Button>
            <Button variant="secondary" onClick={() => setVerb("request-info")}><CircleHelp className="h-4 w-4" />Request info</Button>
            {a.status !== "ESCALATED" && <Button variant="ghost" onClick={() => setVerb("escalate")}><ShieldAlert className="h-4 w-4" />Escalate</Button>}
          </>}
          {["APPROVED", "FAILED"].includes(a.status) && (can("agents:manage") || user?.email === a.requester_email) && <Button onClick={() => setVerb("execute")}>{a.status === "FAILED" ? <RotateCcw className="h-4 w-4" /> : <Play className="h-4 w-4" />}{a.status === "FAILED" ? "Retry" : "Run"}</Button>}
          {a.status === "EXECUTED" && can("agents:manage") && <Button variant="ghost" onClick={() => setVerb("compensate")}><Undo2 className="h-4 w-4" />Reverse</Button>}
        </div>
      </div>
      {awaiting && !canDecide && (
        <p className="mb-6 rounded-xl bg-amber-100/70 px-4 py-2.5 text-[13px] text-amber-700">
          Waiting for {ROLE_LABELS[a.required_approver_role ?? ""] ?? a.required_approver_role}. {user?.email === a.requester_email ? "You can't approve your own request." : "Only that role can decide."}
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <div className="space-y-6">
          <Section title="Requested action">
            {a.request_text_masked && <p className="mb-4 rounded-xl bg-ink px-4 py-3 text-[14px] text-cream">{a.request_text_masked}</p>}
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[13.5px] sm:grid-cols-3">
              {[["Target system", a.target_system || "—"], ["Target record", a.target_record || "—"], ["Business impact", money(a.amount, a.currency)],
                ["Recipient", a.external ? "External party" : "Internal"], ["Approver", a.required_approver_role ? ROLE_LABELS[a.required_approver_role] ?? a.required_approver_role : "Not required"],
                ["Expected completion", a.employee_view.eta]].map(([k, v]) => (
                <div key={k}><dt className="text-[11.5px] text-ink-500">{k}</dt><dd>{v}</dd></div>
              ))}
            </dl>
            {a.params && Object.keys(a.params).length > 0 && <pre className="mt-4 overflow-x-auto rounded-xl bg-cream-200/60 p-3 text-[12px]">{JSON.stringify(a.params, null, 2)}</pre>}
            {a.missing_info.length > 0 && <p className="mt-3 text-[13px] text-lilac-700">Missing: {a.missing_info.join("; ")}</p>}
            {a.info_request_note && <p className="mt-3 text-[13px] text-lilac-700">Approver asked: “{a.info_request_note}”</p>}
          </Section>
          <Section title="Policy basis" description="Why TrustShield decided what it did. The first entry decided the outcome.">
            <div className="mb-4 text-[12.5px]"><span className="text-ink-700">Action risk</span><ScoreBar value={a.risk_score} tone={a.risk_score >= 0.9 ? "crimson" : a.risk_score >= 0.5 ? "amber" : "forest"} label="Action risk" /></div>
            <ol className="space-y-2">
              {a.policy_basis.map((b, i) => (
                <li key={i} className="rounded-xl border border-hair bg-white/50 px-3 py-2.5 text-[13px]">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{b.name}</span><span className="ml-auto"><ActionBadge action={b.decision} /></span></div>
                  {b.reason && <p className="mt-0.5 text-ink-700">{b.reason}</p>}
                </li>
              ))}
            </ol>
          </Section>
          {a.result && <Section title="Execution result"><pre className="overflow-x-auto rounded-xl bg-sage-100/60 p-3 text-[12px]">{JSON.stringify(a.result, null, 2)}</pre></Section>}
          {a.error && <ErrorState message={`Execution failed: ${a.error}. Nothing was changed.`} />}
        </div>
        <div className="space-y-6">
          <Section title="Approvals">
            {!a.approvals?.length ? <p className="text-[13px] text-ink-500">No approval was required.</p> : (
              <ol className="space-y-2 text-[13px]">{a.approvals.map((x) => (
                <li key={x.id} className="rounded-xl border border-hair bg-white/50 px-3 py-2">
                  <div className="flex items-center gap-2"><Badge>{ROLE_LABELS[x.approver_role] ?? x.approver_role}</Badge><ActionBadge action={x.status} /></div>
                  {x.decided_by_email && <p className="mt-1 text-[12px] text-ink-500">{x.decided_by_email} · {dateTime(x.decided_at ?? x.created_at)}</p>}
                  {x.note && <p className="mt-1">{x.note}</p>}
                </li>))}</ol>
            )}
          </Section>
          <Section title="Executions">
            {!a.executions?.length ? <p className="text-[13px] text-ink-500">Not executed.</p> : (
              <ol className="space-y-2 text-[13px]">{a.executions.map((x) => (
                <li key={x.id} className="flex items-start justify-between gap-3 border-b border-hair pb-2 last:border-0">
                  <span><span className="font-mono text-[12px]">{x.executor}</span> · attempt {x.attempt}<span className="block text-[12px] text-ink-500">{x.executed_by_email} · {dateTime(x.started_at)}</span>
                    {x.error && <span className="block text-[12px] text-crimson">{x.error}</span>}</span>
                  <ActionBadge action={x.status} />
                </li>))}</ol>
            )}
          </Section>
          {can("agents:read") && (
            <Section title="Audit trail">
              {!trail.data ? <LoadingRows rows={3} /> : (
                <ol className="space-y-2 text-[12.5px]" data-testid="action-audit">{trail.data.map((t) => (
                  <li key={t.id}>
                    <p className="flex flex-wrap items-center gap-1.5"><span className="font-medium">{humanize(t.event_type)}</span>{t.to_status && <ActionBadge action={t.to_status} />}
                      <span className="text-ink-500">· {t.actor_email ?? "system"} · {dateTime(t.created_at)}</span></p>
                    {t.note && <p className="text-ink-700">{t.note}</p>}
                    {t.audit_event_id && <p className="font-mono text-[10.5px] text-ink-400">audit #{t.audit_event_id}</p>}
                  </li>))}</ol>
              )}
            </Section>
          )}
        </div>
      </div>
      {verb && <ConfirmDialog open onClose={() => setVerb(null)} title={COPY[verb].title} description={COPY[verb].desc} confirmLabel={COPY[verb].label}
        tone={COPY[verb].danger ? "danger" : "primary"} withNote={verb !== "execute"} noteRequired={COPY[verb].noteRequired} onConfirm={run} />}
    </>
  );
}
