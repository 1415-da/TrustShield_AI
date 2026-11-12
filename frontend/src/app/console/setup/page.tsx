"use client";

import { ArrowRight, BookOpen, CheckCircle2, Circle, Copy } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader, Section, Stat } from "@/components/console/shell";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { shortDate } from "@/lib/format";
import type { OrganizationSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const SNIPPET = (origin: string) => `curl -X POST ${origin}/api/v1/guard/input \\
  -H "X-TrustShield-App-Key: $TRUSTSHIELD_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"text": "My card 4111 1111 1111 1111 was charged twice", "subject": {"role": "employee"}}'`;

export default function SetupPage() {
  const { can, refresh } = useAuth();
  const org = useApi<OrganizationSummary>("/orgs/current");
  const toast = useToast();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [origin, setOrigin] = useState("https://your-trustshield-host");
  useEffect(() => setOrigin(window.location.origin), []);
  useEffect(() => { if (org.data) setName(org.data.name); }, [org.data]);

  const rename = async () => {
    setSaving(true);
    try {
      org.setData(await api<OrganizationSummary>("/orgs/current", { method: "PATCH", body: { name } }));
      await refresh();
      toast({ tone: "success", title: "Workspace renamed" });
    } catch (e) {
      toast({ tone: "error", title: e instanceof ApiError ? e.message : "Rename failed" });
    } finally {
      setSaving(false);
    }
  };

  if (org.error) return <ErrorState message={org.error.message} onRetry={() => void org.reload()} />;
  if (!org.data) return <LoadingRows rows={6} />;
  const o = org.data;
  const done = o.onboarding.filter((s) => s.done).length;

  return (
    <>
      <PageHeader eyebrow={o.is_demo ? "Live demo workspace" : "Your workspace"} title={`Welcome to ${o.name}`}
        description="Your organization's isolated TrustShield workspace. Baseline policies are already enforcing — finish these steps to make it yours."
        actions={<Link href="/docs/quickstart" className={buttonVariants({ variant: "secondary" })}><BookOpen className="h-4 w-4" />Quickstart guide</Link>} />

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Section title="Get started" description={`${done} of ${o.onboarding.length} complete`} className="min-w-0">
          <div className="mb-5 h-1.5 overflow-hidden rounded-full bg-ink/[0.06]" role="progressbar" aria-valuemin={0} aria-valuemax={o.onboarding.length} aria-valuenow={done}>
            <div className="h-full rounded-full bg-forest transition-all" style={{ width: `${(done / o.onboarding.length) * 100}%` }} />
          </div>
          <ol className="space-y-2" data-testid="onboarding">
            {o.onboarding.map((s) => (
              <li key={s.key}>
                <Link href={s.href} className={cn("group flex items-center gap-4 rounded-2xl border px-4 py-3.5 transition",
                  s.done ? "border-hair bg-white/40" : "border-hair bg-white/80 hover:border-forest/40 hover:shadow-soft")} data-done={s.done}>
                  {s.done ? <CheckCircle2 className="h-5 w-5 shrink-0 text-forest" /> : <Circle className="h-5 w-5 shrink-0 text-ink-300" />}
                  <span className="flex-1">
                    <span className={cn("block text-[14.5px] font-medium", s.done && "text-ink-500 line-through decoration-ink/20")}>{s.title}</span>
                    <span className="block text-[12.5px] text-ink-500">{s.detail}</span>
                  </span>
                  {!s.done && <ArrowRight className="h-4 w-4 text-ink-400 transition group-hover:translate-x-0.5 group-hover:text-forest" />}
                </Link>
              </li>
            ))}
          </ol>
        </Section>

        <div className="min-w-0 space-y-6">
          <Section title="Workspace">
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Policies" value={o.stats.active_policies} sub="enforcing" tone="forest" />
              <Stat label="People" value={o.stats.users} />
              <Stat label="Requests" value={o.stats.requests} />
            </div>
            <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-hair pt-4 text-[13px]">
              <div><dt className="text-ink-500">Workspace ID</dt><dd className="font-mono">{o.slug}</dd></div>
              <div><dt className="text-ink-500">Created</dt><dd>{shortDate(o.created_at)}</dd></div>
              {o.industry && <div><dt className="text-ink-500">Industry</dt><dd>{o.industry}</dd></div>}
              {o.size && <div><dt className="text-ink-500">Size</dt><dd>{o.size}</dd></div>}
            </dl>
            {can("users:manage") && !o.is_demo && (
              <form className="mt-5 flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); void rename(); }}>
                <Field label="Organization name" htmlFor="org-name" className="flex-1"><Input id="org-name" value={name} minLength={2} onChange={(e) => setName(e.target.value)} /></Field>
                <Button type="submit" variant="secondary" loading={saving} disabled={name.trim() === o.name || name.trim().length < 2}>Save</Button>
              </form>
            )}
          </Section>
          <Section title="Connect your own AI app" description="Create an app key under Connected apps, then call the Guard API around your model.">
            <div className="relative">
              <pre className="scrollbar-thin overflow-x-auto rounded-xl bg-[#0F1F1C] p-4 font-mono text-[11.5px] leading-relaxed text-cream/90"><code>{SNIPPET(origin)}</code></pre>
              <button onClick={() => { void navigator.clipboard?.writeText(SNIPPET(origin)); toast({ tone: "info", title: "Copied" }); }}
                className="absolute right-2 top-2 rounded-lg bg-cream/10 p-1.5 text-cream/70 hover:text-cream" aria-label="Copy snippet"><Copy className="h-3.5 w-3.5" /></button>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-[13px]">
              <Link href="/console/apps" className="link">Create an app key</Link>
              <Link href="/docs/guard-api" className="link">Guard API reference</Link>
            </div>
          </Section>
        </div>
      </div>
    </>
  );
}
