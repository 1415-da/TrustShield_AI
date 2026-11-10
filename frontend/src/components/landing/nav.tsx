"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Logo } from "@/components/brand/logo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const LINKS = [
  ["How it works", "#how"],
  ["Platform", "#platform"],
  ["Trust", "#trust"],
  ["FAQ", "#faq"],
];

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header className={cn("sticky top-0 z-40 transition-[background,border-color,backdrop-filter]", scrolled ? "border-b border-hair bg-cream/85 backdrop-blur-md" : "border-b border-transparent")}>
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8" aria-label="Main">
        <Logo />
        <div className="hidden items-center gap-8 text-[14px] text-ink-700 md:flex">
          {LINKS.map(([label, href]) => (
            <a key={href} href={href} className="transition hover:text-ink">{label}</a>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Link href="/login" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}>Sign in</Link>
          <a href="#demo" className={buttonVariants({ size: "sm" })}>Request a demo</a>
        </div>
      </nav>
    </header>
  );
}
