import { ProtectedArea } from "@/lib/auth/server";

export const metadata = { title: "Assistant" };
export const dynamic = "force-dynamic";

export default function AssistantLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedArea fallbackPath="/assistant">{children}</ProtectedArea>;
}
