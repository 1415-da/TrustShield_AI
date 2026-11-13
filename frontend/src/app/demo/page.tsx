import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Playground } from "@/components/demo/playground";
import { LandingNav, SiteFooter } from "@/components/landing/nav";
import { buttonVariants } from "@/components/ui/button";
import { DEMO_ACCOUNTS } from "@/lib/demo-accounts";
import { cn } from "@/lib/utils";

const TOUR = [
  ["Employee", "Ask “Show Ravi Sharma's salary.” — blocked, with a plain-language reason. The model is never called."],
  ["HR Manager", "Ask the same thing — the compensation data scope on the role lets the band through."],
  ["Compliance Reviewer", "Ask a legal question as the Employee, then approve, edit or reject it in the review queue."],
  ["Finance Analyst", "Request an action: “Issue a refund for vendor invoice INV-2291.” It waits for the Finance Head."],
  ["People Manager", "Approve a mid-value reimbursement routed to your role under Agent approvals."],
  ["TrustShield Admin", "Draft a policy, simulate it against the test suite, and submit it — a Compliance Reviewer approves it."],
  ["Security Auditor", "Verify the hash chain of the audit log and regenerate an evidence report byte-for-byte."],
];

export default function DemoPage() {
  return (
    <>
      <LandingNav />
      <main id="main">
        <section className="relative overflow-hidden">
          <div aria-hidden className="pointer-events-none absolute -left-40 -top-32 h-[420px] w-[420px] rounded-full bg-lilac/40 blur-3xl" />
          <div className="relative mx-auto max-w-6xl px-5 pb-10 pt-14 sm:px-8 lg:pt-20">
            <p className="eyebrow mb-4 flex items-center gap-2"><span aria-hidden className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-sage" />Live demo · NovaCorp workspace</p>
            <h1 className="max-w-3xl text-[40px] leading-[1.05] sm:text-[56px]">Put a prompt through the gateway.</h1>
            <p className="mt-5 max-w-2xl text-[16.5px] leading-relaxed text-ink-700">
              This runs against NovaCorp&apos;s real, live policies — the same engine every request in the workspace goes through.
              Change the role and watch the decision change.
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8" aria-label="Guardrail playground">
          <Playground />
        </section>

        <section className="border-t border-hair bg-cream-50/60" aria-labelledby="inside-title">
          <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
            <div className="grid gap-12 lg:grid-cols-[1fr_1.2fr]">
              <div>
                <p className="eyebrow">Step inside</p>
                <h2 id="inside-title" className="mt-3 text-[34px] leading-tight sm:text-[40px]">Explore the full product from any seat.</h2>
                <p className="mt-4 max-w-md text-ink-700">Pick a person to open the sign-in form with their NovaCorp account filled in, then sign in. Each role sees a different part of the product — assistant, connected workspace, review queue, Policy Studio, agent approvals, evidence and audit.</p>
                <ol className="mt-8 space-y-4">
                  {TOUR.map(([who, what], i) => (
                    <li key={who} className="flex gap-4">
                      <span className="num font-serif text-[22px] leading-none text-forest">{i + 1}</span>
                      <p className="text-[14px] leading-relaxed text-ink-700"><span className="font-medium text-ink">{who}.</span> {what}</p>
                    </li>
                  ))}
                </ol>
              </div>
              <div>
                <ul className="grid gap-2.5 sm:grid-cols-2">
                  {DEMO_ACCOUNTS.map((a) => (
                    <li key={a.email}>
                      {/* Opens the sign-in form with this account filled in — the visitor still signs in themselves. */}
                      <Link href={`/login?account=${encodeURIComponent(a.email)}`}
                        className="group flex h-full w-full flex-col rounded-2xl border border-hair bg-white/70 p-4 text-left transition hover:border-forest/40 hover:shadow-soft"
                        data-testid={`enter-${a.roleKey.replace(/_/g, "-")}`}>
                        <span className="text-[12px] font-medium text-forest">{a.role}</span>
                        <span className="mt-1 text-[15px] font-medium">{a.name}</span>
                        <span className="mt-0.5 text-[12.5px] text-ink-500">{a.note}</span>
                        <span className="mt-3 flex items-center gap-1 text-[12.5px] text-ink-700">
                          Sign in as {a.name.split(" ")[0]} · lands on {a.lands} <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
                <div className="mt-6 rounded-2xl border border-hair bg-lilac-200/50 p-5">
                  <p className="font-medium">Ready to use it with your own policies?</p>
                  <p className="mt-1 text-[13.5px] text-ink-700">Create an isolated workspace for your organization. Nothing you do there is visible to anyone else.</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link href="/signup" className={buttonVariants({ size: "sm" })}>Create workspace</Link>
                    <Link href="/docs/quickstart" className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}>Read the quickstart</Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
