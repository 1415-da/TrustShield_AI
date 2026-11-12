"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { DOC_GROUPS, DOCS } from "@/components/docs/registry";
import { cn } from "@/lib/utils";

export function DocsSidebar() {
  const path = usePathname();
  return (
    <nav aria-label="Documentation" className="space-y-6 text-[13.5px]">
      <Link href="/docs" className={cn("block rounded-lg px-3 py-1.5 font-medium", path === "/docs" ? "bg-lilac/60 text-ink" : "text-ink-700 hover:bg-ink/5")}>Overview</Link>
      {DOC_GROUPS.map((g) => (
        <div key={g}>
          <p className="eyebrow px-3 pb-1.5">{g}</p>
          <ul className="space-y-0.5">
            {DOCS.filter((d) => d.group === g).map((d) => {
              const active = path === `/docs/${d.slug}`;
              return (
                <li key={d.slug}>
                  <Link href={`/docs/${d.slug}`} aria-current={active ? "page" : undefined}
                    className={cn("block rounded-lg px-3 py-1.5 transition", active ? "bg-lilac/60 font-medium text-ink" : "text-ink-700 hover:bg-ink/5 hover:text-ink")}>
                    {d.title}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function DocsMobileNav() {
  const path = usePathname();
  return (
    <label className="block lg:hidden">
      <span className="sr-only">Jump to page</span>
      <select value={path} onChange={(e) => { window.location.href = e.target.value; }}
        className="h-10 w-full rounded-xl border border-ink/15 bg-white/70 px-3 text-[14px]">
        <option value="/docs">Overview</option>
        {DOC_GROUPS.map((g) => (
          <optgroup key={g} label={g}>
            {DOCS.filter((d) => d.group === g).map((d) => <option key={d.slug} value={`/docs/${d.slug}`}>{d.title}</option>)}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
