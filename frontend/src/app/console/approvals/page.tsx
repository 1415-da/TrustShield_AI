"use client";

import { Inbox } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/console/shell";
import { ActionBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useApi } from "@/hooks/useApi";
import { humanize, timeAgo } from "@/lib/format";
import type { PolicyApproval } from "@/lib/types";
import { cn } from "@/lib/utils";

const TABS = [["PENDING", "Awaiting decision"], ["all", "All decisions"]] as const;

export default function ApprovalInboxPage() {
  const [status, setStatus] = useState("PENDING");
  const { data, error, loading, reload } = useApi<PolicyApproval[]>(`/admin/policy-approvals?status=${status}`, 20000);
  return (
    <>
      <PageHeader eyebrow="Policy approvals" title="Approval inbox" description="Policy versions waiting for a second pair of eyes. Authors can't approve their own changes." />
      <div role="tablist" aria-label="Approval status" className="mb-5 inline-flex rounded-full border border-hair bg-cream-50 p-1">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={status === k} onClick={() => setStatus(k)}
            className={cn("rounded-full px-4 py-1.5 text-[13px] transition", status === k ? "bg-forest text-cream" : "text-ink-700 hover:text-ink")}>{label}</button>
        ))}
      </div>
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {loading && !data ? <LoadingRows rows={4} /> : !data?.length ? (
        <EmptyState icon={<Inbox className="h-6 w-6" />} title={status === "PENDING" ? "Nothing waiting for approval" : "No decisions yet"} body="Submitted policy versions appear here with their diff and impact analysis." />
      ) : (
        <ul className="space-y-2.5" data-testid="approval-inbox">
          {data.map((a) => (
            <li key={a.id}>
              <Link href={`/console/approvals/${a.id}`} className="group block rounded-2xl border border-hair bg-cream-50 p-4 transition hover:border-forest/40 hover:bg-white sm:p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-serif text-[20px] leading-tight group-hover:text-forest">{a.policy_name}</span>
                  <Badge>v{a.version}</Badge>
                  <ActionBadge action={a.status} />
                  {a.risk_category && <Badge tone="lilac">{humanize(a.risk_category)}</Badge>}
                  <span className="ml-auto text-[12px] text-ink-500">{timeAgo(a.requested_at)}</span>
                </div>
                <p className="mt-2 text-[13.5px] text-ink-700">{a.request_note || "No note from the author."}</p>
                <p className="mt-1 text-[12px] text-ink-500">Requested by {a.requested_by_email}{a.decided_by_email ? ` · decided by ${a.decided_by_email}` : ""}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
