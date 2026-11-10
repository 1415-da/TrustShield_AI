"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/** Decision palette — validated (CVD + contrast) against the cream surface #FFFFEB. Fixed order. */
export const DECISION_SERIES = [
  { key: "allowed", label: "Allowed", color: "#3E8A5C" },
  { key: "redacted", label: "Redacted", color: "#A879C9" },
  { key: "review", label: "Sent to review", color: "#B07610" },
  { key: "blocked", label: "Blocked", color: "#B4322B" },
  { key: "escalated", label: "Escalated", color: "#4B5FA8" },
] as const;

const AXIS = { fontSize: 11, fill: "#6B6A62" };

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (p.value || 0), 0);
  return (
    <div className="rounded-xl border border-hair bg-cream-50 px-3 py-2 text-[12px] shadow-soft">
      <p className="mb-1 font-medium text-ink">{label}</p>
      {payload.filter((p) => p.value).map((p) => (
        <p key={p.name} className="flex items-center gap-2 text-ink-700">
          <span className="h-2 w-2 rounded-sm" style={{ background: p.color }} />
          <span className="flex-1">{p.name}</span>
          <span className="num font-medium text-ink">{p.value}</span>
        </p>
      ))}
      {payload.length > 1 && <p className="mt-1 border-t border-hair pt-1 text-ink-500">Total <span className="num">{total}</span></p>}
    </div>
  );
}

export function DecisionTimeline({ data }: { data: object[] }) {
  const [table, setTable] = useState(false);
  const rows: Record<string, number | string>[] = (data as Record<string, number | string>[]).map((d) => ({ ...d, day: new Date(String(d.date)).toLocaleDateString(undefined, { month: "short", day: "numeric" }) }));
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-label="Legend">
          {DECISION_SERIES.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5 text-[12px] text-ink-700">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />{s.label}
            </li>
          ))}
        </ul>
        <button onClick={() => setTable(!table)} className="text-[12px] text-ink-500 underline-offset-4 hover:text-ink hover:underline">
          {table ? "Show chart" : "Show as table"}
        </button>
      </div>
      {table ? (
        <div className="scrollbar-thin max-h-[260px] overflow-auto">
          <table className="w-full text-[12.5px]">
            <thead className="sticky top-0 bg-cream-50 text-left text-ink-500">
              <tr><th className="py-1.5 font-medium">Day</th>{DECISION_SERIES.map((s) => <th key={s.key} className="py-1.5 text-right font-medium">{s.label}</th>)}</tr>
            </thead>
            <tbody className="num">
              {rows.map((r) => (
                <tr key={String(r.date)} className="border-t border-hair">
                  <td className="py-1.5">{r.day}</td>
                  {DECISION_SERIES.map((s) => <td key={s.key} className="py-1.5 text-right">{r[s.key] as number}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-[260px]" role="img" aria-label="Requests per day by decision, stacked">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: -18 }} barCategoryGap="28%">
              <CartesianGrid vertical={false} stroke="rgba(26,26,26,0.07)" />
              <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={{ stroke: "rgba(26,26,26,0.15)" }} interval="preserveStartEnd" minTickGap={16} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(3,79,70,0.06)" }} />
              {DECISION_SERIES.map((s, i) => (
                <Bar key={s.key} dataKey={s.key} name={s.label} stackId="d" fill={s.color} stroke="#FFFFEB" strokeWidth={2}
                  radius={i === DECISION_SERIES.length - 1 ? [4, 4, 0, 0] : undefined} maxBarSize={28} isAnimationActive={false} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

/** Single-series ranked bars rendered in plain HTML: direct value labels, no legend needed. */
export function RankedBars({ rows, empty = "No data yet" }: { rows: { label: string; value: number }[]; empty?: string }) {
  if (!rows.length) return <p className="text-[13px] text-ink-500">{empty}</p>;
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.label} className="group" title={`${r.label}: ${r.value}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-[13px]">
            <span className="truncate text-ink-700 group-hover:text-ink">{r.label}</span>
            <span className="num font-medium">{r.value}</span>
          </div>
          <div className="h-2 rounded-full bg-ink/[0.05]">
            <div className="h-full rounded-full bg-forest transition-[width] duration-500 group-hover:bg-forest-900" style={{ width: `${(r.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
