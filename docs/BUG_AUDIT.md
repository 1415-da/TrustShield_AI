# TrustShield AI — Authentication, Navigation & Consistency Bug Audit

**Scope:** frontend (Next.js App Router) and backend (FastAPI) authentication, sessions, routing, roles, workspace
resolution, navigation, interaction patterns and error handling.
**Method:** code reading of the full auth path (`backend/app/api/auth.py`, `core/security.py`, `core/deps.py`,
`core/tenancy.py`, `core/errors.py`, `frontend/src/hooks/useAuth.tsx`, `lib/api.ts`, `app/login`, `app/demo`, all
shells and pages), plus a crawler that signed in as five roles and recorded every link (label → destination) and
every 404.
**Status column:** each finding is fixed in the phase noted; see "Resolution" at the end.

Severity: **S1** security / wrong account, **S2** wrong behaviour, **S3** inconsistency / polish.

---

## 1. Authentication bugs

| ID | Sev | Location | Current behaviour | Expected | Root cause | Fix plan | Test |
|---|---|---|---|---|---|---|---|
| AUTH-1 | S1 | `frontend/src/app/login/page.tsx` `LoginForm` `useEffect` (redirect when `user`) | Opening **Sign in** silently forwards the visitor into whichever account was last used in this browser (often a persona clicked days earlier). This is the reported "already-set-up username" bug. | Visiting `/login` while signed in must never silently continue as a previous account. Show who is signed in, with *Continue* or *Sign out and use another account*. A `next=` return from a protected page may continue directly. | Session tokens persist in `localStorage` (AUTH-3) and the login page auto-redirects on any stored session. | Cookie session (AUTH-3) + explicit "already signed in" interstitial. | PW: login page with an existing session shows the interstitial, not a redirect. |
| AUTH-2 | S1 | `login/page.tsx` aside + mobile chips; `app/demo/page.tsx` `enter()` | Persona buttons sign in **with one click** (they call `login()` immediately). | No automatic persona login. Demo accounts are a clearly labelled helper that **fills the form**; the person presses *Sign in*. | Convenience shortcut wired straight to `login()`. | Personas link to `/login?account=…`, which pre-fills the form only. | PW: clicking a persona does not authenticate; the URL stays on `/login`. |
| AUTH-3 | S1 | `frontend/src/lib/api.ts` `getSession`/`setSession` | Access **and refresh** JWTs stored in `localStorage` (readable by any script, persist across browser restarts and are shared by all tabs). | HTTP-only cookies: `trustshield_access_token`, `trustshield_refresh_token`; no tokens in JS. | Original SPA design. | Backend sets/clears cookies; frontend sends `credentials: "same-origin"` and never sees tokens. | BE: login sets HttpOnly cookies; PW: `localStorage` has no token after login. |
| AUTH-4 | S1 | `backend/app/api/auth.py` (no `/logout`) | Sign-out only deletes tokens in the browser; the refresh token stays valid for 7 days and the access token for 30 minutes. | Logout revokes the server-side session; every token of that session is rejected immediately. | No server-side session record. | `auth_sessions` table; access + refresh tokens carry `sid`; `/auth/logout` revokes; `get_current_user` checks the session. | BE: after logout, the old access and refresh tokens return 401. |
| AUTH-5 | S2 | `core/security.py` `create_token`/`decode_token` | JWTs carry no `iss`/`aud`; decode does not require them. | Validate signature, `exp`, `iss`, `aud`, `type`, `sid`. | Minimal JWT setup. | Add `iss`/`aud` claims and `require=[…]` on decode. | BE: tokens with wrong `iss`/`aud`, expired, malformed → 401. |
| AUTH-6 | S2 | `auth.py` `/refresh` | A refresh token isn't bound to anything server-side, so a stolen one works until it expires, even after sign-out. | Refresh only works while the session is live; sign-out or deactivation ends it at once. | No session store. | Bind refresh to the server session (`sid`), checked on every refresh. **Decision:** no per-use rotation. Concurrent page loads would race a rotating token and log people out, and server-side revocation already gives immediate invalidation. | BE: refresh after logout → 401. |
| AUTH-7 | S1 | `auth.py` `/register` | Anyone can self-register an Employee account **inside the NovaCorp workspace** (the default org). | Accounts are created only by creating a workspace (`/orgs/signup`) or by an admin adding a person. | Legacy endpoint from the single-tenant MVP; `allow_self_registration=True` by default. | Remove the endpoint (410-style 404) and the setting. | BE: `/auth/register` is gone. |
| AUTH-8 | S2 | `auth.py` `/login` | No brute-force protection. | Rate limit by client and by email; 429 with a standard message. | Missing. | Reuse the in-memory limiter used by signup/playground. | BE: 11th failed attempt in a minute → 429. |
| AUTH-9 | S1 | `login/page.tsx` `router.replace(params.get("next") …)` | Open redirect: `/login?next=//evil.example` navigates off-site after login. | Only same-site relative paths are honoured. | `next` used unvalidated. | `safeNext()` helper: must start with `/`, not `//` or `/\`, not `/login`. | PW + unit: `next=//evil` lands on the role home. |

