"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError, getSession, setSession } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (body: SignupBody) => Promise<User>;
  refresh: () => Promise<void>;
  logout: () => void;
  can: (permission: string) => boolean;
}

export interface SignupBody {
  organization_name: string;
  full_name: string;
  email: string;
  password: string;
  industry?: string;
  size?: string;
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
      .catch((err) => {
        // Only a rejected token ends the session. A request cancelled by navigation or a network blip must not
        // sign the person out.
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) setSession(null);
      })
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

  const signup = useCallback(async (body: SignupBody) => {
    const res = await api<{ access_token: string; refresh_token: string; user: User }>("/orgs/signup", {
      method: "POST",
      body,
      auth: false,
    });
    setSession({ access_token: res.access_token, refresh_token: res.refresh_token });
    setUser(res.user);
    return res.user;
  }, []);

  const refresh = useCallback(async () => {
    setUser(await api<User>("/auth/me"));
  }, []);

  const logout = useCallback(() => {
    setSession(null);
    setUser(null);
    window.location.href = "/login";
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

/** Where a user should land after login, based on what they're allowed to do. */
export function homeFor(user: User): string {
  const p = new Set(user.permissions);
  if (p.has("analytics:read")) return "/console";
  if (p.has("reviews:act")) return "/console/reviews";
  if (p.has("assistant:use")) return "/assistant";
  return "/console";
}

export const CONSOLE_PERMISSIONS = ["analytics:read", "policies:read", "reviews:read", "audit:read", "users:manage", "apps:manage", "tests:run", "settings:read", "compliance:read", "agents:read", "integrations:read", "actions:approve"];
