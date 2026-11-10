"use client";

import { ArrowLeft, FlaskConical, History } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { AddRuleButton, EMPTY_RULE, MultiChips, RuleEditor } from "@/components/console/rule-builder";
import { PageHeader, Section } from "@/components/console/shell";
import { SimulationView } from "@/components/console/simulation-view";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Switch, Textarea } from "@/components/ui/field";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { dateTime, humanize, ROLE_LABELS } from "@/lib/format";
import type { Catalogue, Policy, PolicyVersion, SimulationResult } from "@/lib/types";

type Draft = Omit<Policy, "id" | "version" | "created_at" | "updated_at">;

const BLANK: Draft = {
  name: "", description: "", risk_category: "", sensitive_data_type: "none", applicable_roles: [], action: "BLOCK", severity: "MEDIUM",
  threshold: 0.5, user_message: "", is_active: false, rules: [{ ...EMPTY_RULE }],
};

function cleanRules(rules: Draft["rules"]) {
  return rules.map(({ id: _id, ...r }) => ({ ...r, name: r.name || humanize(r.rule_type) }));
}

export default function PolicyEditorPage() {
  const { id } = useParams<{ id: string }>();
  const isNew = id === "new";
  const router = useRouter();
  const { can } = useAuth();
  const writable = can("policies:write");
  const policy = useApi<Policy>(isNew ? null : `/admin/policies/${id}`);
  const catalogue = useApi<Catalogue>("/admin/policies/catalogue");
  const versions = useApi<PolicyVersion[]>(isNew ? null : `/admin/policies/${id}/versions`);
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [summary, setSummary] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState(false);
  const [simPrompt, setSimPrompt] = useState("");
  const [simRole, setSimRole] = useState("employee");
  const [sim, setSim] = useState<SimulationResult | null>(null);
  const [simBusy, setSimBusy] = useState(false);

  useEffect(() => {
    if (policy.data) {
      const { id: _i, version: _v, created_at: _c, updated_at: _u, ...rest } = policy.data;
      setDraft(rest);
    }
  }, [policy.data]);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => { setDraft((d) => ({ ...d, [k]: v })); setSaved(false); };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const body = { ...draft, rules: cleanRules(draft.rules) };
      if (isNew) {
        const created = await api<Policy>("/admin/policies", { method: "POST", body });
        router.replace(`/console/policies/${created.id}`);
      } else {
        const updated = await api<Policy>(`/admin/policies/${id}`, { method: "PATCH", body: { ...body, change_summary: summary } });
        policy.setData(updated);
        setSummary("");
        setSaved(true);
        void versions.reload();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "error", "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  const archive = async () => {
    if (!window.confirm("Archive this policy? It stops being enforced; its history stays in the audit log.")) return;
    await api(`/admin/policies/${id}`, { method: "DELETE" });
    router.replace("/console/policies");
  };

  const simulate = async () => {
    if (!simPrompt.trim()) return;
    setSimBusy(true);
    setError(null);
    try {
      const res = isNew
        ? await api<SimulationResult>("/admin/simulate", { method: "POST", body: { prompt: simPrompt, role: simRole, draft_policy: { ...draft, rules: cleanRules(draft.rules) } } })
        : await api<SimulationResult>(`/admin/policies/${id}/simulate`, { method: "POST", body: { prompt: simPrompt, role: simRole } });
      setSim(res);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "error", "Simulation failed"));
    } finally {
      setSimBusy(false);
    }
  };

  if ((!isNew && policy.loading) || !catalogue.data) return <LoadingRows rows={6} />;
  if (policy.error) return <ErrorState message={policy.error.message} onRetry={policy.reload} />;

  return (
    <>
      <Link href="/console/policies" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-ink-500 hover:text-ink"><ArrowLeft className="h-3.5 w-3.5" />All policies</Link>
      <PageHeader
        eyebrow={isNew ? "New policy" : `Policy · v${policy.data?.version}`}
        title={isNew ? "Create a policy" : draft.name || "Policy"}
        description={isNew ? "Define what to detect and what TrustShield should do. New policies start inactive so you can test them first." : draft.description}
        actions={!isNew && writable && <Button variant="ghost" onClick={() => void archive()}>Archive</Button>}
      />
      <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <form onSubmit={save} className="space-y-6" aria-label="Policy editor">
          <fieldset disabled={!writable} className="space-y-6">
            <Section title="Definition">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Policy name" htmlFor="p-name" className="sm:col-span-2"><Input id="p-name" required minLength={3} value={draft.name} onChange={(e) => set("name", e.target.value)} /></Field>
                <Field label="Description" htmlFor="p-desc" className="sm:col-span-2"><Textarea id="p-desc" rows={2} value={draft.description} onChange={(e) => set("description", e.target.value)} /></Field>
                <Field label="Risk category" htmlFor="p-cat"><Input id="p-cat" required value={draft.risk_category} onChange={(e) => set("risk_category", e.target.value)} placeholder="e.g. compensation" /></Field>
                <Field label="Sensitive data type" htmlFor="p-type"><Input id="p-type" value={draft.sensitive_data_type} onChange={(e) => set("sensitive_data_type", e.target.value)} /></Field>
                <Field label="Default action" htmlFor="p-action">
                  <Select id="p-action" value={draft.action} onChange={(e) => set("action", e.target.value as Draft["action"])}>
                    {catalogue.data.actions.map((a) => <option key={a}>{a}</option>)}
                  </Select>
                </Field>
                <Field label="Severity" htmlFor="p-sev">
                  <Select id="p-sev" value={draft.severity} onChange={(e) => set("severity", e.target.value as Draft["severity"])}>
                    {catalogue.data.severities.map((a) => <option key={a}>{a}</option>)}
                  </Select>
                </Field>
                <Field label="Default threshold" htmlFor="p-thr" hint="Used by rules that don't set their own (0–1).">
                  <Input id="p-thr" type="number" min={0} max={1} step={0.05} value={draft.threshold} onChange={(e) => set("threshold", Number(e.target.value))} />
                </Field>
                <div className="flex items-center gap-3 pt-6">
                  <Switch checked={draft.is_active} onChange={(v) => set("is_active", v)} label="Policy active" disabled={!writable} />
                  <span className="text-[13.5px]">{draft.is_active ? "Active — enforced on live traffic" : "Inactive — simulator only"}</span>
                </div>
                <Field label="Message shown to employees" htmlFor="p-msg" className="sm:col-span-2" hint="Plain language. Shown in the “Why was this blocked?” panel.">
                  <Textarea id="p-msg" rows={2} value={draft.user_message} onChange={(e) => set("user_message", e.target.value)} />
                </Field>
                <Field label="Applicable roles" className="sm:col-span-2" hint="None selected = applies to everyone">
                  <MultiChips options={Object.keys(ROLE_LABELS)} value={draft.applicable_roles} onChange={(v) => set("applicable_roles", v)} labels={ROLE_LABELS} />
                </Field>
              </div>
            </Section>
            <Section title="Rules" description="A policy triggers when any active rule matches." actions={writable && <AddRuleButton onAdd={() => set("rules", [...draft.rules, { ...EMPTY_RULE }])} />}>
              <div className="space-y-3">
                {draft.rules.map((r, i) => (
                  <RuleEditor key={i} index={i} rule={r} catalogue={catalogue.data!} readOnly={!writable}
                    onChange={(nr) => set("rules", draft.rules.map((x, j) => (j === i ? nr : x)))}
                    onRemove={() => set("rules", draft.rules.filter((_, j) => j !== i))} />
                ))}
              </div>
            </Section>
          </fieldset>
          {error && <ErrorState message={error.message + (error.details ? ` — ${JSON.stringify(error.details).slice(0, 200)}` : "")} requestId={error.requestId} />}
          {writable && (
            <div className="sticky bottom-4 flex flex-wrap items-center gap-3 rounded-2xl border border-hair bg-cream/95 p-3 shadow-soft backdrop-blur">
              {!isNew && <Input aria-label="Change summary" placeholder="Change summary (recorded in version history)" className="min-w-[200px] flex-1" value={summary} onChange={(e) => setSummary(e.target.value)} />}
              <Button type="submit" loading={saving}>{isNew ? "Create policy" : "Save new version"}</Button>
              {saved && <span role="status" className="text-[13px] text-forest">Saved as v{policy.data?.version}</span>}
            </div>
          )}
        </form>

        <div className="space-y-6">
          <Section title="Test this policy" description={isNew ? "Runs your unsaved draft alongside the live policies." : "Runs with this policy forced active, even if it's off."}>
            <div className="space-y-3">
              <Textarea aria-label="Sample prompt" rows={3} placeholder="Paste a sample employee prompt…" value={simPrompt} onChange={(e) => setSimPrompt(e.target.value)} data-testid="policy-sim-prompt" />
              <div className="flex gap-2">
                <Select aria-label="Simulated role" value={simRole} onChange={(e) => setSimRole(e.target.value)} className="flex-1">
                  {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
                <Button type="button" onClick={() => void simulate()} loading={simBusy} disabled={!simPrompt.trim()}><FlaskConical className="h-4 w-4" />Run</Button>
              </div>
            </div>
            {sim && <div className="mt-4"><SimulationView result={sim} /></div>}
          </Section>
          {!isNew && (
            <Section title="Version history" actions={<History className="h-4 w-4 text-ink-400" />}>
              <ol className="space-y-3">
                {versions.data?.map((v) => (
                  <li key={v.id} className="flex gap-3 text-[13px]">
                    <span className="num font-serif text-[18px] leading-none text-forest">v{v.version}</span>
                    <div><p className="text-ink">{v.change_summary || "Updated"}</p><p className="text-[12px] text-ink-500">{dateTime(v.created_at)}</p></div>
                  </li>
                ))}
              </ol>
            </Section>
          )}
        </div>
      </div>
    </>
  );
}
