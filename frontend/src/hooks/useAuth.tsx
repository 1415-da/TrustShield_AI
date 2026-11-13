/** Compatibility entry point — the auth system lives in `@/lib/auth`. */
export { AuthProvider, useAuth } from "@/lib/auth/auth-context";
export type { SignupBody } from "@/lib/auth/auth-client";
export { canAccess, hasConsole, homeFor } from "@/lib/auth/permissions";

/** Permissions that unlock at least one console page (for "Open console" links). */
export const CONSOLE_PERMISSIONS = ["analytics:read", "policies:read", "reviews:read", "audit:read", "users:manage", "apps:manage",
  "tests:run", "settings:read", "compliance:read", "agents:read", "integrations:read", "actions:approve", "documents:read"];
