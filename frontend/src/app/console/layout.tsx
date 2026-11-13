import { ConsoleShell } from "@/components/console/shell";
import { ProtectedArea } from "@/lib/auth/server";

export const metadata = { title: "Console" };
export const dynamic = "force-dynamic";

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedArea fallbackPath="/console">
      <ConsoleShell>{children}</ConsoleShell>
    </ProtectedArea>
  );
}
