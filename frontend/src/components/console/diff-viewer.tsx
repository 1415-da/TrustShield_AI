import { Minus, Plus, RefreshCw } from "lucide-react";

import { humanize, PROFILE_LABELS, ROLE_LABELS } from "@/lib/format";
import type { FieldChange, PolicyDiff, Rule } from "@/lib/types";
import { cn } from "@/lib/utils";

function fmt(field: string, v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) {
    if (!v.length) return field.includes("roles") || field === "profiles" ? "all" : "none";
    const labels = field.includes("roles") ? ROLE_LABELS : field === "profiles" ? PROFILE_LABELS : {};
    return v.map((x) => labels[String(x)] ?? String(x)).join(", ");
  }
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (field.startsWith("effective") && typeof v === "string") return v.slice(0, 10);
  return String(v);
}

const LABELS: Record<string, string> = { threshold: "Threshold", action: "Action", severity: "Severity", pattern: "Regex pattern",
  applies_to_roles: "Roles", applicable_roles: "Applicable roles", keywords: "Keywords", entity_types: "Entity types", is_active: "Active",
  match_field: "Match field", review_cadence_days: "Review cadence (days)", effective_from: "Effective from", effective_to: "Effective until",
  profiles: "Channel profiles", user_message: "Employee message" };

function ChangeRow({ c }: { c: FieldChange }) {
  return (
    <tr className="border-b border-hair last:border-0 align-top">
      <td className="py-2 pr-3 text-ink-700">{LABELS[c.field] ?? humanize(c.field)}</td>
      <td className="py-2 pr-3"><span className="rounded bg-crimson-100/70 px-1.5 py-0.5 font-mono text-[12px] text-crimson-700 line-through decoration-crimson/40">{fmt(c.field, c.before)}</span></td>
      <td className="py-2"><span className="rounded bg-sage-100 px-1.5 py-0.5 font-mono text-[12px] text-sage-700">{fmt(c.field, c.after)}</span></td>
    </tr>
  );
}

function RuleLine({ rule, tone }: { rule: Rule; tone: "add" | "remove" }) {
  const detail = rule.pattern ? `pattern ${rule.pattern}` : rule.keywords?.length ? `keywords ${rule.keywords.join(", ")}`
    : rule.entity_types?.length ? `entities ${rule.entity_types.join(", ")}` : rule.topic ? `topic ${rule.topic}` : rule.threshold !== null ? `threshold ${rule.threshold}` : "";
  return (
    <li className={cn("flex items-start gap-2 rounded-xl border px-3 py-2 text-[13px]", tone === "add" ? "border-sage/40 bg-sage-100/60" : "border-crimson/25 bg-crimson-100/50")}>
      {tone === "add" ? <Plus className="mt-0.5 h-3.5 w-3.5 text-sage-700" /> : <Minus className="mt-0.5 h-3.5 w-3.5 text-crimson" />}
      <div>
        <p className="font-medium">{rule.name || humanize(rule.rule_type)} <span className="font-normal text-ink-500">· {humanize(rule.rule_type)} on {humanize(rule.match_field)}{rule.action ? ` → ${rule.action}` : ""}</span></p>
        {detail && <p className="font-mono text-[11.5px] text-ink-700">{detail}</p>}
      </div>
    </li>
  );
}

export function DiffViewer({ diff, baseLabel, targetLabel, isNew }: { diff: PolicyDiff; baseLabel: string; targetLabel: string; isNew?: boolean }) {
  if (!diff.has_changes) return <p className="text-[13px] text-ink-500">No differences between {baseLabel} and {targetLabel}.</p>;
  if (isNew) {
    return (
      <div className="space-y-5" data-testid="policy-diff">
        <dl className="grid gap-x-6 gap-y-2.5 text-[13px] sm:grid-cols-2">
          {diff.fields.filter((c) => c.after !== null && c.after !== "").map((c) => (
            <div key={c.field}><dt className="text-[11.5px] text-ink-500">{LABELS[c.field] ?? humanize(c.field)}</dt><dd>{fmt(c.field, c.after)}</dd></div>
          ))}
        </dl>
        <div><p className="eyebrow mb-2">Rules added</p><ul className="space-y-1.5">{diff.rules_added.map((r, i) => <RuleLine key={i} rule={r} tone="add" />)}</ul></div>
      </div>
    );
  }
  return (
    <div className="space-y-5" data-testid="policy-diff">
      <p className="text-[12.5px] text-ink-500">Comparing <span className="font-medium text-ink">{targetLabel}</span> against <span className="font-medium text-ink">{baseLabel}</span></p>
      {diff.fields.length > 0 && (
        <div>
          <p className="eyebrow mb-2">Policy settings</p>
          <table className="w-full text-left text-[13px]"><tbody>{diff.fields.map((c) => <ChangeRow key={c.field} c={c} />)}</tbody></table>
        </div>
      )}
      {diff.rules_added.length > 0 && <div><p className="eyebrow mb-2">Rules added</p><ul className="space-y-1.5">{diff.rules_added.map((r, i) => <RuleLine key={i} rule={r} tone="add" />)}</ul></div>}
      {diff.rules_removed.length > 0 && <div><p className="eyebrow mb-2">Rules removed</p><ul className="space-y-1.5">{diff.rules_removed.map((r, i) => <RuleLine key={i} rule={r} tone="remove" />)}</ul></div>}
      {diff.rules_changed.length > 0 && (
        <div>
          <p className="eyebrow mb-2">Rules changed</p>
          <ul className="space-y-2">
            {diff.rules_changed.map((rc) => (
              <li key={rc.key} className="rounded-xl border border-amber/30 bg-amber-100/40 px-3 py-2">
                <p className="flex items-center gap-2 text-[13px] font-medium"><RefreshCw className="h-3.5 w-3.5 text-amber-700" />{rc.name}</p>
                <table className="mt-1 w-full text-left text-[12.5px]"><tbody>{rc.changes.map((c) => <ChangeRow key={c.field} c={c} />)}</tbody></table>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
