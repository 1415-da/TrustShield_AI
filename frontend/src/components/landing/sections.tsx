"use client";

import { ClipboardCheck, FileLock2, Fingerprint, Gauge, ScrollText, ShieldCheck, Users } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";

const FEATURES = [
  { Icon: ShieldCheck, title: "Input guardrails", body: "Prompt-injection scoring, Microsoft Presidio PII detection with enterprise recognizers, and sensitive-topic classification before anything leaves your network." },
  { Icon: Gauge, title: "Output validation", body: "Every draft is scanned for leaked identifiers and scored against the policy evidence it cites. Weak support becomes a warning or a review — never a confident guess." },
  { Icon: FileLock2, title: "Policy engine", body: "Rules live in the database, not in code. Regex, keywords, PII entities, topics, role permissions and confidence thresholds — versioned and testable." },
  { Icon: Users, title: "Human review", body: "A prioritised queue with SLA aging. Reviewers approve, edit, reject or escalate with the request, draft, evidence and risk explanation side by side." },
  { Icon: ScrollText, title: "Audit trail", body: "Request ID, role, policies triggered, risk scores, model, latency and outcome — hash-chained and append-only, with sensitive values stored as hashes." },
  { Icon: Fingerprint, title: "Role-based access", body: "An HR manager can see a salary band; an engineer can't. Data scopes are attached to roles and enforced on the way in and the way out." },
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
  ["49", "labelled evaluation scenarios ship with the demo, across 17 test categories"],
  ["5", "possible decisions per request — every request gets exactly one, and it is logged"],
  ["0", "model calls on blocked or escalated requests, enforced by an automated test"],
  ["14", "seeded policies across injection, compensation, financial data, PII, legal and quality"],
];

export function Metrics() {
  return (
    <section className="border-y border-hair bg-cream-50/60" aria-labelledby="metrics-title">
      <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 id="metrics-title" className="text-[30px] leading-tight sm:text-[34px]">What the demo environment measures</h2>
          <p className="rounded-full border border-hair px-3 py-1 text-[12px] text-ink-500">Simulated demo data · synthetic NovaCorp tenant</p>
        </div>
        <dl className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {METRICS.map(([n, label]) => (
            <div key={label} className="border-l border-forest/30 pl-5">
              <dt className="num font-serif text-[52px] leading-none text-forest">{n}</dt>
              <dd className="mt-3 text-[14px] leading-snug text-ink-700">{label}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-10 max-w-2xl text-[13px] text-ink-500">Pass rate, false-positive and false-negative figures are computed live by the Test Center against these scenarios. We don't publish production performance claims for a demo.</p>
      </div>
    </section>
  );
}

const FAQS = [
  ["Does TrustShield replace our LLM provider?", "No. It sits in front of whichever OpenAI-compatible or Azure OpenAI endpoint you already use. Without an API key it runs on a deterministic offline model so you can evaluate it safely."],
  ["How do you detect hallucinations?", "We don't claim to. TrustShield computes a grounding risk signal from evidence overlap, citations, similarity and contradiction cues. Low scores add a warning or route the answer to a reviewer."],
  ["Can admins change rules without engineering?", "Yes. Policies and their rules are stored in the database, versioned on every change, and can be tested in the simulator — including inactive drafts — before activation."],
  ["What gets stored about a request?", "The masked prompt and answer, the decision at each stage, the rules that fired, risk scores, model and latency. Raw sensitive values are represented only by hashes."],
  ["Is any real personal data in the demo?", "No. NovaCorp Technologies is fictional. Every name, email, phone number, salary band and identifier is synthetic test data."],
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

export function DemoRequest() {
  const [sent, setSent] = useState(false);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setSent(true);
  };
  return (
    <section id="demo" className="mx-auto max-w-6xl px-5 pb-24 sm:px-8" aria-labelledby="demo-title">
      <div className="grid gap-10 rounded-[32px] bg-lilac-200 p-8 sm:p-12 lg:grid-cols-2">
        <div>
          <h2 id="demo-title" className="text-[34px] leading-tight sm:text-[40px]">See it with your own policies.</h2>
          <p className="mt-4 max-w-md text-ink-700">Tell us a little about your rollout. This is a portfolio demo, so nothing is sent anywhere — but the live product is one click away.</p>
          <a href="/login" className="link mt-6 inline-block text-[15px]">Explore the live product instead →</a>
        </div>
        {sent ? (
          <div role="status" className="flex flex-col justify-center rounded-3xl border border-lilac-400/60 bg-cream-50 p-8">
            <p className="font-serif text-[26px]">Thank you.</p>
            <p className="mt-2 text-ink-700">In a real deployment this would reach our team. For now, sign in with one of the demo accounts to see TrustShield in action.</p>
          </div>
        ) : (
          <form onSubmit={submit} className="grid gap-4 rounded-3xl border border-lilac-400/60 bg-cream-50 p-6 sm:grid-cols-2">
            <Field label="Work email" htmlFor="demo-email" className="sm:col-span-2"><Input id="demo-email" type="email" required placeholder="you@company.com" /></Field>
            <Field label="Company" htmlFor="demo-co"><Input id="demo-co" required /></Field>
            <Field label="Employees" htmlFor="demo-size">
              <Select id="demo-size" defaultValue="1000-5000">
                <option>Under 1,000</option><option value="1000-5000">1,000–5,000</option><option>5,000+</option>
              </Select>
            </Field>
            <Button type="submit" className="sm:col-span-2">Request a demo</Button>
          </form>
        )}
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-hair">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-10 text-[13px] text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <p>© {new Date().getFullYear()} TrustShield AI · Portfolio MVP. All demo data is synthetic.</p>
        <div className="flex gap-6">
          <a href="#platform" className="hover:text-ink">Platform</a>
          <a href="#trust" className="hover:text-ink">Trust</a>
          <a href="/login" className="hover:text-ink">Sign in</a>
        </div>
      </div>
    </footer>
  );
}
