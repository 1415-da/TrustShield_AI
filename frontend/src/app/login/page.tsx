"use client";

import { Lock, LogIn } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState, type FormEvent } from "react";

import { Logo } from "@/components/brand/logo";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";
import { useAuth } from "@/lib/auth/auth-context";
import { canAccess, homeFor } from "@/lib/auth/permissions";
import { hardNavigate, safeNext } from "@/lib/auth/session";
import { ApiError } from "@/lib/api";
import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/demo-accounts";
import { ROLE_LABELS } from "@/lib/roles";
import type { User } from "@/lib/types";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

/** Where to go after sign-in: the requested page if it is a safe in-app path this person may open, else their home. */
function destination(user: User, next: string | null): string {
  const target = safeNext(next);
  return target && canAccess(target, user.permissions) ? target : homeFor(user);
}

function LoginForm() {
  const { login, logout, user, loading } = useAuth();
  const params = useSearchParams();
  const next = params.get("next");
  const prefill = DEMO_ACCOUNTS.find((a) => a.email === params.get("account"));
  const [email, setEmail] = useState(prefill?.email ?? "");
  const [password, setPassword] = useState(prefill ? DEMO_PASSWORD : "");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);
  const submitRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (prefill) submitRef.current?.focus();
  }, [prefill]);

  const fill = (a: (typeof DEMO_ACCOUNTS)[number]) => {
    setEmail(a.email);
    setPassword(DEMO_PASSWORD);
    setFieldErrors({});
    setError(null);
    submitRef.current?.focus();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const errs: typeof fieldErrors = {};
    if (!EMAIL_RE.test(email.trim())) errs.email = "Enter a valid work email address.";
    if (!password) errs.password = "Enter your password.";
    setFieldErrors(errs);
    setError(null);
    if (errs.email || errs.password) return;
    setBusy(true);
    try {
      const u = await login(email, password);
      hardNavigate(destination(u, next)); // stays busy ("Signing in…") until the next page loads
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null;
      setError(apiErr?.message ?? "Sign-in failed. Please try again.");
      if (apiErr?.code === "INVALID_CREDENTIALS") {
        setPassword("");
        passwordRef.current?.focus();
      }
      setBusy(false);
    }
  };

  // Already signed in: never continue silently as whoever used this browser last — say who it is and let them choose.
  if (!loading && user) {
    return (
      <Shell>
        <div className="panel p-6" data-testid="already-signed-in">
          <p className="eyebrow">Already signed in</p>
          <p className="mt-2 text-[17px] font-medium">{user.full_name}</p>
          <p className="text-[13.5px] text-ink-500">{user.email} · {ROLE_LABELS[user.primary_role] ?? user.primary_role}{user.organization ? ` · ${user.organization.name}` : ""}</p>
          <div className="mt-5 flex flex-col gap-2">
            <button type="button" onClick={() => hardNavigate(destination(user, next))} className={buttonVariants({ size: "lg" })} data-testid="continue-session">
              Continue as {user.full_name.split(" ")[0]}
            </button>
            <button type="button" onClick={() => void logout()} className={buttonVariants({ variant: "secondary", size: "lg" })} data-testid="switch-account">
              Sign out and use another account
            </button>
          </div>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <form onSubmit={submit} className="space-y-4" aria-label="Sign in" noValidate>
        <Field label="Work email" htmlFor="email" error={fieldErrors.email}>
          <Input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com"
            aria-invalid={!!fieldErrors.email} aria-describedby={fieldErrors.email ? "email-error" : undefined} disabled={busy} />
        </Field>
        <Field label="Password" htmlFor="password" error={fieldErrors.password}>
          <Input id="password" ref={passwordRef} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!fieldErrors.password} aria-describedby={fieldErrors.password ? "password-error" : error ? "login-error" : undefined} disabled={busy} />
        </Field>
        {error && <div id="login-error"><ErrorState message={error} /></div>}
        <Button ref={submitRef} type="submit" className="w-full" size="lg" loading={busy} data-testid="sign-in-submit">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="mt-6 flex items-center gap-2 text-[12.5px] text-ink-500"><Lock className="h-3.5 w-3.5" /> Secure, HTTP-only session. All activity is audited.</p>
      <p className="mt-4 text-[13.5px] text-ink-700">New to TrustShield? <Link href="/signup" className="link">Create workspace</Link></p>

      <section className="mt-10 rounded-2xl border border-hair bg-cream-50/70 p-4" aria-labelledby="demo-accounts-title">
        <p id="demo-accounts-title" className="eyebrow">Live demo · NovaCorp accounts</p>
        <p className="mt-1 text-[12.5px] text-ink-500">Choosing an account fills in the form. You still sign in yourself. Password: <code className="font-mono">{DEMO_PASSWORD}</code></p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {DEMO_ACCOUNTS.map((a) => (
            <button key={a.email} type="button" onClick={() => fill(a)} disabled={busy}
              className="rounded-full border border-hair bg-white/70 px-3 py-1.5 text-[12.5px] transition hover:border-forest/40 disabled:opacity-50"
              aria-label={`Fill in ${a.name}, ${a.role}`} data-testid={`fill-${a.roleKey}`}>
              {a.role}
            </button>
          ))}
        </div>
      </section>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main id="main" className="flex min-h-screen flex-col px-6 py-8 sm:px-12">
      <Logo />
      <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
        <h1 className="flex items-center gap-3 text-[40px] leading-tight"><LogIn className="h-7 w-7 text-forest" />Sign in</h1>
        <p className="mb-8 mt-2 text-ink-500">to your organization&apos;s TrustShield workspace.</p>
        {children}
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
