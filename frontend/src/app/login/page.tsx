"use client";

import { ArrowRight, Lock } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";
import { homeFor, useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";
import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/demo-accounts";
import Link from "next/link";



function LoginForm() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace(params.get("next") || homeFor(user));
  }, [loading, user, router, params]);

  const submit = async (e?: FormEvent, override?: { email: string; password: string }) => {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(override?.email ?? email, override?.password ?? password);
      router.replace(params.get("next") || homeFor(u));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed. Please try again.");
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      <main id="main" className="flex flex-col px-6 py-8 sm:px-12">
        <Logo />
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <h1 className="text-[40px] leading-tight">Sign in</h1>
          <p className="mt-2 text-ink-500">to your organization&apos;s TrustShield workspace.</p>
          <form onSubmit={submit} className="mt-8 space-y-4" aria-label="Sign in">
            <Field label="Work email" htmlFor="email">
              <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
            </Field>
            <Field label="Password" htmlFor="password">
              <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            {error && <ErrorState message={error} />}
            <Button type="submit" className="w-full" size="lg" loading={busy}>Continue</Button>
          </form>
          <p className="mt-6 flex items-center gap-2 text-[12.5px] text-ink-500"><Lock className="h-3.5 w-3.5" /> Sessions use short-lived tokens. All activity is audited.</p>
          <p className="mt-4 text-[13.5px] text-ink-700">New to TrustShield? <Link href="/signup" className="link">Create a workspace</Link></p>
          <div className="mt-10 lg:hidden" aria-label="Demo accounts">
            <p className="eyebrow mb-3">Live demo · NovaCorp</p>
            <div className="flex flex-wrap gap-2">
              {DEMO_ACCOUNTS.map((a) => (
                <button key={a.email} onClick={() => void submit(undefined, { email: a.email, password: DEMO_PASSWORD })}
                  className="rounded-full border border-hair bg-cream-50 px-3 py-1.5 text-[12.5px] transition hover:border-forest/40">
                  {a.role}
                </button>
              ))}
            </div>
          </div>
        </div>
      </main>

      <aside className="relative hidden overflow-hidden bg-forest px-12 py-10 text-cream lg:flex lg:flex-col lg:justify-center" aria-label="Demo accounts">
        <div aria-hidden className="absolute -right-24 top-10 h-80 w-80 rounded-full bg-lilac/20 blur-3xl" />
        <div className="relative max-w-md">
          <p className="eyebrow text-cream/60">Live demo · NovaCorp workspace</p>
          <h2 className="mt-3 text-[34px] leading-tight text-cream">Explore as any role at NovaCorp.</h2>
          <p className="mt-3 text-[14px] text-cream/75">Each account shows TrustShield from a different seat: the employee asking, the reviewer deciding, the admin governing, the auditor checking.</p>
          <ul className="mt-8 space-y-2">
            {DEMO_ACCOUNTS.map((a) => (
              <li key={a.email}>
                <button
                  onClick={() => { setEmail(a.email); setPassword(DEMO_PASSWORD); void submit(undefined, { email: a.email, password: DEMO_PASSWORD }); }}
                  className="group flex w-full items-center justify-between rounded-2xl border border-cream/15 bg-cream/[0.04] px-4 py-3 text-left transition hover:border-cream/35 hover:bg-cream/[0.08]"
                  data-testid={`demo-${a.role.toLowerCase().replace(/[^a-z]+/g, "-")}`}
                >
                  <span>
                    <span className="block text-[14.5px] font-medium">{a.name} <span className="font-normal text-cream/60">· {a.role}</span></span>
                    <span className="block text-[12.5px] text-cream/60">{a.note}</span>
                  </span>
                  <ArrowRight className="h-4 w-4 text-lilac opacity-60 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-6 text-[12px] text-cream/50">Workspace password: <code className="font-mono text-cream/80">{DEMO_PASSWORD}</code></p>
        </div>
      </aside>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
