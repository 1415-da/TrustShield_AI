"use client";

import { FlaskConical } from "lucide-react";
import { useState } from "react";

import { Section } from "@/components/console/shell";
import { SimulationView } from "@/components/console/simulation-view";
import { Button } from "@/components/ui/button";
import { Select, Textarea } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { PROFILE_LABELS, ROLE_LABELS } from "@/lib/format";
import type { PolicyDefinition, SimulationResult } from "@/lib/types";

/** "Test this version": a saved version (policyId + versionId) or an unsaved definition (draft). */
export function VersionSimulator({ policyId, versionId, versionLabel, draft }: {
  policyId?: number; versionId?: number; versionLabel?: string; draft?: PolicyDefinition;
}) {
  const [prompt, setPrompt] = useState("");
  const [role, setRole] = useState("employee");
  const [profile, setProfile] = useState("");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = { prompt, role, profile: profile || null };
      setResult(policyId
        ? await api<SimulationResult>(`/admin/policies/${policyId}/simulate`, { method: "POST", body: { ...body, version_id: versionId } })
        : await api<SimulationResult>("/admin/simulate", { method: "POST", body: { ...body, draft_policy: draft } }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Simulation failed");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Section title="Test this version" description={policyId ? `Runs live traffic rules with ${versionLabel ?? "this version"} forced in place of the live version. Nothing is stored.` : "Runs your unsaved draft alongside the live policies."}>
      <div className="space-y-3">
        <Textarea aria-label="Sample prompt" rows={3} placeholder="Paste a sample employee prompt…" value={prompt} onChange={(e) => setPrompt(e.target.value)} data-testid="policy-sim-prompt" />
        <div className="grid gap-2 sm:grid-cols-2">
          <Select aria-label="Simulated role" value={role} onChange={(e) => setRole(e.target.value)}>
            {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
          <Select aria-label="Channel profile" value={profile} onChange={(e) => setProfile(e.target.value)}>
            <option value="">Web assistant</option>
            {Object.entries(PROFILE_LABELS).map(([k, v]) => <option key={k} value={k}>{v} channel</option>)}
          </Select>
          <Button type="button" className="sm:col-span-2" onClick={() => void run()} loading={busy} disabled={!prompt.trim()}><FlaskConical className="h-4 w-4" />Run</Button>
        </div>
      </div>
      {error && <div className="mt-3"><ErrorState message={error} /></div>}
      {result && <div className="mt-4"><SimulationView result={result} /></div>}
    </Section>
  );
}
