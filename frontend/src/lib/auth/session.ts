/**
 * Browser-side session helpers. The session itself lives in HTTP-only cookies set by the API — this module never
 * sees a token. It only reads the (non-secret) CSRF cookie, validates redirect targets, and keeps tabs in sync.
 */

export const CSRF_COOKIE = "trustshield_csrf";

export function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE}=([^;]+)`));
  return m ? decodeURIComponent(m[1]) : null;
}

/** Only same-site, in-app paths are valid post-login destinations (prevents open redirects such as `//evil.com`). */
export function safeNext(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return null;
  if (/^\/(login|signup)(\/|\?|$)/.test(next)) return null;
  return next;
}

type AuthMessage = { type: "login"; userId: number } | { type: "logout" };
const CHANNEL = "trustshield-auth";

/** Tell every other open tab that the session changed. */
export function broadcast(msg: AuthMessage): void {
  try {
    const ch = new BroadcastChannel(CHANNEL);
    ch.postMessage(msg);
    ch.close();
  } catch {
    /* BroadcastChannel unavailable — other tabs catch up on their next API call (401 → sign-in). */
  }
}

export function onAuthMessage(handler: (msg: AuthMessage) => void): () => void {
  try {
    const ch = new BroadcastChannel(CHANNEL);
    ch.onmessage = (e) => handler(e.data as AuthMessage);
    return () => ch.close();
  } catch {
    return () => undefined;
  }
}

let leaving = false;

/** Sign-out is in progress: requests that fail because the session was just revoked must not redirect elsewhere. */
export function markSigningOut(): void {
  leaving = true;
}

export function isSigningOut(): boolean {
  return leaving;
}

/** Leave the app with a full document navigation so no in-memory user, workspace or cached data survives. */
export function hardNavigate(path: string, replace = true): void {
  if (replace) window.location.replace(path);
  else window.location.assign(path);
}
