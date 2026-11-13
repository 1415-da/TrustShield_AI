"use client";

import { BookOpen, ChevronDown, Hourglass, Info, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";

import { ActionCard } from "@/components/assistant/action-card";
import { TrustBadge } from "@/components/trust/badges";
import { ENTITY_LABELS, timeAgo } from "@/lib/format";
import type { ChatMessage, Citation, Explanation } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Renders assistant text: paragraphs, "- " bullets, [n] citation markers and <MASKED> tokens. */
export function RichText({ text }: { text: string | null | undefined }) {
  const lines = (text ?? "").split("\n");
  const blocks: JSX.Element[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      blocks.push(
        <ul key={`ul${blocks.length}`} className="my-2 space-y-1.5 pl-1">
          {bullets.map((b, i) => (
            <li key={i} className="flex gap-2.5"><span aria-hidden className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-forest" /><span>{inline(b)}</span></li>
          ))}
        </ul>,
      );
      bullets = [];
    }
  };
  lines.forEach((line, i) => {
    if (line.startsWith("- ")) bullets.push(line.slice(2));
    else {
      flush();
      if (line.trim()) blocks.push(<p key={i} className="my-1.5">{inline(line)}</p>);
    }
  });
  flush();
  return <>{blocks}</>;
}

function inline(s: string | null | undefined) {
  return (s ?? "").split(/(\[\d+\]|<[A-Z_]+>)/g).map((part, i) => {
    if (/^\[\d+\]$/.test(part)) return <sup key={i} className="ml-0.5 rounded bg-forest-50 px-1 text-[10.5px] font-semibold text-forest">{part.slice(1, -1)}</sup>;
    const m = part.match(/^<([A-Z_]+)>$/);
    if (m) return <span key={i} className="mx-0.5 rounded-md bg-lilac px-1.5 py-px text-[12px] font-medium text-lilac-700" title="Masked by TrustShield">{ENTITY_LABELS[m[1]] ?? m[1]} hidden</span>;
    return <span key={i}>{part}</span>;
  });
}

function Sources({ citations }: { citations: Citation[] | null | undefined }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!citations?.length) return null;
  return (
    <div className="mt-3">
      <p className="eyebrow mb-2 flex items-center gap-1.5"><BookOpen className="h-3 w-3" />Sources</p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c) => (
          <button
            key={`${c.index}-${c.chunk_id}`}
            onClick={() => setOpen(open === c.index ? null : c.index)}
            aria-expanded={open === c.index}
            className={cn("rounded-full border px-2.5 py-1 text-[12px] transition", open === c.index ? "border-forest bg-forest text-cream" : "border-hair bg-white/60 text-ink-700 hover:border-forest/40")}
          >
            <span className="num mr-1 font-semibold">{c.index}</span>{c.title}{c.heading && c.kind === "policy" ? ` · ${c.heading}` : ""}
          </button>
        ))}
      </div>
      {citations.filter((c) => c.index === open).map((c) => (
        <blockquote key={c.index} className="mt-2 rounded-xl border-l-2 border-forest bg-forest-50/60 px-4 py-3 text-[13px] leading-relaxed text-ink-700 animate-rise">
          {c.snippet}{(c.snippet?.length ?? 0) >= 270 ? "…" : ""}
        </blockquote>
      ))}
    </div>
  );
}

function WhyPanel({ explanation, status }: { explanation: Explanation; status: string }) {
  const [open, setOpen] = useState(status === "blocked");
  const label = status === "blocked" ? "Why was this blocked?" : status === "needs_review" ? "Why is this being reviewed?" : status === "redacted" ? "What was masked?" : "About this answer";
  return (
    <div className="mt-3 rounded-xl border border-hair bg-white/50">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left text-[13px] font-medium text-ink-700">
        <span className="flex items-center gap-2"><Info className="h-3.5 w-3.5 text-forest" />{label}</span>
        <ChevronDown className={cn("h-4 w-4 text-ink-400 transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-3 border-t border-hair px-3.5 py-3 text-[13px] leading-relaxed text-ink-700" data-testid="why-panel">
          <p className="font-medium text-ink">{explanation.headline}</p>
          {(explanation.policies ?? []).map((p) => (
            <div key={p.id} className="rounded-lg bg-cream-200/60 px-3 py-2">
              <p className="text-[12.5px] font-semibold text-ink">{p.name}</p>
              {p.reason && <p className="mt-0.5">{p.reason}</p>}
            </div>
          ))}
          {(explanation.redactions?.length ?? 0) > 0 && (
            <p>Masked before reaching the model or you: {(explanation.redactions ?? []).map((r) => `${ENTITY_LABELS[r.entity_type] ?? r.entity_type}${r.count > 1 ? ` ×${r.count}` : ""}`).join(", ")}.</p>
          )}
          {explanation.suggestion && <p className="text-forest">{explanation.suggestion}</p>}
          {typeof explanation.confidence === "number" && (
            <p className="text-[12px] text-ink-500">Grounding confidence {explanation.confidence.toFixed(2)}{explanation.confidence_label ? ` — ${explanation.confidence_label.toLowerCase()}` : ""}.</p>
          )}
        </div>
      )}
    </div>
  );
}

export function MessageView({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-rise">
        <div className="max-w-[85%] rounded-[22px] rounded-br-md bg-ink px-4 py-2.5 text-[14.5px] leading-relaxed text-cream sm:max-w-[75%]">
          {inline(message.content)}
        </div>
      </div>
    );
  }
  if (message.action_id) {
    return (
      <div className="flex gap-3 animate-rise" data-testid="assistant-message" data-trust={message.trust_status ?? "needs_review"}>
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-forest-50 text-forest"><ShieldCheck className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1"><ActionCard actionId={message.action_id} /></div>
      </div>
    );
  }
  const e = message.explanation;
  const status = message.trust_status ?? "verified";
  const pending = message.status === "pending_review";
  return (
    <div className="flex gap-3 animate-rise" data-testid="assistant-message" data-trust={status}>
      <div className={cn("mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", status === "blocked" ? "bg-crimson-100 text-crimson" : "bg-forest-50 text-forest")}>
        {pending ? <Hourglass className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex flex-wrap items-center gap-2">
          <TrustBadge status={status} warning={!!e?.warning} />
          {e?.reviewed && <span className="flex items-center gap-1 text-[12px] text-ink-500"><UserRound className="h-3 w-3" />Reviewed by Compliance</span>}
          <span className="text-[11.5px] text-ink-400">{timeAgo(message.updated_at)}</span>
        </div>
        <div className={cn("rounded-[22px] rounded-tl-md border px-4 py-3 text-[14.5px] leading-relaxed", pending ? "border-amber/30 bg-amber-100/50" : status === "blocked" ? "border-crimson/15 bg-crimson-100/40" : "border-hair bg-cream-50")}>
          <RichText text={message.content} />
          {pending && <p className="mt-2 flex items-center gap-2 text-[12px] text-amber-700"><span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-amber" />Waiting for a reviewer — this updates automatically.</p>}
          {e?.warning && !pending && <p className="mt-2 rounded-lg bg-amber-100/70 px-3 py-2 text-[12.5px] text-amber-700">{e.warning}</p>}
          <Sources citations={message.citations} />
        </div>
        {e && (status !== "verified" || e.warning) && <WhyPanel explanation={e} status={status} />}
        {message.request_id && <p className="mt-1.5 font-mono text-[10.5px] text-ink-300">req {message.request_id.slice(0, 12)}</p>}
      </div>
    </div>
  );
}
