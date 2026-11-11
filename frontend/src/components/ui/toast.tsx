"use client";

import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type Tone = "success" | "error" | "info";
interface ToastItem { id: number; tone: Tone; title: string; body?: string }

const ToastContext = createContext<(t: Omit<ToastItem, "id">) => void>(() => undefined);

/** Non-blocking notifications. Announced politely to screen readers; dismiss with the close button or wait 5s. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((t: Omit<ToastItem, "id">) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs.slice(-3), { ...t, id }]);
    window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 5000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-[min(380px,calc(100vw-2.5rem))] flex-col gap-2">
        {items.map((t) => {
          const Icon = t.tone === "success" ? CheckCircle2 : t.tone === "error" ? TriangleAlert : Info;
          return (
            <div key={t.id} role="status" data-testid="toast"
              className={cn("pointer-events-auto flex items-start gap-3 rounded-2xl border bg-cream-50 px-4 py-3 shadow-lift animate-rise",
                t.tone === "error" ? "border-crimson/30" : "border-hair")}>
              <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", t.tone === "success" ? "text-forest" : t.tone === "error" ? "text-crimson" : "text-ink-500")} />
              <div className="min-w-0 flex-1">
                <p className="text-[13.5px] font-medium">{t.title}</p>
                {t.body && <p className="mt-0.5 text-[12.5px] text-ink-500">{t.body}</p>}
              </div>
              <button onClick={() => setItems((xs) => xs.filter((x) => x.id !== t.id))} className="rounded-full p-1 text-ink-400 hover:text-ink" aria-label="Dismiss">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
