"use client";

import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Switch } from "@/components/ui/field";
import { ENTITY_LABELS, humanize, ROLE_LABELS } from "@/lib/format";
import type { Catalogue, Rule } from "@/lib/types";

export const EMPTY_RULE: Rule = {
  name: "", rule_type: "keyword", match_field: "user_input", pattern: null, keywords: [], entity_types: [], topic: null,
  required_permission: null, threshold: null, action: null, severity: null, applies_to_roles: [], is_active: true,
};

const RULE_HELP: Record<string, string> = {
  regex: "Triggers when the pattern matches (case-insensitive).",
  keyword: "Triggers when any keyword appears as a whole word.",
  pii_entity: "Triggers when Presidio or a custom recognizer detects one of these entity types.",
  topic: "Triggers when the topic classifier scores at or above the threshold.",
  role_permission: "Triggers when the topic/entity is present AND the user lacks the permission scope.",
  confidence_threshold: "Triggers when grounding confidence is below the threshold (output only).",
};

const DATA_SCOPES = ["data:compensation", "data:financial"];

function MultiChips({ options, value, onChange, labels }: { options: string[]; value: string[]; onChange: (v: string[]) => void; labels?: Record<string, string> }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button key={o} type="button" aria-pressed={on} onClick={() => onChange(on ? value.filter((x) => x !== o) : [...value, o])}
            className={`rounded-full border px-2.5 py-1 text-[12px] transition ${on ? "border-forest bg-forest text-cream" : "border-hair bg-white/60 text-ink-700 hover:border-forest/40"}`}>
            {labels?.[o] ?? humanize(o)}
          </button>
        );
      })}
    </div>
  );
}

export function RuleEditor({ rule, index, catalogue, onChange, onRemove, readOnly }: {
  rule: Rule; index: number; catalogue: Catalogue; onChange: (r: Rule) => void; onRemove: () => void; readOnly?: boolean;
}) {
  const set = <K extends keyof Rule>(k: K, v: Rule[K]) => onChange({ ...rule, [k]: v });
  const id = (s: string) => `rule-${index}-${s}`;
  return (
    <fieldset disabled={readOnly} className="rounded-2xl border border-hair bg-white/50 p-4">
      <legend className="sr-only">Rule {index + 1}</legend>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="font-serif text-[17px]">Rule {index + 1}</p>
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-ink-500">Active</span>
          <Switch checked={rule.is_active} onChange={(v) => set("is_active", v)} label={`Rule ${index + 1} active`} disabled={readOnly} />
          {!readOnly && <button type="button" onClick={onRemove} className="rounded-full p-1.5 text-ink-400 hover:bg-crimson-100 hover:text-crimson" aria-label={`Remove rule ${index + 1}`}><Trash2 className="h-4 w-4" /></button>}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Name" htmlFor={id("name")} className="sm:col-span-3"><Input id={id("name")} value={rule.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Salary request without scope" /></Field>
        <Field label="Rule type" htmlFor={id("type")}>
          <Select id={id("type")} value={rule.rule_type} onChange={(e) => onChange({ ...rule, rule_type: e.target.value as Rule["rule_type"], match_field: e.target.value === "confidence_threshold" ? "llm_output" : rule.match_field })}>
            {catalogue.rule_types.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
          </Select>
        </Field>
        <Field label="Match field" htmlFor={id("field")}>
          <Select id={id("field")} value={rule.match_field} onChange={(e) => set("match_field", e.target.value as Rule["match_field"])} disabled={rule.rule_type === "confidence_threshold"}>
            {catalogue.match_fields.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
          </Select>
        </Field>
        <Field label="Threshold" htmlFor={id("thr")} hint="Blank = policy default">
          <Input id={id("thr")} type="number" min={0} max={1} step={0.05} value={rule.threshold ?? ""} onChange={(e) => set("threshold", e.target.value === "" ? null : Number(e.target.value))} />
        </Field>
      </div>
      <p className="mt-2 text-[12px] text-ink-500">{RULE_HELP[rule.rule_type]}</p>

      <div className="mt-3 space-y-3">
        {rule.rule_type === "regex" && (
          <Field label="Pattern" htmlFor={id("pattern")}><Input id={id("pattern")} className="font-mono text-[13px]" value={rule.pattern ?? ""} onChange={(e) => set("pattern", e.target.value)} placeholder="\bacme\s+corp\b" /></Field>
        )}
        {rule.rule_type === "keyword" && (
          <Field label="Keywords" htmlFor={id("kw")} hint="Comma-separated">
            <Input id={id("kw")} value={rule.keywords.join(", ")} onChange={(e) => set("keywords", e.target.value.split(",").map((k) => k.trim()).filter(Boolean))} />
          </Field>
        )}
        {(rule.rule_type === "pii_entity" || rule.rule_type === "role_permission") && (
          <Field label={rule.rule_type === "role_permission" ? "Entity types (or use a topic)" : "Entity types"}>
            <MultiChips options={catalogue.entity_types} value={rule.entity_types} onChange={(v) => set("entity_types", v)} labels={ENTITY_LABELS} />
          </Field>
        )}
        {(rule.rule_type === "topic" || rule.rule_type === "role_permission") && (
          <Field label="Topic" htmlFor={id("topic")}>
            <Select id={id("topic")} value={rule.topic ?? ""} onChange={(e) => set("topic", e.target.value || null)}>
              <option value="">—</option>
              {catalogue.topics.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
            </Select>
          </Field>
        )}
        {rule.rule_type === "role_permission" && (
          <Field label="Required permission scope" htmlFor={id("perm")}>
            <Select id={id("perm")} value={rule.required_permission ?? ""} onChange={(e) => set("required_permission", e.target.value || null)}>
              <option value="">—</option>
              {DATA_SCOPES.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
          </Field>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Action override" htmlFor={id("action")}>
            <Select id={id("action")} value={rule.action ?? ""} onChange={(e) => set("action", (e.target.value || null) as Rule["action"])}>
              <option value="">Inherit from policy</option>
              {catalogue.actions.map((a) => <option key={a} value={a}>{a}</option>)}
            </Select>
          </Field>
          <Field label="Severity override" htmlFor={id("sev")}>
            <Select id={id("sev")} value={rule.severity ?? ""} onChange={(e) => set("severity", (e.target.value || null) as Rule["severity"])}>
              <option value="">Inherit from policy</option>
              {catalogue.severities.map((a) => <option key={a} value={a}>{humanize(a.toLowerCase())}</option>)}
            </Select>
          </Field>
        </div>
        <Field label="Applies to roles" hint="None selected = all roles">
          <MultiChips options={Object.keys(ROLE_LABELS)} value={rule.applies_to_roles} onChange={(v) => set("applies_to_roles", v)} labels={ROLE_LABELS} />
        </Field>
      </div>
    </fieldset>
  );
}

export function AddRuleButton({ onAdd }: { onAdd: () => void }) {
  return <Button type="button" variant="secondary" size="sm" onClick={onAdd}><Plus className="h-4 w-4" />Add rule</Button>;
}

export { MultiChips };
