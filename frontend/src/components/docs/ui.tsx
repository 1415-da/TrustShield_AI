"use client";

import { AlertTriangle, Check, Copy, Info, Lightbulb } from "lucide-react";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Code({ children, title, lang }: { children: string; title?: string; lang?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    void navigator.clipboard?.writeText(children.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="my-5 overflow-hidden rounded-2xl border border-ink/10 bg-[#0F1F1C]">
      <div className="flex items-center justify-between border-b border-cream/10 px-4 py-2">
        <span className="font-mono text-[11.5px] text-cream/50">{title ?? lang ?? ""}</span>
        <button onClick={copy} className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] text-cream/60 hover:text-cream" aria-label="Copy code">
          {copied ? <><Check className="h-3.5 w-3.5" />Copied</> : <><Copy className="h-3.5 w-3.5" />Copy</>}
        </button>
      </div>
      <pre className="scrollbar-thin overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-cream/90"><code>{children.trim()}</code></pre>
    </div>
  );
}

const CALLOUT = {
  note: { Icon: Info, cls: "border-forest/20 bg-forest-50" },
  tip: { Icon: Lightbulb, cls: "border-lilac-400/50 bg-lilac-200/50" },
  warning: { Icon: AlertTriangle, cls: "border-amber/30 bg-amber-100/70" },
};

export function Callout({ kind = "note", title, children }: { kind?: keyof typeof CALLOUT; title?: string; children: ReactNode }) {
  const { Icon, cls } = CALLOUT[kind];
  return (
    <div className={cn("my-5 flex gap-3 rounded-2xl border p-4 text-[14px] leading-relaxed", cls)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-forest" />
      <div>{title && <p className="mb-0.5 font-medium">{title}</p>}{children}</div>
    </div>
  );
}

export function H2({ id, children }: { id: string; children: ReactNode }) {
  return <h2 id={id} className="group mt-12 scroll-mt-24 text-[28px] leading-tight first:mt-0"><a href={`#${id}`} className="no-underline">{children}<span className="ml-2 text-ink-300 opacity-0 transition group-hover:opacity-100">#</span></a></h2>;
}

export function H3({ children }: { children: ReactNode }) {
  return <h3 className="mt-8 text-[20px] leading-tight">{children}</h3>;
}

export function P({ children }: { children: ReactNode }) {
  return <p className="mt-4 text-[15px] leading-[1.75] text-ink-700">{children}</p>;
}

export function C({ children }: { children: ReactNode }) {
  return <code className="rounded-md border border-hair bg-cream-200/60 px-1.5 py-0.5 font-mono text-[12.5px] text-ink">{children}</code>;
}

export function UL({ children }: { children: ReactNode }) {
  return <ul className="mt-4 list-disc space-y-2 pl-5 text-[15px] leading-relaxed text-ink-700 marker:text-forest/60">{children}</ul>;
}

export function Steps({ children }: { children: ReactNode }) {
  return <ol className="mt-6 space-y-6 border-l border-forest/20 pl-6 [counter-reset:step]">{children}</ol>;
}

export function Step({ title, children }: { title: string; children: ReactNode }) {
  return (
    <li className="relative [counter-increment:step]">
      <span aria-hidden className="absolute -left-[37px] flex h-6 w-6 items-center justify-center rounded-full bg-forest font-mono text-[11px] text-cream before:content-[counter(step)]" />
      <p className="font-medium">{title}</p>
      <div className="text-[15px] leading-relaxed text-ink-700 [&>*:first-child]:mt-1">{children}</div>
    </li>
  );
}

export function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="my-5 overflow-x-auto rounded-2xl border border-hair">
      <table className="w-full min-w-[520px] text-left text-[13.5px]">
        <thead className="border-b border-hair bg-cream-50 text-[12px] text-ink-500">
          <tr>{head.map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-hair align-top last:border-0">
              {r.map((c, j) => <td key={j} className={cn("px-4 py-2.5 leading-relaxed", j === 0 ? "font-medium text-ink" : "text-ink-700")}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Endpoint({ method, path, auth }: { method: string; path: string; auth?: string }) {
  return (
    <div className="mt-6 flex flex-wrap items-center gap-2 rounded-xl border border-hair bg-white/70 px-3 py-2">
      <span className={cn("rounded-md px-2 py-0.5 font-mono text-[11.5px] font-semibold",
        method === "GET" ? "bg-sage-100 text-sage-700" : "bg-lilac-200 text-lilac-700")}>{method}</span>
      <code className="font-mono text-[13px]">{path}</code>
      {auth && <span className="ml-auto text-[12px] text-ink-500">{auth}</span>}
    </div>
  );
}
