"use client";

import { ArrowRight, Bot, CheckCircle2, ClipboardCheck, FileLock2, Fingerprint, Gauge, Hash, ScrollText, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import type { PublicStats } from "@/lib/types";
import { cn } from "@/lib/utils";

const FEATURES = [
  { Icon: ShieldCheck, title: "Input guardrails", body: "Prompt-injection scoring, Microsoft Presidio PII detection with enterprise recognizers, and sensitive-topic classification before anything leaves your network." },
  { Icon: Gauge, title: "Output validation", body: "Every draft is scanned for leaked identifiers and scored against the policy evidence it cites. Weak support becomes a warning or a review — never a confident guess." },
  { Icon: FileLock2, title: "Policy engine", body: "Rules live in the database, not in code. Regex, keywords, PII entities, topics, role permissions and confidence thresholds — versioned and testable." },
  { Icon: Users, title: "Human review", body: "A prioritised queue with SLA aging. Reviewers approve, edit, reject or escalate with the request, draft, evidence and risk explanation side by side." },
  { Icon: ScrollText, title: "Audit trail", body: "Request ID, role, policies triggered, risk scores, model, latency and outcome — hash-chained and append-only, with sensitive values stored as hashes." },
  { Icon: Fingerprint, title: "Role-based access", body: "An HR manager can see a salary band; an engineer can't. Data scopes are attached to roles and enforced on the way in and the way out." },
  { Icon: Bot, title: "Agent action controls", body: "Refunds, access changes and record updates are classified, risk-scored and held for the right approver. Executed once, compensable, fully traced." },
  { Icon: Hash, title: "Slack & team channels", body: "The same governed answers in Slack threads and built-in channels, with per-channel policy profiles and signed, idempotent event handling." },
];

export function Features() {
  return (
    <section id="platform" className="mx-auto max-w-6xl px-5 py-24 sm:px-8" aria-labelledby="platform-title">
      <div className="grid gap-10 lg:grid-cols-[1fr_2fr]">
        <div>
          <p className="eyebrow">Platform</p>
          <h2 id="platform-title" className="mt-3 text-[34px] leading-tight sm:text-[40px]">Governance that ships with the assistant.</h2>
        </div>
        <div className="grid gap-x-10 gap-y-12 sm:grid-cols-2">
          {FEATURES.map(({ Icon, title, body }) => (
            <div key={title} className="border-t border-hair pt-6">
              <Icon className="h-5 w-5 text-forest" strokeWidth={1.6} />
              <h3 className="mt-4 text-[22px]">{title}</h3>
              <p className="mt-2 text-[14.5px] leading-relaxed text-ink-700">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const STEPS = [
  ["Connect your assistant", "Point your internal assistant at the TrustShield API. Employees sign in as usual; the gateway resolves their role and data scopes."],
  ["Encode your policies", "Upload your policy documents as knowledge sources and turn the rules that matter into enforceable policies in Policy Studio."],
  ["Test before you enforce", "Run any prompt as any role in the simulator, and run the evaluation suite to see pass rate, false positives and false negatives."],
  ["Operate with evidence", "Reviewers work the queue, security watches the audit log, and every decision can be traced back to a policy version."],
];

export function HowItWorks() {
  return (
    <section id="how" className="bg-forest text-cream" aria-labelledby="how-title">
      <div className="mx-auto max-w-6xl px-5 py-24 sm:px-8">
        <p className="eyebrow text-cream/60">How it works</p>
        <h2 id="how-title" className="mt-3 max-w-2xl text-[34px] leading-tight text-cream sm:text-[40px]">From pilot to production without a security exception.</h2>
        <ol className="mt-14 grid gap-px overflow-hidden rounded-3xl border border-cream/15 bg-cream/15 md:grid-cols-4">
          {STEPS.map(([title, body], i) => (
            <li key={title} className="bg-forest p-7">
              <span className="num font-serif text-[40px] leading-none text-lilac">{i + 1}</span>
              <h3 className="mt-6 text-[21px] text-cream">{title}</h3>
              <p className="mt-2 text-[14px] leading-relaxed text-cream/75">{body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

const TRUST = [
  ["Mask before storage", "Card numbers, IDs, emails and credentials are masked before a message is stored. Logs keep SHA-256 hashes, never the raw value."],
  ["Blocked means blocked", "A blocked or escalated request is never sent to the model. That invariant is covered by the automated test suite."],
  ["Signals, not promises", "Grounding and confidence scores are labelled as risk signals. Low scores route to people instead of pretending to detect hallucinations."],
  ["Tamper-evident history", "Audit events are append-only at the database level and hash-chained, so any edit to history is detectable."],
];

export function Trust() {
  return (
    <section id="trust" className="mx-auto max-w-6xl px-5 py-24 sm:px-8" aria-labelledby="trust-title">
      <div className="grid gap-12 lg:grid-cols-2">
        <div>
          <p className="eyebrow">Trust & compliance</p>
          <h2 id="trust-title" className="mt-3 text-[34px] leading-tight sm:text-[40px]">Built the way your security review will read it.</h2>
          <p className="mt-4 max-w-md text-ink-700">TrustShield is self-hosted. Your prompts, policies and audit history stay in your PostgreSQL database, and model credentials never reach the browser.</p>
        </div>
        <dl className="grid gap-6 sm:grid-cols-2">
          {TRUST.map(([t, b]) => (
            <div key={t} className="rounded-2xl border border-hair bg-cream-50 p-6">
              <dt className="flex items-center gap-2 font-medium"><ClipboardCheck className="h-4 w-4 text-forest" />{t}</dt>
              <dd className="mt-2 text-[14px] leading-relaxed text-ink-700">{b}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

const METRICS = [
  ["49", "labelled evaluation scenarios ship with the evaluation suite, across 17 categories"],
  ["5", "possible decisions per request — every request gets exactly one, and it is logged"],
  ["0", "model calls on blocked or escalated requests, enforced by an automated test"],
  ["5", "decisions for agent actions — execute, approve, review, escalate or block — before anything changes"],
];

export function Metrics() {
  return (
    <section className="border-y border-hair bg-cream-50/60" aria-labelledby="metrics-title">
      <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 id="metrics-title" className="text-[30px] leading-tight sm:text-[34px]">Governance you can measure</h2>
          <p className="rounded-full border border-hair px-3 py-1 text-[12px] text-ink-500">Built into every workspace</p>
        </div>
        <dl className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {METRICS.map(([n, label]) => (
            <div key={label} className="border-l border-forest/30 pl-5">
              <dt className="num font-serif text-[52px] leading-none text-forest">{n}</dt>
              <dd className="mt-3 text-[14px] leading-snug text-ink-700">{label}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-10 max-w-2xl text-[13px] text-ink-500">Pass rate, false-positive and false-negative figures are computed live by the Test Center against these scenarios — measured in your environment, not claimed in ours.</p>
      </div>
    </section>
  );
}

const FAQS = [
  ["Does TrustShield replace our LLM provider?", "No. It sits in front of whichever OpenAI-compatible or Azure OpenAI endpoint you already use. Without an API key it runs on a deterministic offline model so you can evaluate it safely."],
  ["Can agents take actions on their own?", "Only within rules you set. Every agent action is classified, checked against the requester's role and your approval rules, and executed through a controlled executor — high-value or destructive actions wait for the right approver."],
  ["Can we prove compliance to an auditor?", "Yes. The Compliance Evidence Center generates immutable, hashed reports from audit records, and anyone can re-verify that a report regenerates identically from the same records."],
  ["How do you detect hallucinations?", "We don't claim to. TrustShield computes a grounding risk signal from evidence overlap, citations, similarity and contradiction cues. Low scores add a warning or route the answer to a reviewer."],
  ["Can admins change rules without engineering?", "Yes. Policies and their rules are stored in the database, versioned on every change, and can be tested in the simulator — including inactive drafts — before activation."],
  ["What gets stored about a request?", "The masked prompt and answer, the decision at each stage, the rules that fired, risk scores, model and latency. Raw sensitive values are represented only by hashes."],
  ["Where does our data live?", "In your PostgreSQL database, inside your network. Sensitive values are masked before storage, and model credentials never reach the browser."],
];

export function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-3xl px-5 py-24 sm:px-8" aria-labelledby="faq-title">
      <p className="eyebrow text-center">FAQ</p>
      <h2 id="faq-title" className="mt-3 text-center text-[34px] sm:text-[40px]">Questions security teams ask</h2>
      <div className="mt-10 divide-y divide-hair border-y border-hair">
        {FAQS.map(([q, a]) => (
          <details key={q} className="group py-5">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-6 text-[17px] font-medium">
              {q}
              <span aria-hidden className="text-xl text-forest transition group-open:rotate-45">+</span>
            </summary>
            <p className="mt-3 text-[14.5px] leading-relaxed text-ink-700">{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

export function LiveStats() {
  const [stats, setStats] = useState<PublicStats | null>(null);
  useEffect(() => {
    fetch("/api/public/stats").then((r) => (r.ok ? r.json() : null)).then(setStats).catch(() => setStats(null));
  }, []);
  const by = stats?.by_decision ?? {};
  const items: [string, number | undefined, string][] = [
    ["Requests governed", stats?.requests, "in the live NovaCorp workspace, last 30 days"],
    ["Blocked before the model", by.BLOCK, "never sent to the LLM"],
    ["Masked, then answered", by.REDACT, "sensitive values removed first"],
    ["Sent to people", (by.REVIEW ?? 0) + (by.ESCALATE ?? 0) || undefined, "review or escalation"],
  ];
  return (
    <section aria-label="Live workspace activity" className="border-y border-hair bg-cream-50/60">
      <div className="mx-auto grid max-w-6xl gap-6 px-5 py-10 sm:grid-cols-2 sm:px-8 lg:grid-cols-4">
        {items.map(([label, n, sub]) => (
          <div key={label} className="border-l border-forest/30 pl-5">
            <p className="eyebrow flex items-center gap-1.5">{label === "Requests governed" && <span aria-hidden className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-sage" />}{label}</p>
            <p className="num mt-2 font-serif text-[40px] leading-none text-forest">{stats ? (n ?? 0).toLocaleString() : "—"}</p>
            <p className="mt-1.5 text-[12.5px] text-ink-500">{sub}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

const SNIPPETS = {
  python: `import os, requests

TS = "https://trustshield.yourco.com/api/v1/guard"
KEY = {"X-TrustShield-App-Key": os.environ["TRUSTSHIELD_KEY"]}

check = requests.post(f"{TS}/input", headers=KEY, json={
    "text": prompt, "subject": {"role": "employee", "email": user.email},
}).json()

if not check["allow_model_call"]:
    return check["user_message"]          # blocked or escalated

draft = my_llm(check["sanitized_text"])   # PII already masked

out = requests.post(f"{TS}/output", headers=KEY, json={
    "text": draft, "prompt": check["sanitized_text"], "context": passages,
}).json()
return out["sanitized_text"] if out["show_to_user"] else out["user_message"]`,
  curl: `curl -X POST https://trustshield.yourco.com/api/v1/guard/input \\
  -H "X-TrustShield-App-Key: $TRUSTSHIELD_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"text": "Export every employee bank account to a CSV.", "subject": {"role": "employee"}}'

# → {"decision": "ESCALATE", "allow_model_call": false,
#    "matches": [{"policy": "Bulk Data Exfiltration", ...}],
#    "user_message": "This request has been paused and escalated ..."}`,
  node: `const res = await fetch(\`\${TS}/input\`, {
  method: "POST",
  headers: { "X-TrustShield-App-Key": process.env.TRUSTSHIELD_KEY!, "Content-Type": "application/json" },
  body: JSON.stringify({ text: prompt, subject: { role: "employee" } }),
});
const check = await res.json();
if (!check.allow_model_call) return check.user_message;
const draft = await llm(check.sanitized_text);`,
};

export function Integrate() {
  const [tab, setTab] = useState<keyof typeof SNIPPETS>("python");
  return (
    <section id="integrate" className="mx-auto max-w-6xl px-5 py-24 sm:px-8" aria-labelledby="integrate-title">
      <div className="grid items-start gap-12 lg:grid-cols-[1fr_1.25fr]">
        <div>
          <p className="eyebrow">For developers</p>
          <h2 id="integrate-title" className="mt-3 text-[34px] leading-tight sm:text-[40px]">Two calls around the model you already use.</h2>
          <p className="mt-4 max-w-md text-ink-700">
            Keep your LLM, your prompts and your UI. Call the Guard API before the model and after it. Your organization&apos;s
            live policies apply, every decision lands in your audit log, and raw sensitive values never come back.
          </p>
          <ul className="mt-6 space-y-2.5 text-[14.5px] text-ink-700">
            {["Input check: injection, PII, credentials, role-scoped topics", "Output check: leaked identifiers, grounding against your passages",
              "One app key per integration — revocable, attributed in the audit log", "Or use the hosted assistant, Slack and agents with zero code"].map((t) => (
              <li key={t} className="flex gap-2.5"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-forest" />{t}</li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/docs/quickstart" className={buttonVariants({})}>Read the quickstart</Link>
            <Link href="/docs/guard-api" className={buttonVariants({ variant: "secondary" })}>Guard API reference</Link>
          </div>
        </div>
        <div className="overflow-hidden rounded-3xl border border-ink/10 bg-[#0F1F1C] shadow-lift">
          <div className="flex items-center gap-1 border-b border-cream/10 px-3 pt-3" role="tablist" aria-label="Language">
            {(Object.keys(SNIPPETS) as (keyof typeof SNIPPETS)[]).map((k) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                className={`rounded-t-lg px-3.5 py-2 text-[12.5px] font-medium transition ${tab === k ? "bg-cream/10 text-cream" : "text-cream/50 hover:text-cream/80"}`}>
                {k === "node" ? "Node.js" : k === "curl" ? "cURL" : "Python"}
              </button>
            ))}
          </div>
          <pre className="scrollbar-thin overflow-x-auto p-5 font-mono text-[12.5px] leading-relaxed text-cream/90"><code>{SNIPPETS[tab]}</code></pre>
        </div>
      </div>
    </section>
  );
}

export function GetStarted() {
  return (
    <section id="start" className="mx-auto max-w-6xl px-5 pb-24 sm:px-8" aria-labelledby="start-title">
      <div className="relative overflow-hidden rounded-[32px] bg-forest px-8 py-14 text-cream sm:px-14">
        <div aria-hidden className="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-lilac/25 blur-3xl" />
        <div className="relative grid items-center gap-10 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <h2 id="start-title" className="text-[34px] leading-tight text-cream sm:text-[44px]">Your organization&apos;s own governed AI workspace — in a minute.</h2>
            <p className="mt-4 max-w-xl text-cream/75">
              Create a workspace and you start with the baseline policy pack already enforcing, an assistant, team channels, agent
              approval rules and a hash-chained audit log. Upload your policies, invite reviewers, connect your apps.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
            <Link href="/signup" className={cn(buttonVariants({ variant: "lilac", size: "lg" }), "group")}>
              Create workspace <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </Link>
            <Link href="/demo" className={cn(buttonVariants({ variant: "secondary", size: "lg" }), "border-cream/25 bg-transparent text-cream hover:bg-cream/10")}>Explore the live demo</Link>
          </div>
        </div>
      </div>
    </section>
  );
}
