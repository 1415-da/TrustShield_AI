/**
 * TrustShield API client. Every call goes to same-origin /api/* (proxied to the gateway).
 * There is intentionally no code path from the browser to an LLM provider.
 */

import { broadcast, csrfToken, hardNavigate, isSigningOut } from "@/lib/auth/session";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string | null,
    public details?: { field?: string | null; message?: string }[],
  ) {
    super(message);
  }
}

/** One status → message table for the whole app. Server messages are written to be shown to people, so they are
 * used when present; server errors and network failures always get the generic copy. */
const STATUS_MESSAGES: Record<number, string> = {
  0: "Can't reach TrustShield. Check your connection and try again.",
  401: "Your session has expired. Please sign in again.",
  403: "You do not have permission to perform this action.",
  404: "This item could not be found.",
  409: "This action conflicts with an existing record.",
  422: "Some fields need attention.",
  429: "Too many requests. Please try again shortly.",
  500: "Something went wrong. Please try again.",
};

export function messageFor(status: number, serverMessage?: string | null): string {
  if (status >= 500) return STATUS_MESSAGES[500];
  return serverMessage || STATUS_MESSAGES[status] || STATUS_MESSAGES[500];
}

let refreshing: Promise<boolean> | null = null;

/** Mint a new access token from the refresh cookie. Concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const res = await fetch("/api/auth/refresh", { method: "POST", credentials: "same-origin" });
      return res.ok;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

/** The session is gone: tell other tabs and go to sign-in, returning here afterwards. */
export function sessionEnded(): void {
  if (typeof window === "undefined" || window.location.pathname.startsWith("/login") || isSigningOut()) return;
  broadcast({ type: "logout" });
  hardNavigate(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  /** Send the session cookie and handle expiry (default true). */
  auth?: boolean;
  /** On a 401 after refresh fails: "redirect" to sign-in (default) or just "throw". */
  onUnauthorized?: "redirect" | "throw";
  signal?: AbortSignal;
}

export async function api<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const { method = "GET", body, form, auth = true, onUnauthorized = "redirect", signal } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const csrf = csrfToken();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "NETWORK_ERROR", STATUS_MESSAGES[0]);
  }

  if (res.status === 401 && auth && !retried && (await refreshSession())) {
    return api<T>(path, opts, true);
  }
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const e = ((data as { error?: Record<string, unknown> } | null)?.error ?? {}) as {
      code?: string; message?: string; request_id?: string; details?: ApiError["details"];
    };
    if (res.status === 401 && auth && onUnauthorized === "redirect") sessionEnded();
    throw new ApiError(res.status, e.code ?? "ERROR", messageFor(res.status, e.message), e.request_id, e.details ?? []);
  }
  return data as T;
}

/** File download through the session cookie (saved with the server-provided file name). */
export async function download(path: string, fallbackName: string): Promise<void> {
  let res = await fetch(`/api${path}`, { credentials: "same-origin", cache: "no-store" });
  if (res.status === 401 && (await refreshSession())) res = await fetch(`/api${path}`, { credentials: "same-origin", cache: "no-store" });
  if (res.status === 401) sessionEnded();
  if (!res.ok) throw new ApiError(res.status, "DOWNLOAD_FAILED", "Export failed. Please try again.");
  const disposition = res.headers.get("content-disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
