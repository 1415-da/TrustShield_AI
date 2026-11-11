"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { DecisionTimeline, RankedBars } from "@/components/console/charts";
import { firstAllowed, PageHeader, Section, Stat } from "@/components/console/shell";
import { Badge } from "@/components/ui/badge";
import { ErrorState, LoadingRows, Skeleton } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { humanize, minutes, pct } from "@/lib/format";
import type { GuardrailStats, Overview, ReviewStats } from "@/lib/types";

export default function OverviewPage() {
  const { can } = useAuth();
  const router = useRouter();
  const allowed = can("analytics:read");
  useEffect(() => {
    if (!allowed) {
      const next = firstAllowed(can);
      if (next && next !== "/console") router.replace(next);
    }
  }, [allowed, can, router]);

  const overview = useApi<Overview>(allowed ? "/admin/analytics/overview" : null);
  const guard = useApi<GuardrailStats>(allowed ? "/admin/analytics/guardrails" : null);
  const reviews = useApi<ReviewStats>(allowed ? "/admin/analytics/reviews" : null);
  if (!allowed) return <LoadingRows />;

  const o = overview.data;
  const run = o?.latest_test_run;
  return (
    <>
      <PageHeader
        eyebrow="Governance overview"
        title="How the gateway is behaving"
        description="Every request processed by TrustShield in the last 14 days, by the decision it received."
        actions={<Badge tone="lilac">Operational data · last 14 days</Badge>}
      />
      {overview.error && <ErrorState message={overview.error.message} onRetry={overview.reload} />}

      <section className="panel mb-6 grid grid-cols-2 gap-y-6 p-6 md:grid-cols-3 xl:grid-cols-6" aria-label="Key metrics">
        {!o ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16" />) : (
          <>
            <Stat label="Requests" value={o.requests} sub={`${o.allowed} answered directly`} />
            <Stat label="Blocked" value={o.blocked + o.escalated} sub={`${o.escalated} escalated`} tone="crimson" />
            <Stat label="Redactions" value={o.redactions} sub={`across ${o.redacted} requests`} tone="lilac" />
            <Stat label="Open reviews" value={o.review_queue_open} sub={`${reviews.data?.breaching_sla ?? 0} past SLA`} tone="amber" />
            <Stat label="Avg review" value={minutes(o.avg_review_minutes)} sub="created → resolved" />
            <Stat label="LLM calls avoided" value={o.llm_calls_avoided} sub="blocked before the model" tone="forest" />
          </>
        )}
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Section title="Decisions per day" description="Each request receives exactly one outcome.">
          {o ? <DecisionTimeline data={o.timeline} /> : <Skeleton className="h-[260px]" />}
        </Section>
        <Section title="Evaluation suite" description="Latest Test Center run against labelled scenarios." actions={<Link href="/console/tests" className="link text-[13px]">Open</Link>}>
          {!o ? <LoadingRows rows={3} /> : !run ? (
            <p className="text-[13px] text-ink-500">No completed runs yet.</p>
          ) : (
            <div>
              <p className="num font-serif text-[56px] leading-none text-forest">{pct(run.pass_rate)}</p>
              <p className="mt-1 text-[13px] text-ink-500">{run.passed} of {run.total} scenarios passed</p>
              <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-hair pt-4 text-[13px]">
                <div><dt className="eyebrow">False positives</dt><dd className="num mt-1 font-serif text-[26px]">{run.false_positives}</dd><dd className="text-ink-500">rate {pct(run.false_positive_rate, 1)}</dd></div>
                <div><dt className="eyebrow">False negatives</dt><dd className="num mt-1 font-serif text-[26px]">{run.false_negatives}</dd><dd className="text-ink-500">rate {pct(run.false_negative_rate, 1)}</dd></div>
              </dl>
            </div>
          )}
        </Section>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Section title="Policy triggers" description="How often each policy fired.">
          {guard.data ? <RankedBars rows={guard.data.policy_triggers.slice(0, 8).map((p) => ({ label: p.policy, value: p.count }))} /> : <LoadingRows rows={4} />}
        </Section>
        <Section title="Risk categories" description="Rule matches by category.">
          {guard.data ? <RankedBars rows={guard.data.risk_categories.map((c) => ({ label: humanize(c.category), value: c.count }))} /> : <LoadingRows rows={4} />}
        </Section>
        <Section title="Review operations" description="Human-in-the-loop health.">
          {!reviews.data ? <LoadingRows rows={4} /> : (
            <dl className="space-y-3 text-[13.5px]">
              {[
                ["Cases total", reviews.data.total],
                ["Resolved", reviews.data.resolved],
                ["Approval rate", pct(reviews.data.approval_rate)],
                ["Past SLA (open)", reviews.data.breaching_sla],
                ["Escalation origin", reviews.data.by_origin.escalation ?? 0],
                ["Low-confidence origin", reviews.data.by_origin.output ?? 0],
              ].map(([k, v]) => (
                <div key={String(k)} className="flex items-baseline justify-between border-b border-hair pb-2 last:border-0">
                  <dt className="text-ink-700">{k}</dt><dd className="num font-medium">{v}</dd>
                </div>
              ))}
            </dl>
          )}
        </Section>
      </div>
    </>
  );
}
