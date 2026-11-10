"use client";

import { ArrowRight, CircleSlash } from "lucide-react";

import { ActionBadge, ScoreBar, SeverityBadge, TrustBadge } from "@/components/trust/badges";
import { ENTITY_LABELS, humanize } from "@/lib/format";
import type { RuleMatch, SimulationResult, StageOut } from "@/lib/types";
import { cn } from "@/lib/utils";

function Matches({ matches, focusId }: { matches: RuleMatch[]; focusId?: number }) {
  if (!matches.length) return <p className="text-[12.5px] text-ink-500">No rules triggered.</p>;
  return (
    <ul className="space-y-2">
      {matches.map((m, i) => (
        <li key={i} className={cn("rounded-xl border px-3 py-2.5 text-[12.5px]", m.policy_id === focusId ? "border-forest bg-forest-50" : "border-hair bg-white/60")}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-ink">{m.policy_name}</span>
            <span className="text-ink-400">›</span>
            <span className="text-ink-700">{m.rule_name}</span>
            <span className="ml-auto flex gap-1.5"><SeverityBadge severity={m.severity} /><ActionBadge action={m.action} /></span>
          </div>
          <p className="mt-1 font-mono text-[11.5px] text-ink-500">{m.rule_type} · {m.match_field} · {m.evidence}</p>
        </li>
      ))}
    </ul>
  );
}

function StageCard({ title, stage, focusId, children }: { title: string; stage: StageOut | null; focusId?: number; children?: React.ReactNode }) {
  if (!stage) {
    return (
      <div className="rounded-2xl border border-dashed border-ink/15 p-4">
        <p className="eyebrow">{title}</p>
        <p className="mt-2 flex items-center gap-2 text-[13px] text-ink-500"><CircleSlash className="h-4 w-4" />Not reached — the request stopped earlier.</p>
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-hair bg-cream-50 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="eyebrow">{title}</p>
        <div className="flex items-center gap-2 text-[11.5px] text-ink-500">
          <span className="num">risk {stage.risk_score.toFixed(2)}</span>
          <span className="num">· {stage.latency_ms.toFixed(0)}ms</span>
          <ActionBadge action={stage.action} />
        </div>
      </div>
      {children}
      <Matches matches={stage.matches} focusId={focusId} />
    </div>
  );
}

export function SimulationView({ result }: { result: SimulationResult }) {
  const inp = result.input;
  const topics = Object.entries((inp?.signals.topics ?? {}) as Record<string, { score: number; signals: string[] }>);
  const entities = (inp?.signals.entities ?? []) as { entity_type: string; score: number; masked: string; source: string }[];
  const grounding = result.output?.signals.grounding as Record<string, number | string[] | string> | undefined;
  const f = result.final;
  return (
    <div className="space-y-4 animate-rise" data-testid="simulation-result">
      <div className="rounded-2xl border border-forest/25 bg-white/70 p-5">
        <p className="eyebrow">Outcome for {humanize(result.role)}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <ActionBadge action={f.input_action} />
          <ArrowRight className="h-4 w-4 text-ink-300" />
          <ActionBadge action={f.output_action ?? "—"} />
          {f.trust_status && <TrustBadge status={f.trust_status} />}
          <span className="ml-auto text-[12.5px] text-ink-500">{f.llm_called ? "Model was called" : "Model was not called"}</span>
        </div>
        {result.focus_policy && (
          <p className={cn("mt-3 rounded-lg px-3 py-2 text-[13px]", result.focus_policy.triggered ? "bg-forest-50 text-forest" : "bg-ink/[0.04] text-ink-700")} data-testid="focus-result">
            {result.focus_policy.triggered ? `“${result.focus_policy.name}” triggered ${result.focus_policy.matches.length} rule(s).` : `“${result.focus_policy.name}” did not trigger for this prompt and role.`}
          </p>
        )}
        {f.response_preview && (
          <div className="mt-4 border-t border-hair pt-3">
            <p className="eyebrow mb-1.5">What the employee would see</p>
            <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-700">{f.response_preview}</p>
          </div>
        )}
      </div>

      <StageCard title="1 · Input guardrails" stage={inp} focusId={result.focus_policy?.id}>
        {(entities.length > 0 || topics.length > 0) && (
          <div className="mb-3 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1.5 text-[12px] font-medium text-ink-700">Detected entities</p>
              {entities.length ? (
                <ul className="space-y-1 text-[12px]">
                  {entities.map((e, i) => (
                    <li key={i} className="flex justify-between gap-2"><span>{ENTITY_LABELS[e.entity_type] ?? e.entity_type} <span className="font-mono text-ink-500">{e.masked}</span></span><span className="num text-ink-500">{e.score.toFixed(2)} · {e.source}</span></li>
                  ))}
                </ul>
              ) : <p className="text-[12px] text-ink-500">None</p>}
            </div>
            <div>
              <p className="mb-1.5 text-[12px] font-medium text-ink-700">Topic scores</p>
              <div className="space-y-1.5">
                {topics.length ? topics.map(([k, v]) => (
                  <div key={k} className="text-[12px]"><span className="text-ink-700">{humanize(k)}</span><ScoreBar value={v.score} tone={v.score >= 0.6 ? "crimson" : v.score >= 0.4 ? "amber" : "forest"} label={k} /></div>
                )) : <p className="text-[12px] text-ink-500">No sensitive topics</p>}
              </div>
            </div>
          </div>
        )}
        {result.sanitized_prompt && inp && inp.redaction_count > 0 && (
          <p className="mb-3 rounded-lg bg-lilac-200 px-3 py-2 font-mono text-[12px] text-ink-700">Sent to model: {result.sanitized_prompt}</p>
        )}
      </StageCard>
      <StageCard title="2 · Retrieved context" stage={result.context} focusId={result.focus_policy?.id}>
        {result.context && <p className="mb-3 text-[12.5px] text-ink-500">{result.context.signals.retrieved} chunk(s) retrieved · {result.context.signals.quarantined} quarantined · {result.context.signals.masked_values ?? 0} value(s) masked</p>}
      </StageCard>
      <StageCard title="3 · Output validation" stage={result.output} focusId={result.focus_policy?.id}>
        {grounding && (
          <div className="mb-3 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
            {["confidence", "groundedness", "semantic_similarity", "lexical_support", "citation_presence", "query_support"].map((k) => (
              <div key={k} className="text-[12px]"><span className="text-ink-700">{humanize(k)}</span><ScoreBar value={Number(grounding[k] ?? 0)} label={k} /></div>
            ))}
            <p className="text-[11.5px] text-ink-500 sm:col-span-2">Grounding scores are a risk signal, not a guarantee of correctness.</p>
          </div>
        )}
      </StageCard>
    </div>
  );
}
