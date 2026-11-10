"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Accessible modal / side drawer. Closes on Escape and backdrop click; restores focus on close. */
export function Dialog({
  open, onClose, title, description, children, side = false, className,
}: {
  open: boolean; onClose: () => void; title: string; description?: ReactNode; children: ReactNode; side?: boolean; className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previous?.focus();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex" role="presentation">
      <div className="absolute inset-0 bg-ink/25 backdrop-blur-[2px]" onClick={onClose} />
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "relative z-10 flex max-h-full flex-col border border-hair bg-cream shadow-lift outline-none animate-rise",
          side ? "ml-auto h-full w-full max-w-xl rounded-l-3xl" : "m-auto w-[calc(100%-2rem)] max-w-lg rounded-3xl",
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-hair px-6 py-5">
          <div>
            <h2 className="text-[22px] leading-tight">{title}</h2>
            {description && <p className="mt-1 text-[13px] text-ink-500">{description}</p>}
          </div>
          <button onClick={onClose} className="rounded-full p-1.5 text-ink-500 hover:bg-ink/5 hover:text-ink" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="scrollbar-thin overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}
