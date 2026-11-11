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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
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
