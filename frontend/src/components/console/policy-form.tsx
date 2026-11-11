"use client";

import { AddRuleButton, EMPTY_RULE, MultiChips, RuleEditor } from "@/components/console/rule-builder";
import { Section } from "@/components/console/shell";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { humanize, PROFILE_LABELS, ROLE_LABELS } from "@/lib/format";
import type { Catalogue, PolicyDefinition } from "@/lib/types";

export const BLANK_DEFINITION: PolicyDefinition = {
  name: "", description: "", risk_category: "", sensitive_data_type: "none", owner: "", review_cadence_days: 180,
  effective_from: null, effective_to: null, applicable_roles: [], profiles: [], action: "BLOCK", severity: "MEDIUM",
  threshold: 0.5, user_message: "", rules: [{ ...EMPTY_RULE }],
};

const toLocal = (iso: string | null) => (iso ? iso.slice(0, 10) : "");
const fromLocal = (v: string) => (v ? `${v}T00:00:00` : null);

/** Policy definition editor: every field a version snapshot captures. */
export function PolicyForm({ value, onChange, catalogue, readOnly }: {
  value: PolicyDefinition; onChange: (d: PolicyDefinition) => void; catalogue: Catalogue; readOnly?: boolean;
}) {
  const set = <K extends keyof PolicyDefinition>(k: K, v: PolicyDefinition[K]) => onChange({ ...value, [k]: v });
  return (
    <fieldset disabled={readOnly} className="space-y-6">
      <Section title="Definition">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Policy name" htmlFor="p-name" className="sm:col-span-2"><Input id="p-name" required minLength={3} value={value.name} onChange={(e) => set("name", e.target.value)} /></Field>
          <Field label="Description" htmlFor="p-desc" className="sm:col-span-2"><Textarea id="p-desc" rows={2} value={value.description} onChange={(e) => set("description", e.target.value)} /></Field>
          <Field label="Risk category" htmlFor="p-cat"><Input id="p-cat" required value={value.risk_category} onChange={(e) => set("risk_category", e.target.value)} placeholder="e.g. compensation" /></Field>
          <Field label="Policy owner" htmlFor="p-owner"><Input id="p-owner" value={value.owner} onChange={(e) => set("owner", e.target.value)} placeholder="e.g. Privacy Office" /></Field>
          <Field label="Effective from" htmlFor="p-from" hint="Blank = as soon as it is activated"><Input id="p-from" type="date" value={toLocal(value.effective_from)} onChange={(e) => set("effective_from", fromLocal(e.target.value))} /></Field>
          <Field label="Effective until" htmlFor="p-to" hint="Optional end date"><Input id="p-to" type="date" value={toLocal(value.effective_to)} onChange={(e) => set("effective_to", fromLocal(e.target.value))} /></Field>
          <Field label="Review cadence" htmlFor="p-cadence">
            <Select id="p-cadence" value={value.review_cadence_days} onChange={(e) => set("review_cadence_days", Number(e.target.value))}>
              {[30, 90, 180, 365].map((d) => <option key={d} value={d}>Every {d} days</option>)}
            </Select>
          </Field>
          <Field label="Sensitive data type" htmlFor="p-type"><Input id="p-type" value={value.sensitive_data_type} onChange={(e) => set("sensitive_data_type", e.target.value)} /></Field>
          <Field label="Default action" htmlFor="p-action">
            <Select id="p-action" value={value.action} onChange={(e) => set("action", e.target.value as PolicyDefinition["action"])}>
              {catalogue.actions.map((a) => <option key={a}>{a}</option>)}
            </Select>
          </Field>
          <Field label="Severity" htmlFor="p-sev">
            <Select id="p-sev" value={value.severity} onChange={(e) => set("severity", e.target.value as PolicyDefinition["severity"])}>
              {catalogue.severities.map((a) => <option key={a}>{a}</option>)}
            </Select>
          </Field>
          <Field label="Confidence threshold" htmlFor="p-thr" hint="Default for rules that don't set their own (0–1).">
            <Input id="p-thr" type="number" min={0} max={1} step={0.05} value={value.threshold} onChange={(e) => set("threshold", Number(e.target.value))} />
          </Field>
          <Field label="Message shown to employees" htmlFor="p-msg" className="sm:col-span-2" hint="Plain language. Shown in the “Why was this blocked?” panel.">
            <Textarea id="p-msg" rows={2} value={value.user_message} onChange={(e) => set("user_message", e.target.value)} />
          </Field>
          <Field label="Applicable roles" className="sm:col-span-2" hint="None selected = applies to everyone">
            <MultiChips options={Object.keys(ROLE_LABELS)} value={value.applicable_roles} onChange={(v) => set("applicable_roles", v)} labels={ROLE_LABELS} />
          </Field>
          <Field label="Channel policy profiles" className="sm:col-span-2" hint="Scope this policy to workspace channels using these profiles. None selected = everywhere.">
            <MultiChips options={catalogue.profiles} value={value.profiles} onChange={(v) => set("profiles", v)} labels={PROFILE_LABELS} />
          </Field>
        </div>
      </Section>
      <Section title="Rules" description="The policy triggers when any active rule matches."
        actions={!readOnly && <AddRuleButton onAdd={() => set("rules", [...value.rules, { ...EMPTY_RULE }])} />}>
        <div className="space-y-3">
          {value.rules.map((r, i) => (
            <RuleEditor key={r.key ?? i} index={i} rule={r} catalogue={catalogue} readOnly={readOnly}
              onChange={(nr) => set("rules", value.rules.map((x, j) => (j === i ? nr : x)))}
              onRemove={() => set("rules", value.rules.filter((_, j) => j !== i))} />
          ))}
        </div>
      </Section>
    </fieldset>
  );
}

export function cleanDefinition(d: PolicyDefinition): PolicyDefinition {
  return { ...d, rules: d.rules.map(({ id: _id, ...r }) => ({ ...r, name: r.name || humanize(r.rule_type) })) };
}

export { humanize };
