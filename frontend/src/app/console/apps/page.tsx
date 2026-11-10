"use client";

import { Copy, KeyRound, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { PageHeader, Section } from "@/components/console/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Switch } from "@/components/ui/field";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { ConnectedApp } from "@/lib/types";

export default function AppsPage() {
  const apps = useApi<ConnectedApp[]>("/admin/apps");
  const [newKey, setNewKey] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); await apps.reload(); } catch (e) { setError(e instanceof ApiError ? e.message : "Request failed"); }
  };
  const create = (e: FormEvent) => { e.preventDefault(); void run(async () => { await api("/admin/apps", { method: "POST", body: { name, description: desc } }); setCreating(false); setName(""); setDesc(""); }); };
  const issue = (app: ConnectedApp) => run(async () => { const k = await api<{ key: string }>(`/admin/apps/${app.id}/keys`, { method: "POST", body: { name: `key-${app.keys.length + 1}` } }); setNewKey(k.key); });

  return (
    <>
      <PageHeader eyebrow="Integrations" title="Connected apps" description="Apps that send employee requests through TrustShield. Every request is attributed to its app in the audit log." actions={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" />Connect app</Button>} />
      {error && <div className="mb-4"><ErrorState message={error} /></div>}
      {apps.loading ? <LoadingRows rows={3} /> : (
        <div className="grid gap-5 lg:grid-cols-2">
          {apps.data?.map((a) => (
            <Section key={a.id} title={a.name} description={a.description}
              actions={<div className="flex items-center gap-2"><Badge tone={a.status === "active" ? "sage" : "amber"}>{a.status}</Badge><Switch checked={a.status === "active"} label={`${a.name} active`} onChange={(v) => void run(() => api(`/admin/apps/${a.id}`, { method: "PATCH", body: { status: v ? "active" : "paused" } }))} /></div>}>
              <p className="mb-3 text-[12.5px] text-ink-500">Owner: {a.owner_team} · slug <span className="font-mono">{a.slug}</span></p>
              <ul className="space-y-2">
                {a.keys.map((k) => (
                  <li key={k.id} className="flex items-center justify-between gap-3 rounded-xl border border-hair bg-white/50 px-3 py-2 text-[13px]">
                    <span className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-ink-400" /><span className="font-mono">{k.prefix}…</span><span className="text-ink-500">{k.name}</span></span>
                    <span className="flex items-center gap-2 text-[12px] text-ink-500">
                      {k.revoked_at ? <Badge tone="crimson">revoked</Badge> : <>{k.last_used_at ? `used ${timeAgo(k.last_used_at)}` : "never used"}<Button size="sm" variant="ghost" onClick={() => void run(() => api(`/admin/apps/${a.id}/keys/${k.id}/revoke`, { method: "POST" }))}>Revoke</Button></>}
                    </span>
                  </li>
                ))}
                {!a.keys.length && <p className="text-[13px] text-ink-500">{a.slug === "novacorp-assistant-web" ? "First-party app — uses employee sign-in, no key required." : "No API keys yet."}</p>}
              </ul>
              {a.slug !== "novacorp-assistant-web" && <Button size="sm" variant="secondary" className="mt-3" onClick={() => void issue(a)}>Issue API key</Button>}
            </Section>
          ))}
        </div>
      )}
      <Dialog open={creating} onClose={() => setCreating(false)} title="Connect an app">
        <form onSubmit={create} className="space-y-4">
          <Field label="Name" htmlFor="app-name"><Input id="app-name" required minLength={3} value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Description" htmlFor="app-desc"><Input id="app-desc" value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
          <Button type="submit" className="w-full">Create app</Button>
        </form>
      </Dialog>
      <Dialog open={!!newKey} onClose={() => setNewKey(null)} title="Copy your API key" description="This is the only time the key is shown. TrustShield stores only its hash.">
        <div className="flex items-center gap-2 rounded-xl bg-ink p-3 font-mono text-[12px] text-cream"><span className="flex-1 break-all">{newKey}</span>
          <button onClick={() => void navigator.clipboard.writeText(newKey ?? "")} className="rounded-lg p-1.5 hover:bg-cream/10" aria-label="Copy key"><Copy className="h-4 w-4" /></button>
        </div>
        <p className="mt-3 text-[12.5px] text-ink-500">Send it as the <span className="font-mono">X-TrustShield-App-Key</span> header alongside the employee&apos;s bearer token.</p>
      </Dialog>
    </>
  );
}
