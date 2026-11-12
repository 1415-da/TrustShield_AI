"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useRef, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

export type ComposerMode = "ask" | "action";

export function Composer({ value, onChange, onSend, busy, mode = "ask", onModeChange }: {
  value: string; onChange: (v: string) => void; onSend: () => void; busy: boolean; mode?: ComposerMode; onModeChange?: (m: ComposerMode) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (value.trim() && !busy) onSend();
    }
  };
  return (
    <div>
    {onModeChange && (
      <div role="radiogroup" aria-label="Composer mode" className="mb-2 inline-flex rounded-full border border-hair bg-cream-50 p-0.5 text-[12.5px]">
        {([["ask", "Ask a question"], ["action", "Request an action"]] as const).map(([k, label]) => (
          <button key={k} type="button" role="radio" aria-checked={mode === k} onClick={() => onModeChange(k)} data-testid={`mode-${k}`}
            className={cn("rounded-full px-3 py-1 transition", mode === k ? "bg-forest text-cream" : "text-ink-700 hover:text-ink")}>{label}</button>
        ))}
      </div>
    )}
    <form
      onSubmit={(e) => { e.preventDefault(); if (value.trim() && !busy) onSend(); }}
      className="flex items-end gap-2 rounded-[26px] border border-ink/15 bg-white/80 p-2 pl-4 shadow-soft transition focus-within:border-forest focus-within:ring-2 focus-within:ring-forest/10"
    >
      <label htmlFor="composer" className="sr-only">Ask the assistant</label>
      <textarea
        id="composer"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKey}
        maxLength={4000}
        placeholder={mode === "action" ? "e.g. Issue a refund for vendor invoice INV-2291" : "Ask about a company policy…"}
        className="max-h-[180px] flex-1 resize-none bg-transparent py-2 text-[15px] leading-relaxed placeholder:text-ink-400 focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
        data-testid="composer"
      />
      <button
        type="submit"
        disabled={!value.trim() || busy}
        aria-label="Send"
        className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition", value.trim() && !busy ? "bg-forest text-cream hover:bg-forest-900" : "bg-ink/10 text-ink-400")}
      >
        {busy ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" /> : <ArrowUp className="h-4 w-4" />}
      </button>
    </form>
    </div>
  );
}
