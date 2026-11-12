import { ArrowRight, BookOpen, Code2, Compass, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { DOC_GROUPS, DOCS } from "@/components/docs/registry";

const ICON = { "Getting started": Compass, Govern: ShieldCheck, Developers: Code2, Reference: BookOpen } as const;

export default function DocsHome() {
  return (
    <>
      <p className="eyebrow">Documentation</p>
      <h1 className="mt-3 text-[40px] leading-[1.08] sm:text-[48px]">Use TrustShield to govern your AI.</h1>
      <p className="mt-4 max-w-2xl text-[16px] leading-relaxed text-ink-700">
        Everything you need to run TrustShield for your organization — from your first workspace to putting the guardrails in front
        of your own LLM apps, approving agent actions, and handing evidence to auditors.
      </p>
      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        <Link href="/docs/quickstart" className="group rounded-2xl bg-forest p-6 text-cream transition hover:bg-forest-900">
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-cream/60">Start here</p>
          <p className="mt-2 font-serif text-[24px]">Quickstart</p>
          <p className="mt-1 text-[14px] text-cream/75">From a new workspace to a governed assistant in ten minutes.</p>
          <span className="mt-4 inline-flex items-center gap-1 text-[13px] text-lilac">Read <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" /></span>
        </Link>
        <Link href="/docs/guard-api" className="group rounded-2xl border border-hair bg-lilac-200/60 p-6 transition hover:border-lilac-400">
          <p className="eyebrow">For developers</p>
          <p className="mt-2 font-serif text-[24px]">Guard API</p>
          <p className="mt-1 text-[14px] text-ink-700">Two server-side calls around the model you already use.</p>
          <span className="mt-4 inline-flex items-center gap-1 text-[13px] text-forest">Read <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" /></span>
        </Link>
      </div>
      {DOC_GROUPS.map((g) => {
        const Icon = ICON[g as keyof typeof ICON] ?? BookOpen;
        return (
          <section key={g} className="mt-12">
            <h2 className="flex items-center gap-2 text-[24px]"><Icon className="h-5 w-5 text-forest" strokeWidth={1.7} />{g}</h2>
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {DOCS.filter((d) => d.group === g).map((d) => (
                <li key={d.slug}>
                  <Link href={`/docs/${d.slug}`} className="block h-full rounded-2xl border border-hair bg-cream-50/70 p-5 transition hover:border-forest/40 hover:bg-white">
                    <p className="font-medium">{d.title}</p>
                    <p className="mt-1 text-[13.5px] leading-relaxed text-ink-500">{d.summary}</p>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </>
  );
}
