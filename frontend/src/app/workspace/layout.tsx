import { ProtectedArea } from "@/lib/auth/server";

export const metadata = { title: "Connected workspace" };
export const dynamic = "force-dynamic";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedArea fallbackPath="/workspace">{children}</ProtectedArea>;
}