## 2. Session-management bugs

| ID | Sev | Location | Current | Expected | Root cause | Fix | Test |
|---|---|---|---|---|---|---|---|
| SESS-1 | S2 | `hooks/useAuth.tsx` `logout()` | Clears local storage and hard-navigates; nothing tells the server; other tabs stay signed in until they next call the API. | Server revocation, cookies cleared, all tabs notified. | No logout endpoint, no cross-tab signal. | `POST /auth/logout` + `BroadcastChannel("trustshield-auth")`; other tabs go to `/login`. | PW: two tabs, sign out in one → the other lands on `/login`. |
| SESS-2 | S2 | Protected pages | After sign-out, the browser **Back** button can restore the previous signed-in page from the back/forward cache. | Back after sign-out must not show protected content. | Pages cacheable; no `pageshow` handling. | `Cache-Control: no-store` on app routes + `pageshow` reload guard. | PW: sign out, go back → login. |
| SESS-3 | S2 | `useAuth.tsx` initial `/auth/me` | A **403** from `/auth/me` deletes the session (403 means "not allowed", not "not signed in"). | Only 401 ends a session. | Over-broad condition. | Session state comes from the cookie-backed `/auth/me`; 401 ⇒ signed out. | Covered by session tests. |
| SESS-4 | S3 | `login`/`signup` | Signing in as a second account in another tab leaves the first tab showing the first user's data. | Tabs follow the current session. | No cross-tab sync. | Broadcast `login` events; other tabs reload. | PW (cross-tab). |
| SESS-5 | S2 | `useAuth.tsx` | `loading` gate renders protected shells client-side before the session is known (flash of skeleton, then redirect). | Unauthenticated requests are redirected before any protected page renders. | No middleware. | `middleware.ts` + server-side session check in protected layouts. | PW: `/console/policies` signed out → `/login?next=/console/policies` with no protected content in the HTML. |

## 3. Routing bugs

| ID | Sev | Location | Current | Expected | Fix |
|---|---|---|---|---|---|
| ROUTE-1 | S2 | No `middleware.ts` | Protected routes are only guarded by client effects. | Middleware redirect + authoritative server check. | Add middleware and server layouts for `/assistant`, `/workspace`, `/console/*`. |
| ROUTE-2 | S2 | `components/console/shell.tsx` | Any signed-in user with *some* console permission can open **any** console URL (e.g. an approver opening `/console/users`); the page then shows raw 403 API errors. | Route-level permission check with a proper "No access" page. | One `ROUTE_ACCESS` table used by the sidebar, the server guard and the client guard. |
| ROUTE-3 | S3 | `landing/nav.tsx` "Open workspace" → `/console` | Signed-in employees are sent to `/console`, then bounced to `/assistant`. | "Open app" goes to the person's role home. | Use `homeFor(user)`. |

