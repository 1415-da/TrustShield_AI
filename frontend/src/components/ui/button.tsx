import { cva, type VariantProps } from "class-variance-authority";
import { Children, forwardRef, isValidElement, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-[background,color,box-shadow,transform] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        primary: "bg-forest text-cream shadow-soft hover:bg-forest-900",
        secondary: "border border-ink/15 bg-cream-50 text-ink hover:border-ink/30 hover:bg-white",
        ghost: "text-ink-700 hover:bg-ink/5",
        lilac: "bg-lilac text-ink hover:bg-lilac-400",
        danger: "bg-crimson text-cream hover:bg-crimson-700",
        link: "rounded-none px-0 text-forest underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3.5 text-[13px]",
        md: "h-10 px-5 text-sm",
        lg: "h-12 px-7 text-[15px]",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

/** Plain-text content of a label, used to give each distinct label its own DOM nodes. */
function labelText(node: ReactNode): string {
  return Children.toArray(node).map((c) => (typeof c === "string" || typeof c === "number" ? String(c)
    : isValidElement<{ children?: ReactNode }>(c) ? labelText(c.props.children) : "")).join("");
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, loading, children, disabled, ...props },
  ref,
) {
  return (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} disabled={disabled || loading} {...props}>
      {loading && <span aria-hidden className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" />}
      {/* Keyed by the label text: when a label changes (Approve → Send edited answer) React draws new text
          instead of editing the old node, which page translators may have replaced and would leave stale. */}
      <span key={labelText(children)} className="contents">{children}</span>
    </button>
  );
});

export { buttonVariants };
