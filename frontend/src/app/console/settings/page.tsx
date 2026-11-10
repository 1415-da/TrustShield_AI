"use client";

import { AlertTriangle } from "lucide-react";

import { PageHeader, Section } from "@/components/console/shell";
import { Badge } from "@/components/ui/badge";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useApi } from "@/hooks/useApi";
import { humanize } from "@/lib/format";

type Settings = Record<string, Record<string, string | number | boolean> | string>;

export default function SettingsPage() {
  const { data, error, loading, reload } = useApi<Settings>("/admin/settings");
  if (loading) return <LoadingRows rows={5} />;
  if (error || !data) return <ErrorState message={error?.message ?? "Unavailable"} onRetry={reload} />;
  const groups = Object.entries(data).filter(([, v]) => typeof v === "object") as [string, Record<string, string | number | boolean>][];
  const auth = data.auth as Record<string, boolean>;
  return (
    <>
      <PageHeader eyebrow="Configuration" title="Settings" description="Gateway configuration comes from environment variables and is read-only here. Guardrail thresholds are policy rules — edit them in Policy Studio." />
      {auth.jwt_secret_is_default && (
        <div role="alert" className="mb-6 flex items-start gap-3 rounded-2xl border border-amber/40 bg-amber-100/70 px-4 py-3 text-[13.5px] text-amber-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />JWT_SECRET is still the default value. Set a strong secret before exposing this deployment.
        </div>
      )}
      <div className="grid gap-6 md:grid-cols-2">
        {groups.map(([group, values]) => (
          <Section key={group} title={group === "llm" ? "Language model" : group === "pii" ? "PII detection" : humanize(group)}>
            <dl className="space-y-2.5 text-[13.5px]">
              {Object.entries(values).map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-4 border-b border-hair pb-2 last:border-0">
                  <dt className="text-ink-700">{humanize(k)}</dt>
                  <dd className="text-right font-mono text-[12.5px]">{typeof v === "boolean" ? <Badge tone={v ? "sage" : "neutral"}>{v ? "yes" : "no"}</Badge> : String(v)}</dd>
                </div>
              ))}
            </dl>
          </Section>
        ))}
      </div>
    </>
  );
}
