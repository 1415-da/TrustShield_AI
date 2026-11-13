/**
 * The single route → permission table. The console sidebar, the client route guard, the server route guard and the
 * post-login redirect all use it, so a link is visible exactly when the page behind it is allowed.
 * The API enforces the same permissions independently on every endpoint — this table is for UX, not security.
 */
import { ROLE_BY_KEY } from "@/lib/roles";
import type { User } from "@/lib/types";

/** path prefix → any-of permissions. Longest matching prefix wins. */
export const ROUTE_ACCESS: [string, string[]][] = [
  ["/assistant", ["assistant:use"]],
  ["/workspace", ["assistant:use"]],
  ["/console/setup", ["users:manage"]],
  ["/console/policies/new", ["policies:write"]],
  ["/console/policies", ["policies:read"]],
  ["/console/approvals", ["policies:read"]],
  ["/console/exceptions", ["policies:read"]],
  ["/console/simulator", ["policies:read"]],
  ["/console/documents", ["documents:read"]],
  ["/console/reviews", ["reviews:read"]],
  ["/console/agents", ["agents:read", "actions:approve"]],
  ["/console/evidence", ["compliance:read"]],
  ["/console/audit", ["audit:read"]],
  ["/console/tests", ["tests:run"]],
  ["/console/users", ["users:manage"]],
  ["/console/integrations", ["integrations:read"]],
  ["/console/apps", ["apps:manage"]],
  ["/console/settings", ["settings:read"]],
  // "/console" is the console's front door: open to every console role. People without the Overview dashboard
  // (analytics:read) are forwarded to their first console page.
  ["/console", ["analytics:read", "policies:read", "documents:read", "reviews:read", "agents:read", "actions:approve",
    "compliance:read", "audit:read", "tests:run", "users:manage", "integrations:read", "apps:manage", "settings:read"]],
];

export const OVERVIEW_PERMISSION = "analytics:read";

/** First console page (sidebar order) this person may open, excluding the front door itself. */
export function firstConsolePage(permissions: string[]): string | null {
  const order = ["/console/setup", "/console/policies", "/console/approvals", "/console/exceptions", "/console/simulator",
    "/console/documents", "/console/reviews", "/console/agents", "/console/evidence", "/console/audit", "/console/tests",
    "/console/users", "/console/integrations", "/console/apps", "/console/settings"];
  return order.find((p) => canAccess(p, permissions)) ?? null;
}

export const PROTECTED_PREFIXES = ["/assistant", "/workspace", "/console"];

export function isProtected(path: string): boolean {
  return PROTECTED_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`));
}

function rule(path: string): string[] | null {
  const clean = path.split(/[?#]/)[0];
  let best: [string, string[]] | null = null;
  for (const r of ROUTE_ACCESS) {
    const match = r[0] === "/console" ? clean === "/console" : clean === r[0] || clean.startsWith(`${r[0]}/`);
    if (match && (!best || r[0].length > best[0].length)) best = r;
  }
  return best ? best[1] : null;
}

/** Can someone with these permissions open `path`? Public paths are always allowed. */
export function canAccess(path: string, permissions: string[] | Set<string>): boolean {
  const perms = permissions instanceof Set ? permissions : new Set(permissions);
  const need = rule(path);
  if (need) return need.some((p) => perms.has(p));
  return !isProtected(path);
}

/** Where a person lands after sign-in: their primary role's home, or the first page they may open. */
export function homeFor(user: Pick<User, "primary_role" | "permissions">): string {
  const home = ROLE_BY_KEY[user.primary_role]?.home;
  if (home && canAccess(home, user.permissions)) return home;
  const first = ["/assistant", "/console", "/console/reviews", "/console/agents", "/console/audit", ...ROUTE_ACCESS.map((r) => r[0])]
    .find((p) => canAccess(p, user.permissions));
  return first ?? "/login";
}

/** Any console page at all? (Used for the "Open console" link.) */
export function hasConsole(permissions: string[]): boolean {
  return canAccess("/console", permissions);
}
