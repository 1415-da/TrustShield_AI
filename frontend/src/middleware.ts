/**
 * First line of route protection (the server layouts and the API are the authoritative checks).
 *
 * * Protected pages without a session → `/login?next=<original path>`.
 * * An expired access cookie with a live refresh cookie is renewed here, before the page renders, so a person who
 *   was idle never sees a spurious sign-in screen.
 * * Protected pages are sent with `Cache-Control: no-store`, so Back after sign-out can't show them from cache.
 */
import { NextResponse, type NextRequest } from "next/server";

const ACCESS = "trustshield_access_token";
const REFRESH = "trustshield_refresh_token";
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";
const SECURE = process.env.COOKIE_SECURE === "true";

function expiresSoon(jwt: string | undefined): boolean {
  if (!jwt) return true;
  try {
    const payload = JSON.parse(atob(jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp !== "number" || payload.exp * 1000 < Date.now() + 15_000;
  } catch {
    return true;
  }
}

function toLogin(req: NextRequest): NextResponse {
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(req.nextUrl.pathname + req.nextUrl.search)}`;
  const res = NextResponse.redirect(url);
  res.cookies.delete(ACCESS);
  return res;
}

function withPath(req: NextRequest, cookieHeader?: string): Headers {
  const h = new Headers(req.headers);
  h.set("x-ts-pathname", req.nextUrl.pathname);
  if (cookieHeader !== undefined) h.set("cookie", cookieHeader);
  return h;
}

function noStore(res: NextResponse): NextResponse {
  res.headers.set("Cache-Control", "no-store, max-age=0");
  return res;
}

export async function middleware(req: NextRequest) {
  const access = req.cookies.get(ACCESS)?.value;
  const refresh = req.cookies.get(REFRESH)?.value;

  if (!expiresSoon(access)) return noStore(NextResponse.next({ request: { headers: withPath(req) } }));
  if (!refresh) return toLogin(req);

  try {
    const r = await fetch(`${BACKEND}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-forwarded-for": req.headers.get("x-forwarded-for") ?? "" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
    if (!r.ok) return toLogin(req);
    const data = (await r.json()) as { access_token: string; expires_in: number };
    // Forward the renewed token to this render, and set it in the browser for the requests that follow.
    const others = req.cookies.getAll().filter((c) => c.name !== ACCESS).map((c) => `${c.name}=${c.value}`);
    const res = NextResponse.next({ request: { headers: withPath(req, [...others, `${ACCESS}=${data.access_token}`].join("; ")) } });
    res.cookies.set(ACCESS, data.access_token, { httpOnly: true, sameSite: "lax", secure: SECURE, path: "/", maxAge: data.expires_in });
    return noStore(res);
  } catch {
    return toLogin(req);
  }
}

export const config = {
  matcher: ["/assistant/:path*", "/workspace/:path*", "/console/:path*"],
};
