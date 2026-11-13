import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const base =
  "w-full rounded-xl border border-ink/15 bg-white/70 px-3.5 text-[14px] text-ink placeholder:text-ink-400 transition focus:border-forest focus:bg-white focus:outline-none focus:ring-2 focus:ring-forest/15 disabled:opacity-60";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...p }, ref) {
  return <input ref={ref} className={cn(base, "h-10", className)} {...p} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...p }, ref) {
  return <textarea ref={ref} className={cn(base, "py-2.5 leading-relaxed", className)} {...p} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...p }, ref) {
  return (
    <select ref={ref} className={cn(base, "h-10 appearance-none bg-[length:12px] bg-[right_0.9rem_center] bg-no-repeat pr-9", className)}
      style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%231A1A1A' stroke-width='1.5' fill='none'/%3E%3C/svg%3E\")" }}
      {...p}>
      {children}
    </select>
  );
});

/** Label + control + hint + field error. The error renders as `<id>-error`; point the control's aria-describedby at it. */
export function Field({ label, hint, htmlFor, error, children, className }: { label: string; hint?: ReactNode; htmlFor?: string; error?: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-[12.5px] font-medium text-ink-700">{label}</label>
      {children}
      {error && <p id={htmlFor ? `${htmlFor}-error` : undefined} role="alert" className="text-[12px] font-medium leading-snug text-crimson-700">{error}</p>}
      {hint && !error && <p className="text-[12px] leading-snug text-ink-500">{hint}</p>}
    </div>
  );
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-[22px] w-[38px] shrink-0 items-center rounded-full border transition disabled:opacity-50",
        checked ? "border-forest bg-forest" : "border-ink/20 bg-ink/10",
      )}
    >
      <span className={cn("inline-block h-4 w-4 rounded-full bg-cream shadow transition-transform", checked ? "translate-x-[18px]" : "translate-x-[2px]")} />
    </button>
  );
}

export function Checkbox({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; disabled?: boolean }) {
  return (
    <label className={cn("flex cursor-pointer items-start gap-2.5 text-[13.5px]", disabled && "cursor-not-allowed opacity-60")}>
      <input type="checkbox" className="mt-0.5 h-4 w-4 rounded border-ink/30 accent-forest" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}
