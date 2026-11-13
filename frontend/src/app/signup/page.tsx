"use client";

import { CheckCircle2, Lock } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";
import { hardNavigate } from "@/lib/auth/session";

const INCLUDED = [
  "14 baseline policies enforcing from minute one — injection, PII, cards, credentials, exfiltration",
  "Governed assistant and team channels with per-channel policy profiles",
  "Agent action approval rules for finance, HR, IT and destructive actions",
  "Human review queue, Policy Studio with two-person approval, and the Test Center",
  "Hash-chained audit log and Compliance Evidence Center",
  "Guard API keys to put TrustShield in front of your own LLM apps",
];

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;
type FormKey = "organization_name" | "full_name" | "email" | "password" | "industry" | "size";
const FIELD_IDS: Record<string, string> = { organization_name: "org", full_name: "name", email: "email", password: "password" };

function validate(f: Record<FormKey, string>): Partial<Record<FormKey, string>> {
  const e: Partial<Record<FormKey, string>> = {};
  if (f.organization_name.trim().length < 2) e.organization_name = "Enter your organization's name (at least 2 characters).";
  if (f.full_name.trim().length < 2) e.full_name = "Enter your name.";
  if (!EMAIL_RE.test(f.email.trim())) e.email = "Enter a valid work email address.";
  if (f.password.length < 10) e.password = "Use a password of at least 10 characters.";
  return e;
}

export default function SignupPage() {
  const { signup } = useAuth();
  const [form, setForm] = useState<Record<FormKey, string>>({ organization_name: "", full_name: "", email: "", password: "", industry: "", size: "" });
  const [errors, setErrors] = useState<Partial<Record<FormKey, string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: FormKey) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const describe = (k: FormKey) => (errors[k] ? { "aria-invalid": true, "aria-describedby": `${FIELD_IDS[k]}-error` } : {});

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const v = validate(form);
    setErrors(v);
    setError(null);
    if (Object.keys(v).length) return;
    setBusy(true);
    try {
      await signup({ ...form, email: form.email.trim(), organization_name: form.organization_name.trim(), full_name: form.full_name.trim() });
      hardNavigate("/console/setup"); // stays busy until the workspace opens
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && err.details?.length) {
        const mapped: Partial<Record<FormKey, string>> = {};
        for (const d of err.details) if (d.field && d.field in FIELD_IDS) mapped[d.field as FormKey] = d.message ?? "Check this field.";
        setErrors(mapped);
      }
      setError(err instanceof ApiError ? err.message : "We couldn't create your workspace. Please try again.");
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <main id="main" className="flex flex-col px-6 py-8 sm:px-12">
        <Logo />
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <h1 className="text-[40px] leading-tight">Create workspace</h1>
          <p className="mt-2 text-ink-500">An isolated, governed AI workspace for your organization. You&apos;ll be its first admin.</p>
          <form onSubmit={submit} className="mt-8 grid gap-4 sm:grid-cols-2" aria-label="Create workspace" noValidate>
            <Field label="Organization name" htmlFor="org" className="sm:col-span-2" error={errors.organization_name}>
              <Input id="org" required minLength={2} maxLength={120} value={form.organization_name} onChange={set("organization_name")} placeholder="Acme Logistics" autoComplete="organization" disabled={busy} {...describe("organization_name")} />
            </Field>
            <Field label="Your name" htmlFor="name" error={errors.full_name}>
              <Input id="name" required minLength={2} value={form.full_name} onChange={set("full_name")} autoComplete="name" disabled={busy} {...describe("full_name")} />
            </Field>
            <Field label="Work email" htmlFor="email" error={errors.email}>
              <Input id="email" type="email" required value={form.email} onChange={set("email")} autoComplete="email" placeholder="you@company.com" disabled={busy} {...describe("email")} />
            </Field>
            <Field label="Password" htmlFor="password" className="sm:col-span-2" error={errors.password}>
              <Input id="password" type="password" required minLength={10} value={form.password} onChange={set("password")} autoComplete="new-password" placeholder="At least 10 characters" disabled={busy} {...describe("password")} />
            </Field>
            <Field label="Industry" htmlFor="industry">
              <Select id="industry" value={form.industry} onChange={set("industry")}>
                <option value="">Select…</option>
                {["Financial services", "Healthcare", "Technology", "Manufacturing", "Retail", "Logistics", "Public sector", "Professional services", "Other"].map((o) => <option key={o}>{o}</option>)}
              </Select>
            </Field>
            <Field label="Company size" htmlFor="size">
              <Select id="size" value={form.size} onChange={set("size")}>
                <option value="">Select…</option>
                {["1–200", "200–1,000", "1,000–5,000", "5,000+"].map((o) => <option key={o}>{o}</option>)}
              </Select>
            </Field>
            {error && <div className="sm:col-span-2"><ErrorState message={error} /></div>}
            <Button type="submit" size="lg" className="sm:col-span-2" loading={busy} data-testid="create-workspace-submit">{busy ? "Creating workspace…" : "Create workspace"}</Button>
          </form>
          <p className="mt-5 flex items-center gap-2 text-[12.5px] text-ink-500"><Lock className="h-3.5 w-3.5" />Your workspace&apos;s data is isolated from every other organization.</p>
          <p className="mt-6 text-[13.5px] text-ink-700">Already have an account? <Link href="/login" className="link">Sign in</Link> · <Link href="/demo" className="link">Live demo</Link></p>
        </div>
      </main>
      <aside className="relative hidden overflow-hidden bg-forest px-12 py-10 text-cream lg:flex lg:flex-col lg:justify-center" aria-label="What's included">
        <div aria-hidden className="absolute -right-24 top-10 h-80 w-80 rounded-full bg-lilac/20 blur-3xl" />
        <div className="relative max-w-md">
          <p className="eyebrow text-cream/60">Included in every workspace</p>
          <h2 className="mt-3 text-[34px] leading-tight text-cream">Protected on day one. Yours to tune.</h2>
          <ul className="mt-8 space-y-3.5">
            {INCLUDED.map((t) => (
              <li key={t} className="flex gap-3 text-[14.5px] text-cream/85"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-lilac" />{t}</li>
            ))}
          </ul>
          <p className="mt-10 text-[12.5px] text-cream/55">Baseline policies are approved by the TrustShield baseline pack. Every change you make afterwards needs a second, human approver.</p>
        </div>
      </aside>
    </div>
  );
}
