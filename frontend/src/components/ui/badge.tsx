import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11.5px] font-medium leading-5 tracking-[0.01em]",
  {
    variants: {
      tone: {
        neutral: "border-ink/10 bg-ink/[0.04] text-ink-700",
        forest: "border-forest/15 bg-forest-50 text-forest",
        sage: "border-sage/30 bg-sage-100 text-sage-700",
        amber: "border-amber/30 bg-amber-100 text-amber-700",
        crimson: "border-crimson/25 bg-crimson-100 text-crimson-700",
        lilac: "border-lilac-400/60 bg-lilac-200 text-lilac-700",
        ink: "border-ink bg-ink text-cream",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export type BadgeTone = NonNullable<VariantProps<typeof badgeVariants>["tone"]>;

export function Badge({ className, tone, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export function Dot({ className }: { className?: string }) {
  return <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full bg-current", className)} />;
}
