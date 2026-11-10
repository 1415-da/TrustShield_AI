"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useRef, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

export function Composer({ value, onChange, onSend, busy }: { value: string; onChange: (v: string) => void; onSend: () => void; busy: boolean }) {
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
    <form
      onSubmit={(e) => { e.preventDefault(); if (value.trim() && !busy) onSend(); }}
      className="flex items-end gap-2 rounded-[26px] border border-ink/15 bg-white/80 p-2 pl-4 shadow-soft transition focus-within:border-forest focus-within:ring-2 focus-within:ring-forest/10"
    >
      <label htmlFor="composer" className="sr-only">Ask the NovaCorp assistant</label>
      <textarea
        id="composer"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKey}
        maxLength={4000}
        placeholder="Ask about a NovaCorp policy…"
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
  );
}
