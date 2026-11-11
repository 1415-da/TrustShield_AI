"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, getSession, setSession } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getSession()) {
      setLoading(false);
      return;
    }
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => setSession(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<{ access_token: string; refresh_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    setSession({ access_token: res.access_token, refresh_token: res.refresh_token });
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(() => {
    setSession(null);
    setUser(null);
    window.location.href = "/login";
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, logout, can: (p: string) => !!user?.permissions.includes(p) }),
    [user, loading, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Where a user should land after login, based on what they're allowed to do. */
export function homeFor(user: User): string {
  const p = new Set(user.permissions);
  if (p.has("analytics:read")) return "/console";
  if (p.has("reviews:act")) return "/console/reviews";
  if (p.has("assistant:use")) return "/assistant";
  return "/console";
}

export const CONSOLE_PERMISSIONS = ["analytics:read", "policies:read", "reviews:read", "audit:read", "users:manage", "apps:manage", "tests:run", "settings:read", "compliance:read", "agents:read", "integrations:read", "actions:approve"];
