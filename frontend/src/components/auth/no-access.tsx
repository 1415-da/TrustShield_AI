import { ShieldOff } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { homeFor } from "@/lib/auth/permissions";
import { ROLE_LABELS } from "@/lib/roles";
import type { User } from "@/lib/types";

/** Shown when a signed-in person opens a page their role does not include. */
export function NoAccess({ user }: { user: Pick<User, "full_name" | "primary_role" | "permissions"> }) {
  return (
    <main id="main" className="flex min-h-[70vh] items-center justify-center px-4" data-testid="no-access">
      <div className="max-w-md text-center">
        <ShieldOff className="mx-auto h-8 w-8 text-ink-400" />
        <h1 className="mt-4 text-[30px] leading-tight">You don&apos;t have access to this page</h1>
        <p className="mt-2 text-[14.5px] text-ink-700">
          You&apos;re signed in as {user.full_name} ({ROLE_LABELS[user.primary_role] ?? user.primary_role}). This page needs a role you
          don&apos;t hold. Ask your TrustShield Admin if you need it.
        </p>
        <Link href={homeFor(user)} className={buttonVariants({ className: "mt-6" })}>Go to your home page</Link>
      </div>
    </main>
  );
}
