"use client";

/** Last-resort error screen for failures in the root layout itself (no app styles are guaranteed here). */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", background: "#F7F3EA", color: "#14201D", display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", margin: 0, padding: 16 }}>
        <div role="alert" style={{ maxWidth: 440 }}>
          <h1 style={{ fontSize: 24, margin: 0 }}>Something went wrong</h1>
          <p style={{ fontSize: 14, opacity: 0.8 }}>Your data is safe — this was a display problem in the browser.</p>
          <p style={{ fontFamily: "monospace", fontSize: 12, opacity: 0.6, wordBreak: "break-word" }}>{error.message}{error.digest ? ` · ${error.digest}` : ""}</p>
          <button onClick={reset} style={{ marginRight: 8, padding: "8px 16px", borderRadius: 999, border: 0, background: "#0F3D33", color: "#F7F3EA", cursor: "pointer" }}>Try again</button>
          <button onClick={() => window.location.reload()} style={{ padding: "8px 16px", borderRadius: 999, border: "1px solid #ccc", background: "transparent", cursor: "pointer" }}>Reload page</button>
        </div>
      </body>
    </html>
  );
}
