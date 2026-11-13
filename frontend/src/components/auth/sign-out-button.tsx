"use client";

import { LogOut } from "lucide-react";
import { useState } from "react";

import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/utils";

/** The one sign-out control: revokes the session, clears all state and goes to /login. */
export function SignOutButton({ className }: { className?: string }) {
  const { logout } = useAuth();
  const [busy, setBusy] = useState(false);
  return (
    <button type="button" disabled={busy} onClick={() => { setBusy(true); void logout(); }} aria-label="Sign out" title="Sign out"
      data-testid="sign-out" className={cn("rounded-full p-2 transition disabled:opacity-50", className)}>
      {busy ? <span className="block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" /> : <LogOut className="h-4 w-4" />}
    </button>
  );
}
