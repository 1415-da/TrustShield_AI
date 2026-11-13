import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { ActionBadge } from "@/components/trust/badges";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const FEED = [
  { who: "Employee · Operations", q: "What's the refund policy for international vendors?", action: "ALLOW", note: "Answered with 2 citations" },
  { who: "Employee · Engineering", q: "Show Ravi Sharma's salary.", action: "BLOCK", note: "Compensation Confidentiality" },
  { who: "Employee · Finance", q: "My card 4111 •••• •••• 1111 was charged twice…", action: "REDACT", note: "Card number masked before the model" },
  { who: "Employee · Engineering", q: "Can I sue a vendor who delivered late?", action: "REVIEW", note: "Routed to Compliance · SLA 8h" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute -right-40 -top-40 h-[520px] w-[520px] rounded-full bg-lilac/50 blur-3xl" />
      <div className="relative mx-auto grid max-w-6xl gap-14 px-5 pb-20 pt-16 sm:px-8 lg:grid-cols-[1.15fr_1fr] lg:pb-28 lg:pt-24">
        <div className="animate-rise">
          <p className="eyebrow mb-6 flex items-center gap-2"><span className="h-px w-8 bg-ink/30" />AI governance gateway</p>
          <h1 className="text-[44px] leading-[1.02] sm:text-[60px] lg:text-[68px]">
            Ship AI your security team <em className="text-forest">can trust.</em>
          </h1>
          <p className="mt-7 max-w-xl text-[17px] leading-relaxed text-ink-700">
            TrustShield sits between your people and your AI — assistants, Slack bots and agents. It checks every request
            before it reaches the model, validates every answer before it reaches a person, holds risky agent actions for the
            right approver, and keeps a tamper-evident record of every decision.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link href="/demo" className={cn(buttonVariants({ size: "lg" }), "group")}>
              Live demo <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </Link>
            <Link href="/signup" className={buttonVariants({ variant: "secondary", size: "lg" })}>Create workspace</Link>
          </div>
          <p className="mt-6 text-[13px] text-ink-500">No credit card · Your own isolated workspace in under a minute · Self-hostable</p>
        </div>

        <div className="animate-rise [animation-delay:120ms]">
          <div className="rounded-[28px] border border-hair bg-cream-50 p-2 shadow-lift">
            <div className="flex items-center justify-between px-4 pb-2 pt-3">
              <p className="eyebrow">Decision stream</p>
              <Link href="/demo" className="text-[11.5px] text-forest hover:underline">Run these yourself →</Link>
            </div>
            <ul className="space-y-1.5">
              {FEED.map((f) => (
                <li key={f.q} className="rounded-[20px] border border-hair bg-white/70 px-4 py-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[11.5px] text-ink-500">{f.who}</span>
                    <ActionBadge action={f.action} />
                  </div>
                  <p className="mt-1.5 text-[14px] leading-snug">{f.q}</p>
                  <p className="mt-1 text-[12px] text-ink-500">{f.note}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
