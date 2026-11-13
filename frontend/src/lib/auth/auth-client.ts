/** Every authentication call in the app goes through here. Tokens are set as HTTP-only cookies by the API. */
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export interface SignupBody {
  organization_name: string;
  full_name: string;
  email: string;
  password: string;
  industry?: string;
  size?: string;
}

/** The signed-in user (with workspace, roles and permissions), or null when there is no valid session. */
export async function fetchMe(): Promise<User | null> {
  try {
    return await api<User>("/auth/me", { onUnauthorized: "throw" });
  } catch (e) {
    if ((e as { status?: number }).status === 401) return null;
    throw e;
  }
}

export async function signIn(email: string, password: string): Promise<User> {
  const res = await api<{ user: User }>("/auth/login", { method: "POST", body: { email: email.trim(), password }, auth: false });
  return res.user;
}

export async function signUp(body: SignupBody): Promise<User> {
  const res = await api<{ user: User }>("/orgs/signup", { method: "POST", body, auth: false });
  return res.user;
}

/** Revoke the session on the server and clear its cookies. Never throws: signing out must always work locally. */
export async function signOut(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  } catch {
    /* offline: cookies expire on their own; the server session is revoked on the next sign-in attempt */
  }
}
