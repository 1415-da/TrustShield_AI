"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

/** Route-level error screen: replaces Next.js's blank "Application error" page with a way to recover. */
export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("TrustShield page error:", error);
    // A tab left open across a redeploy can request code chunks that no longer exist; a reload fixes it.
    if (/ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module/i.test(`${error.name} ${error.message}`)) {
      const key = "trustshield.chunk-reload";
      if (!sessionStorage.getItem(key)) {
        sessionStorage.setItem(key, "1");
        window.location.reload();
      }
    }
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div role="alert" className="w-full max-w-md rounded-3xl border border-hair bg-cream-50 p-7 shadow-soft">
        <AlertTriangle className="h-6 w-6 text-crimson" />
        <h1 className="mt-4 text-[26px] leading-tight">Something went wrong on this page</h1>
        <p className="mt-2 text-[14px] text-ink-700">Your data is safe — this was a display problem in the browser. Try again, or reload the page.</p>
        <p className="mt-4 break-words rounded-xl bg-ink/[0.04] px-3 py-2 font-mono text-[11.5px] text-ink-500">
          {error.message || "Unknown error"}{error.digest ? ` · ${error.digest}` : ""}
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <button onClick={reset} className="inline-flex items-center gap-2 rounded-full bg-forest px-4 py-2 text-[13.5px] font-medium text-cream hover:bg-forest/90">
            <RotateCcw className="h-4 w-4" />Try again
          </button>
          <button onClick={() => window.location.reload()} className="rounded-full border border-hair px-4 py-2 text-[13.5px] hover:bg-ink/[0.04]">Reload page</button>
          <Link href="/" className="rounded-full px-4 py-2 text-[13.5px] text-ink-700 hover:bg-ink/[0.04]">Home</Link>
        </div>
      </div>
    </div>
  );
}
