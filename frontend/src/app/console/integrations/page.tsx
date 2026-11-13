"use client";

import { CheckCircle2, CircleAlert, PlugZap, RefreshCw, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader, Section } from "@/components/console/shell";
import { ActionBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, Switch } from "@/components/ui/field";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { dateTime, timeAgo } from "@/lib/format";
import type { IntegrationEvent, IntegrationStatus, WorkspaceChannel } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ChannelList { channels: WorkspaceChannel[]; profiles: { key: string; name: string; description: string }[] }

export default function IntegrationsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const manage = can("integrations:manage");
  const status = useApi<IntegrationStatus>("/integrations/slack/status", 30000);
  const channels = useApi<ChannelList>("/integrations/slack/channels");
  const [eventFilter, setEventFilter] = useState("");
  const events = useApi<IntegrationEvent[]>(`/integrations/slack/events?limit=60${eventFilter ? `&status=${eventFilter}` : ""}`, 15000);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message?: string; mode: string; team?: string } | null>(null);

  const patch = async (c: WorkspaceChannel, body: Partial<WorkspaceChannel>) => {
    try {
      await api(`/integrations/slack/channels/${c.id}`, { method: "PATCH", body });
      toast({ tone: "success", title: `#${c.name} updated`, body: "Applies to the next message in the channel." });
      void channels.reload();
    } catch (e) { toast({ tone: "error", title: "Not saved", body: e instanceof ApiError ? e.message : undefined }); }
  };
  const test = async () => {
    setTesting(true);
    try { setTestResult(await api("/integrations/slack/test", { method: "POST" })); void status.reload(); } finally { setTesting(false); }
  };
  const retry = async (ev: IntegrationEvent) => {
    try {
      const r = await api<IntegrationEvent>(`/integrations/slack/retry/${encodeURIComponent(ev.event_id)}`, { method: "POST" });
      toast({ tone: r.status === "PROCESSED" ? "success" : "error", title: r.status === "PROCESSED" ? "Event reprocessed" : "Retry failed", body: r.error ?? undefined });
      void events.reload();
    } catch (e) { toast({ tone: "error", title: "Retry failed", body: e instanceof ApiError ? e.message : undefined }); }
  };

  const s = status.data;
  const errors = (events.data ?? []).filter((e) => e.error);
  return (
    <>
      <PageHeader eyebrow="Integrations" title="Slack & connected workspace"
        description="Team channels answered by TrustShield with the same guardrails, review workflow and audit trail as the web assistant."
        actions={<><Link href="/workspace" className="inline-flex h-10 items-center rounded-full border border-ink/15 px-5 text-sm hover:bg-white">Connected workspace</Link>
          {manage && <Button onClick={() => void test()} loading={testing}><PlugZap className="h-4 w-4" />Test connection</Button>}</>} />
      {status.error && <ErrorState message={status.error.message} onRetry={status.reload} />}
      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <Section title="Slack connection">
          {!s ? <LoadingRows rows={3} /> : (
            <div className="space-y-3 text-[13.5px]" data-testid="slack-status">
              <p className="flex items-center gap-2">
                {s.slack.configured ? <CheckCircle2 className="h-5 w-5 text-forest" /> : <CircleAlert className="h-5 w-5 text-amber-700" />}
                <span className="font-serif text-[22px]">{s.slack.configured ? `Connected${s.slack.workspace_name ? ` · ${s.slack.workspace_name}` : ""}` : "Slack connection not configured"}</span>
              </p>
              {!s.slack.configured && (
                <p className="text-ink-700">Set <span className="font-mono text-[12.5px]">{s.slack.missing.join(", ")}</span> in the backend environment and restart. The connected workspace keeps working in the meantime.</p>
              )}
              <dl className="grid gap-2 border-t border-hair pt-3 sm:grid-cols-2">
                <div><dt className="text-[11.5px] text-ink-500">Events request URL</dt><dd className="font-mono text-[12px]">{s.slack.events_endpoint}</dd></div>
                <div><dt className="text-[11.5px] text-ink-500">Interactivity URL</dt><dd className="font-mono text-[12px]">{s.slack.interactions_endpoint}</dd></div>
                <div className="sm:col-span-2"><dt className="text-[11.5px] text-ink-500">Bot permissions required</dt>
                  <dd className="mt-1 flex flex-wrap gap-1">{s.slack.required_bot_scopes.map((sc) => <Badge key={sc} className="font-mono">{sc}</Badge>)}</dd></div>
              </dl>
              {testResult && (
                <p className={cn("rounded-xl px-3 py-2 text-[12.5px]", testResult.ok ? "bg-sage-100 text-sage-700" : "bg-amber-100 text-amber-700")} data-testid="test-result">
                  {testResult.ok ? `Connected to ${testResult.team}.` : testResult.message}
                </p>
              )}
            </div>
          )}
        </Section>
        <Section title="Event delivery">
          {!s ? <LoadingRows rows={3} /> : (
            <div className="space-y-4 text-[13.5px]">
              <dl className="grid grid-cols-3 gap-4">
                {[["Processed", s.events.by_status.PROCESSED ?? 0], ["Failed", s.events.by_status.FAILED ?? 0], ["Rate limited", s.events.by_status.RATE_LIMITED ?? 0]].map(([k, v]) => (
                  <div key={String(k)} className="border-l border-forest/30 pl-3"><dt className="text-[12px] text-ink-500">{k}</dt><dd className="num font-serif text-[30px] leading-none text-forest">{v}</dd></div>
                ))}
              </dl>
              <p className="text-ink-500">Workspace messages {s.events.by_source.workspace ?? 0} · Slack messages {s.events.by_source.slack ?? 0} · last event {s.events.last_event_at ? timeAgo(s.events.last_event_at) : "never"}</p>
              <p className="text-[12.5px] text-ink-500">Slack retries are idempotent: a redelivered event is counted but processed only once.</p>
            </div>
          )}
        </Section>
      </div>

      <Section title="Channel policy mapping" description="Each channel applies a policy profile on top of the organization policy library." className="mb-6">
        {!channels.data ? <LoadingRows rows={4} /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-[13.5px]" data-testid="channel-table">
              <thead className="border-b border-hair text-[12px] text-ink-500"><tr><th className="py-2.5 font-medium">Channel</th><th className="font-medium">Source</th><th className="font-medium">Policy profile</th><th className="text-right font-medium">Enabled</th></tr></thead>
              <tbody>
                {channels.data.channels.map((c) => (
                  <tr key={c.id} className="border-b border-hair align-top last:border-0">
                    <td className="py-3 pr-3"><p className="font-medium">#{c.name}</p><p className="text-[12px] text-ink-500">{c.policy_hint || c.description}</p></td>
                    <td className="py-3"><Badge>{c.source === "slack" ? "Slack" : "Workspace"}</Badge></td>
                    <td className="py-3">
                      <Select aria-label={`Policy profile for #${c.name}`} className="w-auto min-w-[200px]" value={c.profile_key} disabled={!manage}
                        onChange={(e) => void patch(c, { profile_key: e.target.value })}>
                        {channels.data!.profiles.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
                      </Select>
                    </td>
                    <td className="py-3 text-right"><Switch checked={c.is_enabled} onChange={(v) => void patch(c, { is_enabled: v })} label={`#${c.name} enabled`} disabled={!manage} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Recent events" actions={
        <div className="flex items-center gap-2">
          <Select aria-label="Event status" className="w-auto" value={eventFilter} onChange={(e) => setEventFilter(e.target.value)}>
            <option value="">All statuses</option>{["PROCESSED", "FAILED", "RATE_LIMITED", "REJECTED", "REJECTED_UNLINKED"].map((x) => <option key={x}>{x}</option>)}
          </Select>
          <Button size="icon" variant="ghost" onClick={() => void events.reload()} aria-label="Refresh events"><RefreshCw className="h-4 w-4" /></Button>
        </div>}>
        {!events.data ? <LoadingRows rows={4} /> : !events.data.length ? <p className="text-[13px] text-ink-500">No events yet.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-[13px]" data-testid="event-table">
              <thead className="border-b border-hair text-[12px] text-ink-500"><tr><th className="py-2 font-medium">Received</th><th className="font-medium">Channel</th><th className="font-medium">From</th><th className="font-medium">Message (masked)</th><th className="font-medium">Status</th><th className="font-medium">Decision</th><th /></tr></thead>
              <tbody>
                {events.data.map((e) => (
                  <tr key={e.id} className="border-b border-hair align-top last:border-0">
                    <td className="whitespace-nowrap py-2.5 pr-3 text-ink-500">{dateTime(e.created_at)}{e.deliveries > 1 && <Badge className="ml-1">×{e.deliveries}</Badge>}</td>
                    <td className="py-2.5 pr-3">#{e.channel}</td>
                    <td className="max-w-[160px] truncate py-2.5 pr-3 text-ink-700">{e.user_email ?? "unlinked"}</td>
                    <td className="max-w-[280px] py-2.5 pr-3 text-ink-700"><span className="line-clamp-2">{e.text_masked}</span>{e.error && <span className="block text-[12px] text-crimson">{e.error}</span>}</td>
                    <td className="py-2.5 pr-3"><ActionBadge action={e.status} /></td>
                    <td className="py-2.5 pr-3">{e.trust_status ? <ActionBadge action={e.trust_status} /> : "—"}</td>
                    <td className="py-2.5 text-right">{manage && e.status === "FAILED" && <Button size="sm" variant="secondary" onClick={() => void retry(e)}><RotateCcw className="h-3.5 w-3.5" />Retry</Button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {errors.length > 0 && <p className="mt-3 text-[12.5px] text-crimson">{errors.length} event{errors.length > 1 ? "s" : ""} with errors in this view.</p>}
      </Section>
    </>
  );
}
