"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/brand/logo";
import { buttonVariants } from "@/components/ui/button";
import { homeFor, useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const LINKS = [
  ["Product", "/#platform"],
  ["How it works", "/#how"],
  ["Live demo", "/demo"],
  ["Docs", "/docs"],
  ["Security", "/#trust"],
];

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const path = usePathname();
  const { user } = useAuth();
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    setOpen(false);
  }, [path]);

  const active = (href: string) => !href.includes("#") && path.startsWith(href);
  return (
    <header className={cn("sticky top-0 z-40 transition-[background,border-color,backdrop-filter]",
      scrolled || open ? "border-b border-hair bg-cream/90 backdrop-blur-md" : "border-b border-transparent")}>
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8" aria-label="Main">
        <Logo />
        <div className="hidden items-center gap-7 text-[14px] text-ink-700 md:flex">
          {LINKS.map(([label, href]) => (
            <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
              className={cn("transition hover:text-ink", active(href) && "font-medium text-ink")}>{label}</Link>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {user ? (
            <Link href={homeFor(user)} className={buttonVariants({ size: "sm" })} data-testid="open-app">Open app</Link>
          ) : (
            <>
              <Link href="/login" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}>Sign in</Link>
              <Link href="/signup" className={buttonVariants({ size: "sm" })}>Create workspace</Link>
            </>
          )}
          <button onClick={() => setOpen((o) => !o)} className="rounded-full p-2 hover:bg-ink/5 md:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open}>
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </nav>
      {open && (
        <div className="border-t border-hair px-5 pb-5 pt-2 md:hidden">
          <ul className="space-y-1">
            {[...LINKS, ...(user ? [] : [["Sign in", "/login"]])].map(([label, href]) => (
              <li key={href}><Link href={href} className="block rounded-xl px-3 py-2.5 text-[15px] hover:bg-ink/5">{label}</Link></li>
            ))}
          </ul>
        </div>
      )}
    </header>
  );
}

const FOOTER = [
  ["Product", [["Platform", "/#platform"], ["Live demo", "/demo"], ["Create workspace", "/signup"], ["Sign in", "/login"]]],
  ["Developers", [["Quickstart", "/docs/quickstart"], ["Guard API", "/docs/guard-api"], ["Assistant API", "/docs/assistant-api"], ["Self-hosting", "/docs/self-hosting"]]],
  ["Governance", [["Policies & approvals", "/docs/policies"], ["Human review", "/docs/review"], ["Agent actions", "/docs/agent-actions"], ["Compliance evidence", "/docs/evidence"]]],
  ["Trust", [["Security model", "/docs/security"], ["Roles & permissions", "/docs/roles"], ["FAQ", "/#faq"]]],
] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-hair bg-cream-50/50">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 sm:px-8 lg:grid-cols-[1.3fr_repeat(4,1fr)]">
        <div>
          <Logo />
          <p className="mt-4 max-w-xs text-[13.5px] leading-relaxed text-ink-500">
            The governance gateway between your people, your AI assistants and your agents.
          </p>
        </div>
        {FOOTER.map(([title, links]) => (
          <div key={title}>
            <p className="eyebrow">{title}</p>
            <ul className="mt-3 space-y-2 text-[13.5px]">
              {links.map(([label, href]) => (
                <li key={href}><Link href={href} className="text-ink-700 transition hover:text-forest">{label}</Link></li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-hair">
        <p className="mx-auto max-w-6xl px-5 py-6 text-[12.5px] text-ink-500 sm:px-8">© {new Date().getFullYear()} TrustShield AI · Self-hosted AI governance</p>
      </div>
    </footer>
  );
}
