import Link from "next/link";

import { cn } from "@/lib/utils";

export function ShieldMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("h-7 w-7", className)} aria-hidden>
      <path d="M16 2.5 4.5 7v8.2c0 7.1 4.9 12.4 11.5 14.3 6.6-1.9 11.5-7.2 11.5-14.3V7L16 2.5Z" fill="#034F46" />
      <path d="M16 6.4 8.3 9.4v5.9c0 4.9 3.2 8.6 7.7 10.1 4.5-1.5 7.7-5.2 7.7-10.1V9.4L16 6.4Z" fill="#F0D7FF" />
      <path d="m11.8 15.8 3 3 5.6-6.2" stroke="#034F46" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ href = "/", className, subtle }: { href?: string; className?: string; subtle?: string }) {
  return (
    <Link href={href} className={cn("group inline-flex items-center gap-2.5", className)} aria-label="TrustShield AI home">
      <ShieldMark />
      <span className="whitespace-nowrap font-serif text-[21px] leading-none tracking-[-0.01em]">
        TrustShield<span className="text-forest"> AI</span>
      </span>
      {subtle && <span className="ml-1 hidden rounded-full border border-hair px-2 py-0.5 text-[11px] text-ink-500 sm:inline">{subtle}</span>}
    </Link>
  );
}
