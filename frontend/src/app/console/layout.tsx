import { ConsoleShell } from "@/components/console/shell";

export const metadata = { title: "Console" };

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return <ConsoleShell>{children}</ConsoleShell>;
}
