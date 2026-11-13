"use client";

import { Bot, CheckCircle2, Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { PageHeader, Section, Stat } from "@/components/console/shell";
import { ActionBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select, Switch, Textarea } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { humanize, money, ROLE_LABELS, timeAgo } from "@/lib/format";
import { ROLES } from "@/lib/roles";
import type { ActionPolicyItem, AgentActionItem, AgentCatalog } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Roles that approve agent actions (see lib/roles.ts). */
const APPROVER_ROLES = ROLES.filter((r) => ["people_manager", "finance_head", "hr_manager", "security_admin", "compliance_reviewer"].includes(r.key));

type Tab = "overview" | "approvals" | "activity" | "catalog" | "rules";

function ActionRow({ a }: { a: AgentActionItem }) {
  return (
    <li>
      <Link href={`/console/agents/actions/${a.id}`} className="group flex flex-wrap items-center gap-x-4 gap-y-1 rounded-2xl border border-hair bg-cream-50 px-4 py-3 transition hover:border-forest/40 hover:bg-white">
        <span className="num font-mono text-[12px] text-ink-400">#{a.id}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium group-hover:text-forest">{a.summary}</span>
          <span className="text-[12px] text-ink-500">{a.requester_email} · {a.agent?.name ?? "no agent"} · {humanize((a.category ?? "unclassified").toLowerCase())}</span>
        </span>
        <span className="num text-[13px] text-ink-700">{money(a.amount, a.currency)}</span>
        {a.required_approver_role && ["PENDING_APPROVAL", "IN_REVIEW", "ESCALATED"].includes(a.status) && <Badge>{ROLE_LABELS[a.required_approver_role] ?? a.required_approver_role}</Badge>}
        <ActionBadge action={a.status} />
        <span className="w-16 text-right text-[12px] text-ink-500">{timeAgo(a.created_at)}</span>
      </Link>
    </li>
  );
}

const COND_LABEL = (c: Record<string, unknown>) => {
  const parts: string[] = [];
  if (c.amount_gt !== undefined) parts.push(`> ${money(Number(c.amount_gt))}`);
  if (c.amount_gte !== undefined) parts.push(`≥ ${money(Number(c.amount_gte))}`);
  if (c.amount_lt !== undefined) parts.push(`< ${money(Number(c.amount_lt))}`);
  if (c.amount_lte !== undefined) parts.push(`≤ ${money(Number(c.amount_lte))}`);
  if (Array.isArray(c.requester_roles)) parts.push(`requested by ${(c.requester_roles as string[]).map((r) => ROLE_LABELS[r] ?? r).join(" or ")}`);
  if (c.external !== undefined) parts.push(c.external ? "external recipients" : "internal recipients");
  return parts.join(" · ") || "Always";
};

export default function AgentControlCenterPage() {
  const { can } = useAuth();
  const toast = useToast();
  const admin = can("agents:read");
  const manage = can("agents:manage");
  const [tab, setTab] = useState<Tab>(admin ? "overview" : "approvals");
  const [statusFilter, setStatusFilter] = useState("");
  const summary = useApi<{ by_status: Record<string, number>; by_category: Record<string, number>; total: number }>(admin ? "/admin/agent/summary" : null, 20000);
  const recent = useApi<AgentActionItem[]>(admin && (tab === "overview" || tab === "activity") ? `/admin/agent/actions?limit=100${statusFilter ? `&status=${statusFilter}` : ""}` : null, 15000);
  const approvals = useApi<AgentActionItem[]>(can("actions:approve") ? "/agent/actions?scope=approvals" : null, 15000);
  const catalog = useApi<AgentCatalog>(admin ? "/admin/agent/catalog" : null);
  const rules = useApi<ActionPolicyItem[]>(admin && tab === "rules" ? "/admin/agent/action-policies" : null);
  const [editing, setEditing] = useState<ActionPolicyItem | "new" | null>(null);
  const [form, setForm] = useState({ name: "", description: "", scope: "category", action_type: "", category: "FINANCIAL_ACTION", decision: "REQUIRE_APPROVAL",
    approver_role: "finance_head", amount_gt: "", amount_lte: "", priority: "30" });
  const [error, setError] = useState<string | null>(null);

  const s = summary.data?.by_status ?? {};
  const tabs: [Tab, string][] = [...(admin ? [["overview", "Overview"] as [Tab, string]] : []), ...(can("actions:approve") ? [["approvals", `My approvals${approvals.data?.length ? ` (${approvals.data.length})` : ""}`] as [Tab, string]] : []),
    ...(admin ? ([["activity", "Action history"], ["catalog", "Agents & actions"], ["rules", "Approval rules"]] as [Tab, string][]) : [])];

  const openEdit = (p: ActionPolicyItem | "new") => {
    setError(null);
    if (p === "new") setForm({ name: "", description: "", scope: "category", action_type: "", category: "FINANCIAL_ACTION", decision: "REQUIRE_APPROVAL", approver_role: "finance_head", amount_gt: "", amount_lte: "", priority: "30" });
    else setForm({ name: p.name, description: p.description, scope: p.action_type ? "action" : "category", action_type: p.action_type ?? "", category: p.category ?? "",
      decision: p.decision, approver_role: p.approver_role ?? "", amount_gt: p.conditions.amount_gt !== undefined ? String(p.conditions.amount_gt) : "",
      amount_lte: p.conditions.amount_lte !== undefined ? String(p.conditions.amount_lte) : "", priority: String(p.priority) });
    setEditing(p);
  };
  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const existing = editing && editing !== "new" ? editing : null;
    const conditions: Record<string, unknown> = { ...(existing?.conditions ?? {}) };
    delete conditions.amount_gt; delete conditions.amount_lte;
    if (form.amount_gt) conditions.amount_gt = Number(form.amount_gt);
    if (form.amount_lte) conditions.amount_lte = Number(form.amount_lte);
    const approver = ["REQUIRE_APPROVAL", "SEND_TO_REVIEW", "ESCALATE"].includes(form.decision) ? form.approver_role || null : null;
    try {
      if (existing) {
        await api(`/admin/agent/action-policies/${existing.id}`, { method: "PATCH", body: { description: form.description, decision: form.decision, approver_role: approver, conditions, priority: Number(form.priority) } });
      } else {
        await api("/admin/agent/action-policies", { method: "POST", body: { name: form.name, description: form.description, decision: form.decision, approver_role: approver,
          conditions, priority: Number(form.priority), ...(form.scope === "action" ? { action_type: form.action_type } : { category: form.category }) } });
      }
      toast({ tone: "success", title: existing ? "Approval rule updated" : "Approval rule created", body: "Applies to new agent requests immediately." });
      setEditing(null);
      void rules.reload();
    } catch (err) { setError(err instanceof ApiError ? err.message : "Save failed"); }
  };
  const toggle = async (p: ActionPolicyItem) => {
    await api(`/admin/agent/action-policies/${p.id}`, { method: "PATCH", body: { is_active: !p.is_active } });
    toast({ tone: "success", title: `${p.is_active ? "Disabled" : "Enabled"} “${p.name}”` });
    void rules.reload();
  };

  return (
    <>
      <PageHeader eyebrow="Agent Control Center" title="Governed AI actions"
        description="Agents never hold standing permission to act. Every request is classified, checked against your role and approval rules, and executed only through controlled executors." />
      <div role="tablist" aria-label="Agent views" className="mb-6 inline-flex flex-wrap gap-1 rounded-full border border-hair bg-cream-50 p-1">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cn("rounded-full px-4 py-1.5 text-[13px] transition", tab === k ? "bg-forest text-cream" : "text-ink-700 hover:text-ink")}>{label}</button>
        ))}
      </div>

      {tab === "overview" && admin && (
        <>
          <section className="panel mb-6 grid grid-cols-2 gap-y-6 p-6 md:grid-cols-3 xl:grid-cols-6" aria-label="Agent action metrics">
            <Stat label="Requests" value={summary.data?.total ?? "…"} />
            <Stat label="Executed" value={s.EXECUTED ?? 0} tone="forest" />
            <Stat label="Pending approval" value={(s.PENDING_APPROVAL ?? 0) + (s.IN_REVIEW ?? 0)} tone="amber" />
            <Stat label="Escalated" value={s.ESCALATED ?? 0} />
            <Stat label="Blocked" value={(s.BLOCKED ?? 0) + (s.REJECTED ?? 0)} tone="crimson" sub="blocked or rejected" />
            <Stat label="Failed" value={s.FAILED ?? 0} sub="nothing changed" />
          </section>
          <Section title="Recent agent activity">
            {recent.loading ? <LoadingRows rows={4} /> : <ul className="space-y-2">{recent.data?.slice(0, 8).map((a) => <ActionRow key={a.id} a={a} />)}</ul>}
          </Section>
        </>
      )}

      {tab === "approvals" && (
        approvals.loading ? <LoadingRows rows={3} /> : !approvals.data?.length ? (
          <EmptyState icon={<CheckCircle2 className="h-6 w-6" />} title="Nothing waiting for you" body="Agent actions that need approval from one of your roles appear here." />
        ) : <ul className="space-y-2" data-testid="action-approvals">{approvals.data.map((a) => <ActionRow key={a.id} a={a} />)}</ul>
      )}

      {tab === "activity" && admin && (
        <>
          <Select aria-label="Status" className="mb-4 w-auto min-w-[200px]" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>{["EXECUTED", "PENDING_APPROVAL", "IN_REVIEW", "ESCALATED", "NEEDS_INFO", "BLOCKED", "REJECTED", "FAILED", "COMPENSATED"].map((x) => <option key={x} value={x}>{humanize(x.toLowerCase())}</option>)}
          </Select>
          {recent.error && <ErrorState message={recent.error.message} onRetry={recent.reload} />}
          {recent.loading ? <LoadingRows rows={6} /> : !recent.data?.length ? <EmptyState title="No actions match" /> : <ul className="space-y-2">{recent.data.map((a) => <ActionRow key={a.id} a={a} />)}</ul>}
        </>
      )}

      {tab === "catalog" && admin && (
        !catalog.data ? <LoadingRows rows={5} /> : (
          <div className="grid gap-6 xl:grid-cols-[1fr_1.3fr]">
            <Section title="Connected agents">
              <ul className="space-y-3">
                {catalog.data.agents.map((a) => (
                  <li key={a.id} className="rounded-2xl border border-hair bg-white/50 p-4">
                    <p className="flex items-center gap-2 font-medium"><Bot className="h-4 w-4 text-forest" />{a.name}<Badge tone={a.status === "active" ? "sage" : "neutral"}>{a.status}</Badge></p>
                    <p className="mt-1 text-[12.5px] text-ink-500">{a.description} · owned by {a.owner_team}</p>
                    <p className="mt-2 flex flex-wrap gap-1">{a.allowed_action_types.map((t) => <Badge key={t} className="font-mono">{t}</Badge>)}</p>
                  </li>
                ))}
              </ul>
            </Section>
            <Section title="Action catalog">
              <table className="w-full text-left text-[13px]">
                <thead className="border-b border-hair text-[12px] text-ink-500"><tr><th className="py-2 font-medium">Action</th><th className="font-medium">Category</th><th className="font-medium">Requires</th></tr></thead>
                <tbody>{catalog.data.action_types.map((t) => (
                  <tr key={t.id} className="border-b border-hair align-top last:border-0">
                    <td className="py-2.5 pr-3"><p className="font-medium">{t.name}</p><p className="text-[12px] text-ink-500">{t.target_system} · <span className="font-mono">{t.key}</span></p></td>
                    <td className="py-2.5 pr-3"><Badge>{humanize(t.category.toLowerCase())}</Badge></td>
                    <td className="py-2.5 font-mono text-[12px] text-ink-700">{t.required_permission ?? "—"}</td>
                  </tr>))}</tbody>
              </table>
            </Section>
          </div>
        )
      )}

      {tab === "rules" && admin && (
        <Section title="Approval rules" description="The most restrictive matching rule wins: Block › Escalate › Require approval › Review › Execute."
          actions={manage && <Button size="sm" onClick={() => openEdit("new")}><Plus className="h-4 w-4" />New rule</Button>}>
          {!rules.data ? <LoadingRows rows={6} /> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-left text-[13px]" data-testid="action-rules">
                <thead className="border-b border-hair text-[12px] text-ink-500"><tr><th className="py-2 font-medium">Rule</th><th className="font-medium">Applies to</th><th className="font-medium">When</th><th className="font-medium">Decision</th><th className="font-medium">Approver</th><th className="text-right font-medium">Active</th></tr></thead>
                <tbody>{rules.data.map((p) => (
                  <tr key={p.id} className="border-b border-hair align-top last:border-0">
                    <td className="py-3 pr-3"><p className="font-medium">{p.name}</p>{p.description && <p className="text-[12px] text-ink-500">{p.description}</p>}</td>
                    <td className="py-3 pr-3 font-mono text-[12px]">{p.action_type ?? humanize((p.category ?? "").toLowerCase())}</td>
                    <td className="py-3 pr-3 text-ink-700">{COND_LABEL(p.conditions)}</td>
                    <td className="py-3 pr-3"><ActionBadge action={p.decision} /></td>
                    <td className="py-3 pr-3">{p.approver_role ? ROLE_LABELS[p.approver_role] ?? p.approver_role : "—"}</td>
                    <td className="py-3 text-right"><span className="inline-flex items-center gap-2">
                      {manage && <button onClick={() => openEdit(p)} className="rounded-full p-1.5 text-ink-400 hover:bg-ink/5 hover:text-ink" aria-label={`Edit ${p.name}`}><Pencil className="h-3.5 w-3.5" /></button>}
                      <Switch checked={p.is_active} onChange={() => void toggle(p)} label={`${p.name} active`} disabled={!manage} /></span></td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
        </Section>
      )}

      <Dialog open={editing !== null} onClose={() => setEditing(null)} title={editing === "new" ? "New approval rule" : "Edit approval rule"} description="Changes are audited and apply to new requests only.">
        <form onSubmit={save} className="space-y-4">
          {editing === "new" && <Field label="Name" htmlFor="ar-name"><Input id="ar-name" required minLength={3} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>}
          <Field label="Description" htmlFor="ar-desc"><Textarea id="ar-desc" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          {editing === "new" && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Scope" htmlFor="ar-scope"><Select id="ar-scope" value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })}><option value="category">Category</option><option value="action">Specific action</option></Select></Field>
              {form.scope === "category" ? (
                <Field label="Category" htmlFor="ar-cat"><Select id="ar-cat" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{catalog.data?.categories.map((c) => <option key={c} value={c}>{humanize(c.toLowerCase())}</option>)}</Select></Field>
              ) : (
                <Field label="Action" htmlFor="ar-act"><Select id="ar-act" required value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })}><option value="">Choose</option>{catalog.data?.action_types.map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}</Select></Field>
              )}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount above (INR)" htmlFor="ar-gt"><Input id="ar-gt" type="number" min={0} value={form.amount_gt} onChange={(e) => setForm({ ...form, amount_gt: e.target.value })} /></Field>
            <Field label="Amount up to (INR)" htmlFor="ar-lte"><Input id="ar-lte" type="number" min={0} value={form.amount_lte} onChange={(e) => setForm({ ...form, amount_lte: e.target.value })} /></Field>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Decision" htmlFor="ar-dec"><Select id="ar-dec" value={form.decision} onChange={(e) => setForm({ ...form, decision: e.target.value })}>{["EXECUTE", "REQUIRE_APPROVAL", "SEND_TO_REVIEW", "ESCALATE", "BLOCK"].map((d) => <option key={d} value={d}>{humanize(d.toLowerCase())}</option>)}</Select></Field>
            <Field label="Approver" htmlFor="ar-role"><Select id="ar-role" value={form.approver_role} disabled={!["REQUIRE_APPROVAL", "SEND_TO_REVIEW", "ESCALATE"].includes(form.decision)} onChange={(e) => setForm({ ...form, approver_role: e.target.value })}>
              {APPROVER_ROLES.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</Select></Field>
            <Field label="Priority" htmlFor="ar-pri"><Input id="ar-pri" type="number" min={0} max={100} value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} /></Field>
          </div>
          {error && <ErrorState message={error} />}
          <Button type="submit" className="w-full">{editing === "new" ? "Create rule" : "Save rule"}</Button>
        </form>
      </Dialog>
    </>
  );
}