## 4. Role-based access bugs

| ID | Sev | Location | Current | Expected | Fix |
|---|---|---|---|---|---|
| ROLE-1 | S2 | `core/deps.py` `require_permission` | 403s are not audited; message leaks internal scope names ("Missing permission: users:manage"). | Unauthorized attempts are audited; the message is user-friendly; the code is `AUTHORIZATION_DENIED`. | Audit `auth.access_denied` with the permission; standard message. |
| ROLE-2 | S3 | `frontend` page-level `can()` checks | Each page re-implements its own permission logic. | Shared `ROUTE_ACCESS` + `RoleGate`. | Central `lib/auth/permissions.ts`. |

## 5. Workspace-selection bugs

| ID | Sev | Location | Current | Expected | Fix / decision |
|---|---|---|---|---|---|
| WS-1 | S1 | `core/tenancy.py` `org_id()` | Any request-scoped DB session that has not been bound to an organization **silently reads and writes NovaCorp (org 1)**. Today this is reachable via `/auth/register` (AUTH-7), failed-login audit events, and the Slack webhooks. | Request sessions must declare their workspace explicitly; an unscoped tenant query is a server error, never a fallback. | `get_db` marks request sessions as `org_required`; public NovaCorp endpoints and Slack webhooks call `use_org(DEFAULT_ORG_ID)` explicitly. |
| WS-2 | — | Data model | An account (email) belongs to exactly **one** workspace; emails are globally unique and `/orgs/signup` rejects an existing email. | Multi-workspace users must choose explicitly. | **Decision:** multi-workspace membership doesn't exist in this product, and adding it would be a new feature (out of scope). The workspace is resolved **server-side from the account** on every request. It's returned by `/auth/me` and shown in the sidebar, with no client-side guessing and no fallback. The selection screen isn't needed because the case can't occur; documented in the README. |

## 6. Navigation inconsistencies (crawler output)

| ID | Label | Destinations found | Expected | Fix |
|---|---|---|---|---|
| NAV-1 | TrustShield logo | `/` (site), `/assistant` (assistant), `/console` (console) | Site logo → `/`; in-app logo → the person's role home | `Logo` in app shells uses `homeFor(user)` |
| NAV-2 | "Open workspace" | `/workspace` (Slack & workspace page), `/console` (marketing nav) | One meaning per label | `/workspace` is always "Connected workspace"; the marketing nav says "Open app" |
| NAV-3 | "Team channels" / "Connected workspace" | both `/workspace` | One label | "Connected workspace" everywhere |
| NAV-4 | "Open assistant" (console) / "Assistant" | `/assistant` | One label | "Assistant" (chat icon, not a key icon) |
| NAV-5 | "Create workspace" / "Create a workspace" / "Create your workspace" | `/signup` | One label | "Create workspace" |
| NAV-6 | "Try the live demo" / "Live demo" | `/demo` | One label | "Live demo" |
| NAV-7 | Docs "Overview", "Knowledge sources" vs console "Overview", "Knowledge sources" | different pages with identical labels | Distinct labels | Docs: "Introduction", "Connecting knowledge sources" |

No dead links were found (crawler: public site + 5 roles, ~250 pages).

## 7. Broken or inconsistent buttons

| ID | Location | Issue | Fix |
|---|---|---|---|
| BTN-1 | Login/demo persona buttons | Act as sign-in buttons (AUTH-2). | Fill-the-form helper. |
| BTN-2 | Sign-out icon in three shells | Three copies of the logic. | One `SignOutButton` via `useAuth().logout`. |
| BTN-3 | `Button` while `loading` | Disabled ✓, but forms without `loading` (users invite dialog, signup) can double-submit on Enter. | All submit handlers guard on `busy`. |

