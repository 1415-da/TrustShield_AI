"use client";

import { ChevronLeft, ChevronRight, Link2, ShieldCheck, ShieldX } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/console/shell";
import { ActionBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { dateTime, ROLE_LABELS } from "@/lib/format";
import type { AuditEvent, RuleMatch } from "@/lib/types";

interface Page { items: AuditEvent[]; total: number; page: number; page_size: number }
interface Detail { event: AuditEvent; guardrail_decisions: { stage: string; action: string; risk_score: number; matches: RuleMatch[]; redaction_count: number; latency_ms: number }[] }

const TYPES = [["", "All events"], ["assistant", "Assistant requests"], ["review", "Review actions"], ["policy", "Policy changes"], ["auth", "Sign-ins"], ["document", "Documents"], ["simulation", "Simulations"], ["test_run", "Test runs"], ["api_key", "API keys"]];

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const [type, setType] = useState("");
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [requestId, setRequestId] = useState("");
  const qs = new URLSearchParams({ page: String(page), page_size: "25", ...(type && { event_type: type }), ...(action && { action }), ...(actor && { actor }), ...(requestId && { request_id: requestId.trim() }) });
  const { data, error, loading, reload } = useApi<Page>(`/admin/audit-events?${qs.toString()}`);
  const [openId, setOpenId] = useState<number | null>(null);
  const detail = useApi<Detail>(openId ? `/admin/audit-events/${openId}` : null);
  const [chain, setChain] = useState<{ valid: boolean; checked: number; broken_at_event_id: number | null } | null>(null);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <>
      <PageHeader
        eyebrow="Accountability"
        title="Audit log"
        description="Append-only and hash-chained. Sensitive values appear only as masks or SHA-256 hashes."
        actions={
          <div className="flex items-center gap-3">
            {chain && (
              <Badge tone={chain.valid ? "sage" : "crimson"} data-testid="chain-status">
                {chain.valid ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldX className="h-3.5 w-3.5" />}
                {chain.valid ? `Chain intact · ${chain.checked} events` : `Broken at #${chain.broken_at_event_id}`}
              </Badge>
            )}
            <Button variant="secondary" onClick={async () => setChain(await api("/admin/audit-events/verify"))}><Link2 className="h-4 w-4" />Verify chain</Button>
          </div>
        }
      />
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Select aria-label="Event type" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>
        <Select aria-label="Action" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
          <option value="">Any action</option>{["ALLOW", "REDACT", "REVIEW", "BLOCK", "ESCALATE", "SHOW", "SHOW_WITH_WARNING", "SEND_TO_REVIEW", "APPROVE", "EDIT", "REJECT"].map((a) => <option key={a}>{a}</option>)}
        </Select>
        <Input aria-label="Actor email" placeholder="Actor email contains…" value={actor} onChange={(e) => { setActor(e.target.value); setPage(1); }} />
        <Input aria-label="Request ID" placeholder="Request ID" className="font-mono text-[13px]" value={requestId} onChange={(e) => { setRequestId(e.target.value); setPage(1); }} />
      </div>
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {loading && !data ? <LoadingRows rows={8} /> : !data?.items.length ? <EmptyState title="No events match" /> : (
        <div className="panel overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-[13px]" data-testid="audit-table">
            <thead className="border-b border-hair text-[12px] text-ink-500">
              <tr><th className="px-5 py-3 font-medium">Time</th><th className="px-3 py-3 font-medium">Event</th><th className="px-3 py-3 font-medium">Actor</th><th className="px-3 py-3 font-medium">Decision</th><th className="px-3 py-3 text-right font-medium">Risk in / out</th><th className="px-3 py-3 text-right font-medium">Redactions</th><th className="px-5 py-3 text-right font-medium">Latency</th></tr>
            </thead>
            <tbody>
              {data.items.map((e) => (
                <tr key={e.id} onClick={() => setOpenId(e.id)} className="cursor-pointer border-b border-hair last:border-0 hover:bg-white/60" tabIndex={0} onKeyDown={(k) => k.key === "Enter" && setOpenId(e.id)}>
                  <td className="whitespace-nowrap px-5 py-3 text-ink-500">{dateTime(e.created_at)}</td>
                  <td className="px-3 py-3 font-mono text-[12px]">{e.event_type}</td>
                  <td className="px-3 py-3"><span className="block max-w-[200px] truncate">{e.actor_email ?? "—"}</span><span className="text-[11.5px] text-ink-500">{e.actor_role ? ROLE_LABELS[e.actor_role] ?? e.actor_role : ""}</span></td>
                  <td className="px-3 py-3"><span className="flex flex-wrap gap-1">{e.input_action && <ActionBadge action={e.input_action} />}{e.output_action && <ActionBadge action={e.output_action} />}{!e.input_action && <ActionBadge action={e.final_action} />}</span></td>
                  <td className="num px-3 py-3 text-right text-ink-700">{e.input_risk_score?.toFixed(2) ?? "—"} / {e.output_risk_score?.toFixed(2) ?? "—"}</td>
                  <td className="num px-3 py-3 text-right">{e.redaction_count || "—"}</td>
                  <td className="num px-5 py-3 text-right text-ink-500">{e.latency_ms ? `${Math.round(e.latency_ms)}ms` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-hair px-5 py-3 text-[12.5px] text-ink-500">
            <span className="num">{data.total} events</span>
            <div className="flex items-center gap-2">
              <Button size="icon" variant="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
              <span className="num">Page {page} of {pages}</span>
              <Button size="icon" variant="ghost" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        </div>
      )}
      <Dialog open={openId !== null} onClose={() => setOpenId(null)} title={detail.data ? detail.data.event.event_type : "Event"} description={detail.data ? dateTime(detail.data.event.created_at) : undefined} side>
        {!detail.data ? <LoadingRows rows={4} /> : (
          <div className="space-y-5 text-[13px]">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
              {([
                ["Request ID", detail.data.event.request_id], ["Actor", detail.data.event.actor_email], ["Role", detail.data.event.actor_role],
                ["App ID", detail.data.event.app_id], ["Model", detail.data.event.model_provider ? `${detail.data.event.model_provider} / ${detail.data.event.model_name}` : null],
                ["Review case", detail.data.event.review_case_id], ["Policies", detail.data.event.policy_ids.join(", ") || null], ["Final action", detail.data.event.final_action],
              ] as [string, unknown][]).map(([k, v]) => (
                <div key={k}><dt className="text-[11.5px] text-ink-500">{k}</dt><dd className="break-all font-mono text-[12px]">{v === null || v === undefined || v === "" ? "—" : String(v)}</dd></div>
              ))}
            </dl>
            {detail.data.guardrail_decisions.length > 0 && (
              <div>
                <p className="eyebrow mb-2">Guardrail stages</p>
                <ul className="space-y-2">
                  {detail.data.guardrail_decisions.map((d) => (
                    <li key={d.stage} className="rounded-xl border border-hair bg-white/50 p-3">
                      <div className="flex items-center justify-between"><span className="font-medium capitalize">{d.stage}</span><span className="flex items-center gap-2 text-[11.5px] text-ink-500"><span className="num">risk {d.risk_score.toFixed(2)}</span><ActionBadge action={d.action} /></span></div>
                      {d.matches.map((m, i) => <p key={i} className="mt-1 font-mono text-[11.5px] text-ink-700">{m.policy_name} › {m.rule_name} — {m.evidence}</p>)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <p className="eyebrow mb-2">Details (masked)</p>
              <pre className="scrollbar-thin overflow-x-auto rounded-xl bg-ink p-3 text-[11.5px] leading-relaxed text-cream">{JSON.stringify(detail.data.event.details, null, 2)}</pre>
            </div>
            <div className="space-y-1 font-mono text-[10.5px] text-ink-500">
              <p className="break-all">content sha256 {detail.data.event.content_hash ?? "—"}</p>
              <p className="break-all">prev {detail.data.event.prev_hash}</p>
              <p className="break-all">hash {detail.data.event.event_hash}</p>
            </div>
          </div>
        )}
      </Dialog>
    </>
  );
}
