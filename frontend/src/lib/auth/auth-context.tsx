"use client";

/**
 * The one place the app decides who is signed in. Components read the user, permissions and workspace from here;
 * none of them store or guess identity themselves.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { fetchMe, signIn, signOut, signUp, type SignupBody } from "@/lib/auth/auth-client";
import { broadcast, hardNavigate, markSigningOut, onAuthMessage } from "@/lib/auth/session";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (body: SignupBody) => Promise<User>;
  /** Re-read the user after a change to their roles or workspace. */
  refresh: () => Promise<void>;
  /** Revoke the session, clear everything and go to sign-in. */
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetchMe()
      .then((u) => alive && setUser(u))
      .catch(() => alive && setUser(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  // Keep every tab on the same session: sign-out anywhere signs out everywhere; a different account signing in
  // elsewhere reloads this tab so it never shows the previous person's data.
  useEffect(() => onAuthMessage((msg) => {
    if (msg.type === "logout" && user) {
      markSigningOut();
      hardNavigate("/login");
    }
    if (msg.type === "login" && user && msg.userId !== user.id) window.location.reload();
  }), [user]);

  // Pages restored from the back/forward cache (e.g. Back after sign-out) re-check the session.
  useEffect(() => {
    const onShow = (e: PageTransitionEvent) => {
      if (e.persisted) window.location.reload();
    };
    window.addEventListener("pageshow", onShow);
    return () => window.removeEventListener("pageshow", onShow);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const u = await signIn(email, password);
    setUser(u);
    broadcast({ type: "login", userId: u.id });
    return u;
  }, []);

  const signup = useCallback(async (body: SignupBody) => {
    const u = await signUp(body);
    setUser(u);
    broadcast({ type: "login", userId: u.id });
    return u;
  }, []);

  const refresh = useCallback(async () => {
    setUser(await fetchMe());
  }, []);

  const logout = useCallback(async () => {
    markSigningOut();
    await signOut();
    // No setUser(null) here: the full navigation below discards all in-memory state, and clearing the user first would
    // let page guards race us with a "/login?next=…" redirect.
    broadcast({ type: "logout" });
    hardNavigate("/login"); // full navigation: no in-memory user, workspace, sidebar or cached data survives
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, signup, refresh, logout, can: (p: string) => !!user?.permissions.includes(p) }),
    [user, loading, login, signup, refresh, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
