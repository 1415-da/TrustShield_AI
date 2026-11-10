import Link from "next/link";

import { Logo } from "@/components/brand/logo";

export default function NotFound() {
  return (
    <main id="main" className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <Logo />
      <h1 className="mt-10 text-[44px]">Page not found</h1>
      <p className="mt-2 text-ink-500">The page you were looking for doesn&apos;t exist or has moved.</p>
      <Link href="/" className="link mt-6">Back to home</Link>
    </main>
  );
}
