"use client";

import { Inbox, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/console/shell";
import { ActionBadge, SeverityBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { humanize, shortDate } from "@/lib/format";
import type { PolicySummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_FILTERS = [["", "All"], ["ACTIVE", "Live"], ["IN_REVIEW", "In review"], ["DRAFT", "Drafts"], ["INACTIVE", "Inactive"]] as const;

export default function PoliciesPage() {
  const { can } = useAuth();
  const { data, error, loading, reload } = useApi<PolicySummary[]>("/admin/policies");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [status, setStatus] = useState("");
  const categories = useMemo(() => [...new Set((data ?? []).map((p) => p.risk_category))].sort(), [data]);
  const rows = (data ?? []).filter((p) => (!cat || p.risk_category === cat)
    && (!status || p.status === status || p.working_status === status)
    && (!q || `${p.name} ${p.description} ${p.owner}`.toLowerCase().includes(q.toLowerCase())));
  const inReview = (data ?? []).filter((p) => p.pending_review).length;

  return (
    <>
      <PageHeader
        eyebrow="Policy Studio"
        title="Policies"
        description="Every rule TrustShield enforces. Changes are drafted, approved by a second person, and activated deliberately — production only ever runs an approved version."
        actions={
          <>
            <Link href="/console/approvals" className={buttonVariants({ variant: "secondary" })}>
              <Inbox className="h-4 w-4" />Approvals{inReview > 0 && <span className="num rounded-full bg-amber-100 px-1.5 text-[11px] font-semibold text-amber-700">{inReview}</span>}
            </Link>
            {can("policies:write") && <Link href="/console/policies/new" className={buttonVariants()}><Plus className="h-4 w-4" />New policy</Link>}
          </>
        }
      />
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Status" className="flex rounded-full border border-hair bg-cream-50 p-1">
          {STATUS_FILTERS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={status === k} onClick={() => setStatus(k)}
              className={cn("rounded-full px-3.5 py-1.5 text-[13px] transition", status === k ? "bg-forest text-cream" : "text-ink-700 hover:text-ink")}>{label}</button>
          ))}
        </div>
        <div className="relative min-w-[220px] flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <Input aria-label="Search policies" placeholder="Search name, owner, description" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select aria-label="Filter by category" className="w-auto min-w-[180px]" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{humanize(c)}</option>)}
        </Select>
      </div>
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {loading ? <LoadingRows rows={6} /> : rows.length === 0 ? (
        <EmptyState title="No policies match" body="Try a different status, search, or category." />
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-[13.5px]" data-testid="policy-table">
            <thead className="border-b border-hair text-[12px] text-ink-500">
              <tr>
                <th className="px-5 py-3 font-medium">Policy</th>
                <th className="px-3 py-3 font-medium">Status</th>
                <th className="px-3 py-3 font-medium">Live</th>
                <th className="px-3 py-3 font-medium">Action</th>
                <th className="hidden px-3 py-3 font-medium md:table-cell">Severity</th>
                <th className="hidden px-3 py-3 font-medium lg:table-cell">Owner</th>
                <th className="hidden px-5 py-3 font-medium lg:table-cell">Next review</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="border-b border-hair last:border-0 hover:bg-white/50">
                  <td className="px-5 py-3.5">
                    <Link href={`/console/policies/${p.id}`} className="font-medium hover:text-forest">{p.name}</Link>
                    <p className="line-clamp-1 max-w-md text-[12.5px] text-ink-500">{humanize(p.risk_category)} · {p.rules_count} rule{p.rules_count === 1 ? "" : "s"}</p>
                  </td>
                  <td className="px-3">
                    <span className="flex flex-wrap gap-1"><ActionBadge action={p.status} />
                      {p.working_status && p.status === "ACTIVE" && <Badge tone={p.working_status === "IN_REVIEW" ? "amber" : "neutral"}>v{p.latest_version} {humanize(p.working_status.toLowerCase())}</Badge>}</span>
                  </td>
                  <td className="num px-3 text-ink-700">{p.active_version ? `v${p.active_version}` : "—"}</td>
                  <td className="px-3"><ActionBadge action={p.action} /></td>
                  <td className="hidden px-3 md:table-cell"><SeverityBadge severity={p.severity} /></td>
                  <td className="hidden px-3 text-ink-700 lg:table-cell">{p.owner || "—"}</td>
                  <td className="hidden px-5 text-ink-500 lg:table-cell">{shortDate(p.next_review_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
