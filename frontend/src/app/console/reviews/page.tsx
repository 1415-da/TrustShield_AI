"use client";

import { Inbox, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/console/shell";
import { SlaChip } from "@/components/console/sla-chip";
import { ActionBadge, SeverityBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Input, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useApi } from "@/hooks/useApi";
import { humanize, readableMasks, ROLE_LABELS, timeAgo } from "@/lib/format";
import type { ReviewCase } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_TABS = [["open", "Open"], ["resolved", "Resolved"], ["", "All"]] as const;

export default function ReviewQueuePage() {
  const [status, setStatus] = useState<string>("open");
  const [priority, setPriority] = useState("");
  const [origin, setOrigin] = useState("");
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => { const t = setTimeout(() => setDebounced(q), 250); return () => clearTimeout(t); }, [q]);
  const params = new URLSearchParams({ ...(status && { status }), ...(priority && { priority }), ...(origin && { origin }), ...(debounced && { q: debounced }) });
  const { data, error, loading, reload } = useApi<ReviewCase[]>(`/reviewer/cases?${params.toString()}`, 20000);

  return (
    <>
      <PageHeader eyebrow="Human in the loop" title="Review queue" description="Answers TrustShield wouldn't deliver on its own. Highest priority and nearest SLA first." />
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Case status" className="flex rounded-full border border-hair bg-cream-50 p-1">
          {STATUS_TABS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={status === k} onClick={() => setStatus(k)}
              className={cn("rounded-full px-4 py-1.5 text-[13px] transition", status === k ? "bg-forest text-cream" : "text-ink-700 hover:text-ink")}>{label}</button>
          ))}
        </div>
        <Select aria-label="Priority" className="w-auto" value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">Any priority</option>{["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((p) => <option key={p} value={p}>{humanize(p.toLowerCase())}</option>)}
        </Select>
        <Select aria-label="Origin" className="w-auto" value={origin} onChange={(e) => setOrigin(e.target.value)}>
          <option value="">Any origin</option><option value="input">Input policy</option><option value="output">Output check</option><option value="escalation">Escalation</option>
        </Select>
        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <Input aria-label="Search cases" className="pl-9" placeholder="Search request or reason" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {loading && !data ? <LoadingRows rows={5} /> : !data?.length ? (
        <EmptyState icon={<Inbox className="h-6 w-6" />} title={status === "open" ? "Queue is clear" : "No cases"} body="Cases appear here when a request needs legal judgement, an answer has weak evidence, or a request is escalated." />
      ) : (
        <ul className="space-y-2.5" data-testid="review-queue">
          {data.map((c) => (
            <li key={c.id}>
              <Link href={`/console/reviews/${c.id}`} className="group block rounded-2xl border border-hair bg-cream-50 p-4 transition hover:border-forest/40 hover:bg-white sm:p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="num font-mono text-[12px] text-ink-400">#{c.id}</span>
                  <SeverityBadge severity={c.priority} />
                  <ActionBadge action={c.status} />
                  <Badge>{c.origin === "escalation" ? "Escalation" : c.origin === "input" ? "Input policy" : "Output check"}</Badge>
                  <span className="ml-auto"><SlaChip c={c} /></span>
                </div>
                <p className="mt-2.5 line-clamp-2 text-[15px] leading-snug group-hover:text-forest">{readableMasks(c.prompt_masked)}</p>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-ink-500">
                  <span>{ROLE_LABELS[c.requester_role] ?? c.requester_role}</span>
                  <span>{c.reason}</span>
                  {c.confidence !== null && <span className="num">confidence {c.confidence.toFixed(2)}</span>}
                  <span>Suggested: {humanize(c.suggested_action.toLowerCase())}</span>
                  <span>{timeAgo(c.created_at)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
