import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DocsMobileNav, DocsSidebar } from "@/components/docs/sidebar";
import { LandingNav, SiteFooter } from "@/components/landing/nav";

export const metadata: Metadata = { title: { default: "Documentation", template: "%s · Docs · TrustShield AI" } };

export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <LandingNav />
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-10 sm:px-8 lg:grid-cols-[220px_1fr] lg:py-14">
        <aside className="hidden lg:block">
          <div className="sticky top-24 max-h-[calc(100vh-7rem)] overflow-y-auto pb-10 scrollbar-thin"><DocsSidebar /></div>
        </aside>
        <div className="min-w-0">
          <div className="mb-6"><DocsMobileNav /></div>
          <main id="main">{children}</main>
        </div>
      </div>
      <SiteFooter />
    </>
  );
}
