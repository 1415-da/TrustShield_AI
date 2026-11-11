"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { BLANK_DEFINITION, cleanDefinition, PolicyForm } from "@/components/console/policy-form";
import { PageHeader } from "@/components/console/shell";
import { VersionSimulator } from "@/components/console/version-simulator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import type { Catalogue, PolicyDefinition, PolicyDetail } from "@/lib/types";

export default function NewPolicyPage() {
  const router = useRouter();
  const toast = useToast();
  const catalogue = useApi<Catalogue>("/admin/policies/catalogue");
  const [draft, setDraft] = useState<PolicyDefinition>(BLANK_DEFINITION);
  const [summary, setSummary] = useState("Initial draft");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await api<PolicyDetail>("/admin/policies", { method: "POST", body: { ...cleanDefinition(draft), change_summary: summary } });
      toast({ tone: "success", title: "Draft saved", body: "It has no effect on live traffic until it is approved and activated." });
      router.replace(`/console/policies/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "error", "Save failed"));
      setSaving(false);
    }
  };

  if (!catalogue.data) return <LoadingRows rows={6} />;
  return (
    <>
      <Link href="/console/policies" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-ink-500 hover:text-ink"><ArrowLeft className="h-3.5 w-3.5" />All policies</Link>
      <PageHeader eyebrow="New policy · draft" title="Create a policy" description="Drafts never affect employees. Save, test it in the simulator, then submit it for approval." />
      <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <form onSubmit={save} className="space-y-6" aria-label="Policy editor">
          <PolicyForm value={draft} onChange={setDraft} catalogue={catalogue.data} />
          {error && <ErrorState message={error.message + (error.details ? ` — ${JSON.stringify(error.details).slice(0, 200)}` : "")} requestId={error.requestId} />}
          <div className="sticky bottom-4 flex flex-wrap items-center gap-3 rounded-2xl border border-hair bg-cream/95 p-3 shadow-soft backdrop-blur">
            <Input aria-label="Change summary" className="min-w-[200px] flex-1" value={summary} onChange={(e) => setSummary(e.target.value)} />
            <Button type="submit" loading={saving}>Save draft</Button>
          </div>
        </form>
        <VersionSimulator draft={cleanDefinition(draft)} />
      </div>
    </>
  );
}
