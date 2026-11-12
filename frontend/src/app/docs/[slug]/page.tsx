import { ArrowLeft, ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DOC_PAGES } from "@/components/docs/pages";
import { DOCS } from "@/components/docs/registry";

export function generateStaticParams() {
  return DOCS.map((d) => ({ slug: d.slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const d = DOCS.find((x) => x.slug === params.slug);
  return d ? { title: d.title, description: d.summary } : {};
}

export default function DocPage({ params }: { params: { slug: string } }) {
  const i = DOCS.findIndex((d) => d.slug === params.slug);
  if (i < 0 || !DOC_PAGES[params.slug]) notFound();
  const doc = DOCS[i];
  const prev = DOCS[i - 1];
  const next = DOCS[i + 1];
  return (
    <article className="max-w-3xl">
      <p className="eyebrow">{doc.group}</p>
      <h1 className="mt-3 text-[38px] leading-[1.1] sm:text-[44px]">{doc.title}</h1>
      <p className="mt-3 text-[17px] leading-relaxed text-ink-500">{doc.summary}</p>
      <div className="mt-8 border-t border-hair pt-2">{DOC_PAGES[doc.slug]}</div>
      <nav className="mt-16 grid gap-3 border-t border-hair pt-6 sm:grid-cols-2" aria-label="Pagination">
        {prev ? (
          <Link href={`/docs/${prev.slug}`} className="group rounded-2xl border border-hair p-4 transition hover:border-forest/40">
            <span className="flex items-center gap-1 text-[12px] text-ink-500"><ArrowLeft className="h-3.5 w-3.5" />Previous</span>
            <span className="mt-1 block font-medium">{prev.title}</span>
          </Link>
        ) : <span />}
        {next && (
          <Link href={`/docs/${next.slug}`} className="group rounded-2xl border border-hair p-4 text-right transition hover:border-forest/40">
            <span className="flex items-center justify-end gap-1 text-[12px] text-ink-500">Next<ArrowRight className="h-3.5 w-3.5" /></span>
            <span className="mt-1 block font-medium">{next.title}</span>
          </Link>
        )}
      </nav>
    </article>
  );
}
