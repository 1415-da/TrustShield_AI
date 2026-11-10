"use client";

import {
  BookOpenText, FlaskConical, Gauge, KeyRound, LogOut, Menu, MessagesSquare, PlugZap, ScrollText, Settings2, ShieldCheck,
  SlidersHorizontal, Users, X, type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { Skeleton } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { ROLE_LABELS } from "@/lib/format";
import type { ReviewCase } from "@/lib/types";
import { cn } from "@/lib/utils";

interface NavItem { href: string; label: string; Icon: LucideIcon; perm: string }

export const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Govern", items: [
    { href: "/console", label: "Overview", Icon: Gauge, perm: "analytics:read" },
    { href: "/console/policies", label: "Policy Studio", Icon: ShieldCheck, perm: "policies:read" },
    { href: "/console/simulator", label: "Simulator", Icon: SlidersHorizontal, perm: "policies:read" },
    { href: "/console/documents", label: "Knowledge sources", Icon: BookOpenText, perm: "documents:read" },
  ] },
  { group: "Operate", items: [
    { href: "/console/reviews", label: "Review queue", Icon: MessagesSquare, perm: "reviews:read" },
    { href: "/console/audit", label: "Audit log", Icon: ScrollText, perm: "audit:read" },
    { href: "/console/tests", label: "Test center", Icon: FlaskConical, perm: "tests:run" },
  ] },
  { group: "Configure", items: [
    { href: "/console/users", label: "Users & roles", Icon: Users, perm: "users:manage" },
    { href: "/console/apps", label: "Connected apps", Icon: PlugZap, perm: "apps:manage" },
    { href: "/console/settings", label: "Settings", Icon: Settings2, perm: "settings:read" },
  ] },
];

export function firstAllowed(can: (p: string) => boolean): string | null {
  for (const g of NAV) for (const i of g.items) if (can(i.perm)) return i.href;
  return null;
}

export function ConsoleShell({ children }: { children: ReactNode }) {
  const { user, loading, logout, can } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const openCases = useApi<ReviewCase[]>(user && can("reviews:read") ? "/reviewer/cases?status=open" : null, 30000);

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(path)}`);
    else if (!loading && user && !firstAllowed(can)) router.replace("/assistant");
  }, [loading, user, can, router, path]);
  useEffect(() => setOpen(false), [path]);

  if (loading || !user) {
    return <div className="flex h-screen items-center justify-center"><Skeleton className="h-10 w-48" /></div>;
  }

  const isActive = (href: string) => (href === "/console" ? path === "/console" : path.startsWith(href));
  const nav = (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-5 pb-6 pt-5">
        <Logo href="/console" />
        <button onClick={() => setOpen(false)} className="rounded-full p-1.5 hover:bg-ink/5 lg:hidden" aria-label="Close navigation"><X className="h-4 w-4" /></button>
      </div>
      <nav className="scrollbar-thin flex-1 space-y-6 overflow-y-auto px-3" aria-label="Console">
        {NAV.map((g) => {
          const items = g.items.filter((i) => can(i.perm));
          if (!items.length) return null;
          return (
            <div key={g.group}>
              <p className="eyebrow px-3 pb-1.5">{g.group}</p>
              <ul className="space-y-0.5">
                {items.map(({ href, label, Icon }) => (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={isActive(href) ? "page" : undefined}
                      className={cn(
                        "relative flex items-center gap-3 rounded-xl px-3 py-2 text-[13.5px] transition",
                        isActive(href) ? "bg-lilac/70 font-medium text-ink" : "text-ink-700 hover:bg-ink/[0.04] hover:text-ink",
                      )}
                    >
                      {isActive(href) && <span aria-hidden className="absolute -left-3 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-forest" />}
                      <Icon className={cn("h-4 w-4", isActive(href) ? "text-forest" : "text-ink-400")} strokeWidth={1.8} />
                      <span className="flex-1">{label}</span>
                      {href === "/console/reviews" && !!openCases.data?.length && (
                        <span className="num rounded-full bg-amber-100 px-1.5 text-[11px] font-semibold text-amber-700" aria-label={`${openCases.data.length} open cases`}>{openCases.data.length}</span>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </nav>
      <div className="border-t border-hair p-3">
        {can("assistant:use") && (
          <Link href="/assistant" className="mb-1 flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] text-ink-700 hover:bg-ink/[0.04]"><KeyRound className="h-4 w-4 text-ink-400" />Open assistant</Link>
        )}
        <div className="flex items-center justify-between gap-2 rounded-xl px-3 py-2">
          <div className="min-w-0">
            <p className="truncate text-[13.5px] font-medium">{user.full_name}</p>
            <p className="truncate text-[11.5px] text-ink-500">{ROLE_LABELS[user.primary_role] ?? user.primary_role}</p>
          </div>
          <button onClick={logout} className="rounded-full p-2 text-ink-500 hover:bg-ink/5 hover:text-ink" aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[256px] shrink-0 border-r border-hair bg-cream-50/70 lg:block">{nav}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/20" onClick={() => setOpen(false)} />
          <aside className="relative h-full w-[270px] bg-cream shadow-lift animate-rise">{nav}</aside>
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-hair bg-cream/90 px-4 backdrop-blur lg:hidden">
          <button onClick={() => setOpen(true)} className="rounded-full p-2 hover:bg-ink/5" aria-label="Open navigation"><Menu className="h-4 w-4" /></button>
          <Logo href="/console" />
        </div>
        <main id="main" className="mx-auto max-w-[1240px] px-4 py-8 sm:px-8 lg:py-10">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 border-b border-hair pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="text-[34px] leading-[1.1] sm:text-[40px]">{title}</h1>
        {description && <p className="mt-2 text-[14.5px] text-ink-700">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Section({ title, description, actions, children, className }: { title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("panel p-5 sm:p-6", className)}>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[21px] leading-tight">{title}</h2>
          {description && <p className="mt-1 text-[13px] text-ink-500">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "crimson" | "amber" | "forest" | "lilac" }) {
  const color = tone ? { crimson: "text-crimson", amber: "text-amber-700", forest: "text-forest", lilac: "text-lilac-700" }[tone] : "text-ink";
  return (
    <div className="md:border-l md:border-hair md:pl-4 md:first:border-l-0 md:first:pl-0">
      <p className="eyebrow">{label}</p>
      <p className={cn("num mt-2 font-serif text-[38px] leading-none", color)}>{value}</p>
      {sub && <p className="mt-1.5 text-[12px] text-ink-500">{sub}</p>}
    </div>
  );
}