## 8–9. Dead links / duplicate routes
None found. `/console/approvals` (policy approvals) and the Agent Control Center "My approvals" tab are two different approval types. They aren't duplicates, and the labels already differ.

## 10–11. Stale client state / stale cache

| ID | Location | Issue | Fix |
|---|---|---|---|
| STALE-1 | `useApi` | Per-component state only (no global cache), so nothing survives a full reload. But a soft navigation after a role change keeps old permissions until `/auth/me` reloads. | Role and workspace changes call `refresh()`. Logout and login do a full document navigation, which drops every in-memory state. |
| STALE-2 | `localStorage` | Holds tokens (AUTH-3). | Removed; only harmless UI preferences remain. |
| STALE-3 | Next.js | App routes could be served from the bfcache after logout (SESS-2). | `no-store`. |

## 12. Incorrect redirects
AUTH-1, AUTH-9, ROUTE-3, plus: a 401 from any API call sends you to `/login?next=<path>` ✓, but the session isn't revoked server-side first. Fixed by SESS-1.

## 13–15. Loading / error / empty states
Audited every console page: all list pages use `LoadingRows`, `ErrorState` and `EmptyState`. Gaps:

| ID | Location | Gap | Fix |
|---|---|---|---|
| UX-1 | Console pages opened without permission | Raw 403 error text in the page body. | "No access" page from the route guard (ROUTE-2). |
| UX-2 | Login after submit | Button spinner ✓; no "Redirecting…" state, so the form looks idle during navigation. | Keep the busy state until navigation completes. |

## 16. Accessibility
Forms use `Field` with `htmlFor` labels ✓; icon buttons carry `aria-label` ✓; toasts use `aria-live="polite"` ✓; dialogs are `role="dialog"` with focus management ✓. Gaps: the login error isn't linked to its field (`aria-describedby`), and persona chips have no description of what they do. Both are fixed as part of AUTH-2.

## 17. Inconsistent UI patterns
Shared components already exist and are used consistently: `Button` (primary / secondary / ghost / danger), `Badge`, `TrustBadge`, `ActionBadge`, `EmptyState`, `ErrorState`, `LoadingRows`/`Skeleton`, `ConfirmDialog`, `Field`, `Toast`, `PageHeader`, `Section`. **Decision:** they aren't renamed to the `AppButton`/`PrimaryButton` names from the brief, because that would churn every file with no behaviour change. The mapping is in the README. New: `RoleGate`, `SignOutButton`, a shared route-access table.

## 18. Inconsistent API error handling

| ID | Location | Issue | Fix |
|---|---|---|---|
| ERR-1 | `core/errors.py` | Codes are lowercase and ad hoc (`unauthorized`, `http_error`); `details` is sometimes missing. | Standard codes: `UNAUTHENTICATED`, `AUTHORIZATION_DENIED`, `NOT_FOUND`, `CONFLICT`, `VALIDATION_ERROR`, `RATE_LIMITED`, `BAD_REQUEST`, `INTERNAL_ERROR`; `details` is always a list. |
| ERR-2 | `lib/api.ts` | The backend's raw message is shown for every status (e.g. "Missing permission: users:manage", "Request failed (502)"). | One status → message table (401, 403, 404, 409, 422 field errors, 429, 5xx). Specific business messages (e.g. separation-of-duties) are kept when the server marks them as user-facing. |

## 19. Inconsistent permission checks
Frontend: sidebar, page bodies and `homeFor` each made their own decisions. Fixed by one `ROUTE_ACCESS` table in `lib/auth/permissions.ts`, mirrored by the server-side guard; the backend remains authoritative via `require_permission` on every endpoint.

## 20. Inconsistent audit behaviour

