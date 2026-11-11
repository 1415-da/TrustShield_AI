"use client";

import { CalendarClock, FileCheck2, Library, Wand2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { MultiChips } from "@/components/console/rule-builder";
import { PageHeader, Section } from "@/components/console/shell";
import { ActionBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { dateTime, shortDate, timeAgo } from "@/lib/format";
import type { ComplianceReport, ReportOptions, ReportSchedule, ReportType } from "@/lib/types";
import { cn } from "@/lib/utils";

type Tab = "library" | "builder" | "schedules";
const PRESETS = [[7, "Last 7 days"], [30, "Last 30 days"], [90, "Last quarter"]] as const;
const isoDay = (d: Date) => d.toISOString().slice(0, 10);

export default function EvidenceCenterPage() {
  const { can } = useAuth();
  const writable = can("compliance:write");
  const router = useRouter();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("library");
  const reports = useApi<ComplianceReport[]>("/compliance/reports", 15000);
  const schedules = useApi<ReportSchedule[]>(tab === "schedules" ? "/compliance/schedules" : null);
  const options = useApi<ReportOptions>("/compliance/options");
  const [typeFilter, setTypeFilter] = useState("");

  const [type, setType] = useState<ReportType>("governance_summary");
  const [preset, setPreset] = useState<number | "custom">(30);
  const [start, setStart] = useState(isoDay(new Date(Date.now() - 30 * 86400000)));
  const [end, setEnd] = useState(isoDay(new Date()));
  const [departments, setDepartments] = useState<string[]>([]);
  const [policyIds, setPolicyIds] = useState<string[]>([]);
  const [risk, setRisk] = useState<string[]>([]);
  const [reviewers, setReviewers] = useState<string[]>([]);
  const [incl, setIncl] = useState({ include_reviews: true, include_policy_changes: true, include_sensitive_events: true });
  const [retention, setRetention] = useState("365");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setBusy(true);
    setError(null);
    const period = preset === "custom"
      ? { period_start: `${start}T00:00:00Z`, period_end: `${end}T23:59:59Z` }
      : { period_start: new Date(Date.now() - preset * 86400000).toISOString() };
    try {
      const r = await api<ComplianceReport>("/compliance/reports", { method: "POST", body: {
        report_type: type, ...period, departments, policy_ids: policyIds.map(Number), risk_levels: risk, reviewers, ...incl,
        retention_days: retention ? Number(retention) : null } });
      toast({ tone: "success", title: "Report generated", body: "Stored as an immutable evidence record." });
      router.push(`/console/evidence/${r.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Generation failed");
      setBusy(false);
    }
  };

  const tabs: [Tab, string, typeof Library][] = [["library", "Report library", Library], ...(writable ? [["builder", "Report builder", Wand2] as [Tab, string, typeof Library]] : []), ["schedules", "Scheduled reports", CalendarClock]];
  const library = (reports.data ?? []).filter((r) => !typeFilter || r.report_type === typeFilter);
  const typeTitle = (k: string) => options.data?.report_types.find((t) => t.key === k)?.title ?? k;

  return (
    <>
      <PageHeader eyebrow="Compliance Evidence Center" title="Audit-ready evidence, in minutes"
        description="Generate governance reports from audit records. Every report is immutable, hashed, reproducible, and traceable to the events it was built from."
        actions={writable && <Button onClick={() => setTab("builder")}><FileCheck2 className="h-4 w-4" />Generate report</Button>} />
      <div role="tablist" aria-label="Evidence views" className="mb-6 inline-flex flex-wrap gap-1 rounded-full border border-hair bg-cream-50 p-1">
        {tabs.map(([k, label, Icon]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cn("flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] transition", tab === k ? "bg-forest text-cream" : "text-ink-700 hover:text-ink")}>
            <Icon className="h-3.5 w-3.5" />{label}</button>
        ))}
      </div>

      {tab === "library" && (
        <>
          <div className="mb-4 flex flex-wrap gap-3">
            <Select aria-label="Report type" className="w-auto min-w-[220px]" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">All report types</option>
              {options.data?.report_types.map((t) => <option key={t.key} value={t.key}>{t.title}</option>)}
            </Select>
          </div>
          {reports.error && <ErrorState message={reports.error.message} onRetry={reports.reload} />}
          {reports.loading ? <LoadingRows rows={5} /> : !library.length ? (
            <EmptyState icon={<FileCheck2 className="h-6 w-6" />} title="No reports yet" body="Generate an AI Governance Summary to create your first evidence record."
              action={writable && <Button onClick={() => setTab("builder")}>Open report builder</Button>} />
          ) : (
            <div className="panel overflow-x-auto">
              <table className="w-full min-w-[820px] text-left text-[13.5px]" data-testid="report-library">
                <thead className="border-b border-hair text-[12px] text-ink-500">
                  <tr><th className="px-5 py-3 font-medium">Report</th><th className="px-3 font-medium">Evidence period</th><th className="px-3 font-medium">Status</th><th className="px-3 text-right font-medium">Included records</th><th className="px-3 font-medium">Content hash</th><th className="px-5 font-medium">Generated</th></tr>
                </thead>
                <tbody>
                  {library.map((r) => (
                    <tr key={r.id} className="border-b border-hair last:border-0 hover:bg-white/50">
                      <td className="px-5 py-3.5">
                        <Link href={`/console/evidence/${r.id}`} className="font-medium hover:text-forest">{typeTitle(r.report_type)}</Link>
                        <p className="text-[12px] text-ink-500">Report {r.id} · v{r.version}{r.schedule_id ? " · scheduled" : ""}</p>
                      </td>
                      <td className="px-3 text-ink-700">{shortDate(r.period_start)} – {shortDate(r.period_end)}</td>
                      <td className="px-3"><ActionBadge action={r.status} /></td>
                      <td className="num px-3 text-right">{r.source_record_count}</td>
                      <td className="px-3 font-mono text-[11.5px] text-ink-500">{r.content_hash ? `${r.content_hash.slice(0, 12)}…` : "—"}</td>
                      <td className="px-5 text-ink-500">{timeAgo(r.created_at)} · {r.generated_by_email}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {tab === "builder" && writable && (
        <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
          <div className="space-y-6">
            <Section title="Report type">
              <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Report type">
                {options.data?.report_types.map((t) => (
                  <button key={t.key} role="radio" aria-checked={type === t.key} onClick={() => setType(t.key)} data-testid={`type-${t.key}`}
                    className={cn("rounded-2xl border px-4 py-3 text-left transition", type === t.key ? "border-forest bg-forest-50" : "border-hair bg-white/50 hover:border-forest/40")}>
                    <p className="font-serif text-[18px] leading-tight">{t.title}</p>
                    <p className="mt-1 text-[12.5px] text-ink-500">{t.description}</p>
                  </button>
                ))}
              </div>
            </Section>
            <Section title="Evidence period">
              <div className="flex flex-wrap gap-2">
                {PRESETS.map(([d, label]) => (
                  <button key={d} onClick={() => setPreset(d)} className={cn("rounded-full border px-3.5 py-1.5 text-[13px]", preset === d ? "border-forest bg-forest text-cream" : "border-hair bg-white/60")}>{label}</button>
                ))}
                <button onClick={() => setPreset("custom")} className={cn("rounded-full border px-3.5 py-1.5 text-[13px]", preset === "custom" ? "border-forest bg-forest text-cream" : "border-hair bg-white/60")}>Custom</button>
              </div>
              {preset === "custom" && (
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <Field label="From" htmlFor="ev-start"><Input id="ev-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
                  <Field label="To" htmlFor="ev-end"><Input id="ev-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
                </div>
              )}
            </Section>
            <Section title="Scope" description="Leave a filter empty to include everything.">
              {!options.data ? <LoadingRows rows={3} /> : (
                <div className="space-y-4">
                  <Field label="Departments"><MultiChips options={options.data.departments} value={departments} onChange={setDepartments} labels={Object.fromEntries(options.data.departments.map((d) => [d, d]))} /></Field>
                  <Field label="Policies"><MultiChips options={options.data.policies.map((p) => String(p.id))} value={policyIds} onChange={setPolicyIds} labels={Object.fromEntries(options.data.policies.map((p) => [String(p.id), p.name]))} /></Field>
                  <Field label="Risk levels"><MultiChips options={options.data.risk_levels} value={risk} onChange={setRisk} /></Field>
                  <Field label="Reviewers"><MultiChips options={options.data.reviewers} value={reviewers} onChange={setReviewers} labels={Object.fromEntries(options.data.reviewers.map((r) => [r, r]))} /></Field>
                </div>
              )}
            </Section>
          </div>
          <div className="space-y-6 xl:sticky xl:top-6 xl:self-start">
            <Section title="Include">
              <div className="space-y-2.5">
                <Checkbox checked={incl.include_reviews} onChange={(v) => setIncl({ ...incl, include_reviews: v })} label="Review decisions and SLA performance" />
                <Checkbox checked={incl.include_policy_changes} onChange={(v) => setIncl({ ...incl, include_policy_changes: v })} label="Policy changes during the period" />
                <Checkbox checked={incl.include_sensitive_events} onChange={(v) => setIncl({ ...incl, include_sensitive_events: v })} label="Sensitive-data events (types and counts only)" />
              </div>
              <Field label="Retain evidence for" htmlFor="ev-ret" className="mt-4">
                <Select id="ev-ret" value={retention} onChange={(e) => setRetention(e.target.value)}>
                  <option value="90">90 days</option><option value="365">1 year</option><option value="2555">7 years</option><option value="">No expiry</option>
                </Select>
              </Field>
              {error && <div className="mt-3"><ErrorState message={error} /></div>}
              <Button className="mt-5 w-full" size="lg" onClick={() => void generate()} loading={busy} data-testid="generate-report"><FileCheck2 className="h-4 w-4" />Generate report</Button>
              <p className="mt-2 text-[12px] text-ink-500">Generated from audit records only. The report is hashed and cannot be edited afterwards.</p>
            </Section>
          </div>
        </div>
      )}

      {tab === "schedules" && (
        schedules.loading ? <LoadingRows rows={3} /> : !schedules.data?.length ? (
          <EmptyState icon={<CalendarClock className="h-6 w-6" />} title="No scheduled reports" body="Open any report and choose “Schedule” to regenerate it weekly or monthly." />
        ) : (
          <ul className="space-y-2.5">
            {schedules.data.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-4 rounded-2xl border border-hair bg-cream-50 px-5 py-4">
                <CalendarClock className="h-5 w-5 text-forest" />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{s.title}</p>
                  <p className="text-[12.5px] text-ink-500">{s.cadence === "weekly" ? "Every week" : "Every month"} · covers the previous {String(s.filters.period_days ?? 30)} days · created by {s.created_by_email}</p>
                </div>
                <div className="text-right text-[12.5px] text-ink-500">
                  <p>Next run {dateTime(s.next_run_at)}</p>
                  {s.last_report_id && <Link className="link" href={`/console/evidence/${s.last_report_id}`}>Latest report</Link>}
                </div>
                <Badge tone={s.is_active ? "sage" : "neutral"}>{s.is_active ? "Active" : "Cancelled"}</Badge>
                {writable && s.is_active && <Button size="sm" variant="ghost" onClick={async () => { await api(`/compliance/schedules/${s.id}`, { method: "DELETE" }); toast({ tone: "success", title: "Schedule cancelled" }); void schedules.reload(); }}>Cancel</Button>}
              </li>
            ))}
          </ul>
        )
      )}
    </>
  );
}
