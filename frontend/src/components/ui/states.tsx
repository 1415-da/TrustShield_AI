import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-lg bg-ink/[0.06]", className)} />;
}

export function LoadingRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink/15 px-6 py-14 text-center">
      {icon && <div className="mb-4 text-forest">{icon}</div>}
      <h3 className="text-xl">{title}</h3>
      {body && <p className="mt-2 max-w-sm text-[13.5px] text-ink-500">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry, requestId }: { message: string; onRetry?: () => void; requestId?: string | null }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl border border-crimson/20 bg-crimson-100/60 px-4 py-3.5 text-[13.5px] text-crimson-700">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">
        <p>{message}</p>
        {requestId && <p className="mt-0.5 font-mono text-[11px] opacity-70">Request {requestId}</p>}
      </div>
      {onRetry && (
        <button onClick={onRetry} className="font-medium underline underline-offset-4">Retry</button>
      )}
    </div>
  );
}
