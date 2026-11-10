"use client";

import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/console/shell";
import { ActionBadge, SeverityBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Input, Select, Switch } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { Policy } from "@/lib/types";

export default function PoliciesPage() {
  const { can } = useAuth();
  const writable = can("policies:write");
  const { data, error, loading, reload, setData } = useApi<Policy[]>("/admin/policies");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [toggleError, setToggleError] = useState<string | null>(null);

  const categories = useMemo(() => [...new Set((data ?? []).map((p) => p.risk_category))].sort(), [data]);
  const rows = (data ?? []).filter((p) => (!cat || p.risk_category === cat) && (!q || `${p.name} ${p.description}`.toLowerCase().includes(q.toLowerCase())));

  const toggle = async (p: Policy) => {
    setToggleError(null);
    try {
      const updated = await api<Policy>(`/admin/policies/${p.id}/${p.is_active ? "deactivate" : "activate"}`, { method: "POST" });
      setData((data ?? []).map((x) => (x.id === p.id ? updated : x)));
    } catch (e) {
      setToggleError(e instanceof ApiError ? e.message : "Could not update policy");
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Policy Studio"
        title="Policies"
        description="Every rule TrustShield enforces lives here — versioned on each change and testable before it goes live."
        actions={writable && <Link href="/console/policies/new" className={buttonVariants()}><Plus className="h-4 w-4" />New policy</Link>}
      />
      <div className="mb-5 flex flex-wrap gap-3">
        <div className="relative min-w-[220px] flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <Input aria-label="Search policies" placeholder="Search policies" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select aria-label="Filter by category" className="w-auto min-w-[180px]" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{humanize(c)}</option>)}
        </Select>
      </div>
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {toggleError && <div className="mb-4"><ErrorState message={toggleError} /></div>}
      {loading ? <LoadingRows rows={6} /> : rows.length === 0 ? (
        <EmptyState title="No policies match" body="Try a different search or category." />
      ) : (
        <div className="panel overflow-hidden">
          <table className="w-full text-left text-[13.5px]">
            <thead className="border-b border-hair text-[12px] text-ink-500">
              <tr>
                <th className="px-5 py-3 font-medium">Policy</th>
                <th className="hidden px-3 py-3 font-medium md:table-cell">Category</th>
                <th className="px-3 py-3 font-medium">Action</th>
                <th className="hidden px-3 py-3 font-medium sm:table-cell">Severity</th>
                <th className="hidden px-3 py-3 font-medium lg:table-cell">Rules</th>
                <th className="hidden px-3 py-3 font-medium lg:table-cell">Version</th>
                <th className="px-5 py-3 text-right font-medium">Active</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="border-b border-hair last:border-0 hover:bg-white/50">
                  <td className="px-5 py-3.5">
                    <Link href={`/console/policies/${p.id}`} className="font-medium hover:text-forest">{p.name}</Link>
                    <p className="line-clamp-1 max-w-md text-[12.5px] text-ink-500">{p.description}</p>
                  </td>
                  <td className="hidden px-3 md:table-cell"><Badge>{humanize(p.risk_category)}</Badge></td>
                  <td className="px-3"><ActionBadge action={p.action} /></td>
                  <td className="hidden px-3 sm:table-cell"><SeverityBadge severity={p.severity} /></td>
                  <td className="num hidden px-3 text-ink-700 lg:table-cell">{p.rules.length}</td>
                  <td className="num hidden px-3 text-ink-500 lg:table-cell">v{p.version}</td>
                  <td className="px-5 text-right"><Switch checked={p.is_active} onChange={() => void toggle(p)} label={`${p.name} active`} disabled={!writable} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
