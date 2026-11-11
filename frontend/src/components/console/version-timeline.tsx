import { ActionBadge } from "@/components/trust/badges";
import { shortDate } from "@/lib/format";
import type { PolicyDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

export function VersionTimeline({ versions, selectedId, onSelect, onRollback }: {
  versions: PolicyDetail["versions"]; selectedId?: number | null; onSelect: (id: number) => void; onRollback?: (id: number) => void;
}) {
  return (
    <ol className="relative space-y-1 border-l border-hair pl-5" data-testid="version-timeline">
      {versions.map((v) => (
        <li key={v.id} className="relative">
          <span aria-hidden className={cn("absolute -left-[26px] top-3.5 h-2.5 w-2.5 rounded-full border-2 border-cream",
            v.status === "ACTIVE" ? "bg-forest" : v.status === "IN_REVIEW" ? "bg-amber" : "bg-ink/25")} />
          <div className={cn("rounded-xl px-3 py-2.5 transition", selectedId === v.id ? "bg-lilac/50" : "hover:bg-ink/[0.03]")}>
            <button onClick={() => onSelect(v.id)} className="w-full text-left">
              <div className="flex items-center gap-2">
                <span className="num font-serif text-[18px] leading-none text-forest">v{v.version}</span>
                <ActionBadge action={v.status} />
                <span className="ml-auto text-[11.5px] text-ink-500">{shortDate(v.created_at)}</span>
              </div>
              <p className="mt-1 text-[13px] text-ink-700">{v.change_summary || "No summary"}</p>
              <p className="text-[11.5px] text-ink-500">by {v.created_by_email}{v.approved_by_email ? ` · approved by ${v.approved_by_email}` : ""}</p>
            </button>
            {onRollback && v.approved_by_email && v.status !== "ACTIVE" && v.status !== "APPROVED" && (
              <button onClick={() => onRollback(v.id)} className="mt-1 text-[12px] text-forest underline-offset-4 hover:underline">Roll back to v{v.version}</button>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