| Event | Before | After |
|---|---|---|
| Login success / failure | ✓ / ✓ (failure for unknown emails silently written to NovaCorp's chain via WS-1) | ✓ / ✓ (unknown-email failures go explicitly to the platform workspace) |
| Logout | ✗ | `auth.logout` |
| Token refresh reuse | ✗ | `auth.refresh_reuse` (session revoked) |
| Unauthorized access attempt | ✗ | `auth.access_denied` |
| Workspace switch | n/a (WS-2) | n/a |

---

## Resolution and final report

| Area | Outcome |
|---|---|
| **Primary bug** (AUTH-1, AUTH-2, AUTH-3) | Fixed. Sessions are HTTP-only cookies, with no tokens in `localStorage`. `/login` never auto-continues as a previous account; it shows *Already signed in as … · Continue · Sign out and use another account*. Demo accounts only fill in the form. |
| Sign-out (AUTH-4, SESS-1, SESS-2, SESS-4) | `POST /auth/logout` revokes the server session, so every token of it fails immediately. Cookies are cleared, other tabs follow via `BroadcastChannel`, Back can't show protected pages (`no-store` + `pageshow` reload), and sign-out never races into a `next=` redirect. |
| Tokens (AUTH-5, AUTH-6) | `iss`, `aud`, `sid`, `type`, `exp`, `jti` are required and validated. Refresh is bound to a live session. |
| Self-registration (AUTH-7, WS-1) | `/auth/register` removed. Request-scoped DB sessions must bind a workspace; an unscoped tenant query raises instead of falling back to NovaCorp. Unknown-email login failures are written to the platform workspace on purpose. |
| Brute force (AUTH-8) | Failed sign-ins are rate-limited per network and per account (429 `RATE_LIMITED`). |
| Open redirect (AUTH-9) | `safeNext()` only accepts same-site in-app paths the person may open. |
| Route protection (ROUTE-1, ROUTE-2, SESS-5) | `middleware.ts` (redirect, plus silent renewal of an expired access token) → `ProtectedArea` server layout (session and route permission) → client shell guard for in-app navigation → API `require_permission`. One `ROUTE_ACCESS` table drives the sidebar, the guards and the post-login landing page. |
| Authorization (ROLE-1, ROLE-2) | 403 `AUTHORIZATION_DENIED` with a standard message; every denial audited as `auth.access_denied`. |
| Navigation (NAV-1…7, ROUTE-3) | One label per destination: **Create workspace**, **Sign in**, **Live demo**, **Docs**, **Assistant**, **Connected workspace**, **Open console**, **Open app**. The in-app logo goes to your role home. Docs labels no longer collide with console labels. |
| Interaction (BTN-1…3, UX-1, UX-2) | One `SignOutButton`; login and signup block double submission and stay busy until navigation. Field-level errors use `aria-describedby`. Every destructive action (delete document, revoke API key, cancel schedule, deactivate person) goes through the shared `useConfirm` dialog, with success and error toasts. "No access" page for forbidden routes. |
| Errors (ERR-1, ERR-2) | Standard envelope `{code, message, details[], request_id}` with upper-case codes; the frontend maps status codes to standard messages; 5xx and network errors never show internals; 422 maps to field errors. |
| Audit | `auth.login`, `auth.login_failed`, `auth.logout`, `auth.access_denied`; deactivation records the sessions it revoked. |
| Copy | No user-facing "synthetic / demo data / sample / mock / fake / test data" wording; checked by an E2E test across public and console pages. |
| Workspace selection (WS-2) | **By design:** one workspace per account, resolved server-side. Documented in the README. |

**Verification (final run):**
- Backend: **247 passed**. That includes `test_auth.py` (21 tests), the role tests and cross-workspace isolation across 10 record types.
- Playwright: **68 passed**, i.e. 34 tests run on both bundled Chromium and installed Google Chrome 157. That includes `auth-navigation.spec.ts` (19 tests).
- Docker Compose: all three services healthy (`scripts/check_ports.sh` ✓ 3200 / 8200 / 55432).
- Manual pass in Chrome for all nine personas:
  - each lands on its role home with the right sidebar;
  - review approve, edit and reject, and agent approve, reject and request-info, all update the requester's page live.
