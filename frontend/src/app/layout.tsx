import type { Metadata } from "next";
import { EB_Garamond, Figtree } from "next/font/google";

import { ToastProvider } from "@/components/ui/toast";
import { AuthProvider } from "@/hooks/useAuth";
import "@/styles/globals.css";

const serif = EB_Garamond({ subsets: ["latin"], variable: "--font-serif", display: "swap", weight: ["400", "500", "600"], style: ["normal", "italic"] });
const sans = Figtree({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: { default: "TrustShield AI — AI governance gateway", template: "%s · TrustShield AI" },
  description: "Ship AI your security team can trust. Input guardrails, output validation, policy engine, human review, and an audit trail for internal AI assistants.",
};

/**
 * Browser translation (Chrome/Edge "Translate this page") and extensions such as Grammarly or dark-mode tools
 * replace text nodes that React owns. When React later removes or re-inserts one of those nodes it throws
 * "Failed to execute 'removeChild' on 'Node'" and the whole page fails. This guard (the widely used fix
 * for facebook/react#11538) makes those two DOM operations tolerant, so live updates — a reviewer
 * approving an answer, an agent action executing — keep working whatever the browser has done to the page.
 * It must run before React hydrates, hence an inline script in <head>.
 */
const DOM_GUARD = `(function(){
  if (typeof Node !== "function" || !Node.prototype || Node.prototype.__tsGuard) return;
  Node.prototype.__tsGuard = true;
  var remove = Node.prototype.removeChild, insert = Node.prototype.insertBefore;
  Node.prototype.removeChild = function (child) {
    if (child && child.parentNode !== this) {
      // Already moved by an extension: remove it from wherever it is now; if detached, nothing to do.
      if (child.parentNode) return remove.call(child.parentNode, child);
      return child;
    }
    return remove.apply(this, arguments);
  };
  Node.prototype.insertBefore = function (node, ref) {
    if (ref && ref.parentNode !== this) {
      // The reference node was wrapped (e.g. in <font>): insert before its wrapper, or append if it is gone.
      var anchor = ref;
      while (anchor && anchor.parentNode !== this) anchor = anchor.parentNode;
      return insert.call(this, node, anchor || null);
    }
    return insert.apply(this, arguments);
  };
})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: DOM_GUARD }} />
      </head>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-full focus:bg-forest focus:px-4 focus:py-2 focus:text-cream">
          Skip to content
        </a>
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
