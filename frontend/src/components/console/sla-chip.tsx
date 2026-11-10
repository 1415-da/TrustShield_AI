"use client";

import { Clock } from "lucide-react";
import { useEffect, useState } from "react";

import { slaRemaining, timeAgo } from "@/lib/format";
import type { ReviewCase } from "@/lib/types";
import { cn } from "@/lib/utils";

export function SlaChip({ c }: { c: ReviewCase }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t); }, []);
  if (c.resolved_at) return <span className="text-[12px] text-ink-500">Resolved {timeAgo(c.resolved_at)}</span>;
  const s = slaRemaining(c.sla_due_at, now);
  return (
    <span className={cn("inline-flex items-center gap-1 text-[12px] font-medium", s.overdue ? "text-crimson" : s.urgent ? "text-amber-700" : "text-ink-500")}>
      <Clock className="h-3 w-3" />{s.label}
    </span>
  );
}

