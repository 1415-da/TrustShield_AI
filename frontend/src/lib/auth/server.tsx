/**
 * Server-side session check for protected layouts. Runs on every full page load of `/assistant`, `/workspace` and
 * `/console/*`: asks the API who the session cookie belongs to, redirects to sign-in when there is no valid session,
 * and renders "No access" when the signed-in person's role does not include the page.
 */
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { NoAccess } from "@/components/auth/no-access";
import { canAccess } from "@/lib/auth/permissions";
import type { User } from "@/lib/types";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

export async function getServerUser(): Promise<User | null> {
  const cookieHeader = cookies().getAll().map((c) => `${c.name}=${c.value}`).join("; ");
  if (!cookieHeader.includes("trustshield_access_token=")) return null;
  try {
    const res = await fetch(`${BACKEND}/api/auth/me`, { headers: { cookie: cookieHeader }, cache: "no-store" });
    return res.ok ? ((await res.json()) as User) : null;
  } catch {
    return null;
  }
}

export async function ProtectedArea({ children, fallbackPath }: { children: ReactNode; fallbackPath: string }) {
  const path = headers().get("x-ts-pathname") || fallbackPath;
  const user = await getServerUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(path)}`);
  if (!canAccess(path, user.permissions)) return <NoAccess user={user} />;
  return <>{children}</>;
}
