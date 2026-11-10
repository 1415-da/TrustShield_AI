import { ArrowDown, ArrowRight } from "lucide-react";

function Node({ title, sub, tone = "plain" }: { title: string; sub: string; tone?: "plain" | "dark" | "lilac" }) {
  const styles = {
    plain: "border-hair bg-cream-50",
    dark: "border-forest bg-forest text-cream",
    lilac: "border-lilac-400/70 bg-lilac-200",
  }[tone];
  return (
    <div className={`rounded-2xl border px-5 py-4 ${styles}`}>
      <p className="font-serif text-[19px] leading-tight">{title}</p>
      <p className={`mt-1 text-[12.5px] leading-snug ${tone === "dark" ? "text-cream/75" : "text-ink-500"}`}>{sub}</p>
    </div>
  );
}

const STAGES = [
  ["Input guardrails", "Injection scoring · Presidio PII · topic + role checks"],
  ["Policy engine", "Versioned rules from the database · ALLOW / REDACT / BLOCK / REVIEW / ESCALATE"],
  ["Output validation", "Leak detection · grounding risk signal · citation check"],
];

export function Architecture() {
  return (
    <section className="border-y border-hair bg-cream-50/60" aria-labelledby="arch-title">
      <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
        <div className="max-w-2xl">
          <p className="eyebrow">Architecture</p>
          <h2 id="arch-title" className="mt-3 text-[34px] leading-tight sm:text-[40px]">One control point, in both directions.</h2>
          <p className="mt-4 text-ink-700">Your assistant never calls a model directly. Every request and every answer passes through the gateway — and blocked requests never reach the model at all.</p>
        </div>

        <div className="mt-12 grid items-center gap-4 lg:grid-cols-[1fr_auto_1.6fr_auto_1fr]">
          <Node title="Employee apps" sub="Web assistant, Slack bot, internal tools — authenticated with JWT or app keys" />
          <ArrowRight className="mx-auto hidden h-5 w-5 text-ink-400 lg:block" aria-hidden />
          <ArrowDown className="mx-auto h-5 w-5 text-ink-400 lg:hidden" aria-hidden />
          <div className="rounded-[26px] border border-forest/20 bg-white/70 p-3 shadow-soft">
            <p className="eyebrow px-2 pb-2 pt-1 text-forest">TrustShield gateway</p>
            <div className="space-y-2">
              {STAGES.map(([t, s], i) => (
                <div key={t} className="flex items-start gap-3 rounded-2xl border border-hair bg-cream-50 px-4 py-3">
                  <span className="num mt-0.5 font-serif text-[18px] text-forest">0{i + 1}</span>
                  <div>
                    <p className="font-medium">{t}</p>
                    <p className="text-[12.5px] text-ink-500">{s}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <ArrowRight className="mx-auto hidden h-5 w-5 text-ink-400 lg:block" aria-hidden />
          <ArrowDown className="mx-auto h-5 w-5 text-ink-400 lg:hidden" aria-hidden />
          <Node title="LLM provider" sub="OpenAI-compatible, Azure OpenAI, or the offline mock — credentials stay server-side" tone="dark" />
        </div>

        <div className="mx-auto mt-4 grid max-w-xl gap-4 sm:grid-cols-2">
          <Node title="Human review" sub="Uncertain or high-risk answers wait for a compliance reviewer" tone="lilac" />
          <Node title="Audit trail" sub="Hash-chained, append-only record of every decision" tone="lilac" />
        </div>
      </div>
    </section>
  );
}
