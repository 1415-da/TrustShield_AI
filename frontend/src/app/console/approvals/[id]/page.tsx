"use client";

import { ArrowLeft, Check, FlaskConical, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DiffViewer } from "@/components/console/diff-viewer";
import { Section } from "@/components/console/shell";
import { VersionSimulator } from "@/components/console/version-simulator";
import { ActionBadge, SeverityBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { dateTime, humanize, PROFILE_LABELS, ROLE_LABELS } from "@/lib/format";
import type { Impact, PolicyApproval, PolicyComment, VersionDetail } from "@/lib/types";

export default function ApprovalViewPage() {
  const { id } = useParams<{ id: string }>();
  const { can, user } = useAuth();
  const toast = useToast();
  const all = useApi<PolicyApproval[]>("/admin/policy-approvals?status=all");
  const approval = all.data?.find((a) => String(a.id) === id);
  const detail = useApi<VersionDetail>(approval ? `/admin/policies/${approval.policy_id}/versions/${approval.version_id}?compare_to=active` : null);
  const comments = useApi<PolicyComment[]>(approval ? `/admin/policies/${approval.policy_id}/comments` : null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [impact, setImpact] = useState<Impact | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (all.loading || (approval && detail.loading)) return <LoadingRows rows={6} />;
  if (!approval || !detail.data) return <ErrorState message={all.error?.message ?? "Approval request not found"} onRetry={all.reload} />;
  const v = detail.data.version;
  const d = v.snapshot;
  const pending = approval.status === "PENDING";
  const ownChange = user && [v.created_by_email, approval.requested_by_email].includes(user.email);
  const shownImpact = impact ?? approval.impact;

  const decide = async (path: "approve" | "request-changes" | "reject") => {
    setBusy(path);
    setError(null);
    try {
      await api(`/admin/policies/${approval.policy_id}/${path}`, { method: "POST", body: { note } });
      toast({ tone: "success", title: path === "approve" ? "Version approved" : path === "reject" ? "Version rejected" : "Changes requested",
        body: path === "approve" ? "An admin can now activate it." : "The author has been sent back to the draft." });
      setNote("");
      await all.reload();
      await detail.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Decision failed");
    } finally {
      setBusy(null);
    }
  };
  const runImpact = async () => {
    setBusy("impact");
    try {
      const r = await api<{ impact: Impact }>(`/admin/policies/${approval.policy_id}/simulate`, { method: "POST", body: { suite: true, version_id: v.id } });
      setImpact(r.impact);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Impact analysis failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <Link href="/console/approvals" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-ink-500 hover:text-ink"><ArrowLeft className="h-3.5 w-3.5" />Approval inbox</Link>
      <div className="mb-6 flex flex-col gap-3 border-b border-hair pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow mb-2">Approval request · {humanize(d.risk_category)} · owner {d.owner || "unassigned"}</p>
          <h1 className="text-[32px] leading-tight sm:text-[38px]">{approval.policy_name} <span className="text-forest">v{approval.version}</span></h1>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px] text-ink-500">
            <ActionBadge action={approval.status} /><ActionBadge action={d.action} /><SeverityBadge severity={d.severity} />
            <span>Requested by {approval.requested_by_email} · {dateTime(approval.requested_at)}</span>
          </div>
        </div>
        <Link href={`/console/policies/${approval.policy_id}`} className="link text-[13px]">Open policy</Link>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr_340px]">
        <div className="space-y-6">
          <Section title="Requested change">
            <p className="rounded-xl bg-cream-200/60 px-4 py-3 text-[14px] leading-relaxed">{approval.request_note || "The author left no note."}</p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-[13px]">
              <div><dt className="text-[11.5px] text-ink-500">Affected roles</dt><dd>{d.applicable_roles.length ? d.applicable_roles.map((r) => ROLE_LABELS[r] ?? r).join(", ") : "Everyone"}</dd></div>
              <div><dt className="text-[11.5px] text-ink-500">Channel profiles</dt><dd>{d.profiles.length ? d.profiles.map((r) => PROFILE_LABELS[r] ?? r).join(", ") : "All channels"}</dd></div>
              <div><dt className="text-[11.5px] text-ink-500">Effective</dt><dd>{d.effective_from ? d.effective_from.slice(0, 10) : "On activation"}{d.effective_to ? ` → ${d.effective_to.slice(0, 10)}` : ""}</dd></div>
              <div><dt className="text-[11.5px] text-ink-500">Rules</dt><dd>{d.rules.length}</dd></div>
            </dl>
          </Section>
          <Section title={detail.data.compared_to ? `Diff against live v${detail.data.compared_to.version}` : "New policy definition"}>
            {detail.data.compared_to ? <DiffViewer diff={detail.data.diff} baseLabel={`v${detail.data.compared_to.version} (live)`} targetLabel={`v${v.version}`} />
              : <DiffViewer diff={detail.data.diff} baseLabel="nothing" targetLabel={`v${v.version}`} isNew />}
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Impact on the evaluation suite" description="Replays every labelled scenario with this version in force."
            actions={<Button size="sm" variant="secondary" onClick={() => void runImpact()} loading={busy === "impact"}><FlaskConical className="h-3.5 w-3.5" />{shownImpact ? "Re-run" : "Run analysis"}</Button>}>
            {!shownImpact ? <p className="text-[13px] text-ink-500">Not run yet. Takes a few seconds.</p> : (
              <div className="space-y-3 text-[13px]" data-testid="impact">
                <p><span className="num font-serif text-[26px] text-forest">{shownImpact.changed.length}</span> of {shownImpact.scenarios} scenarios change · fires on {shownImpact.triggered}
                  {shownImpact.regressions > 0 && <Badge tone="crimson" className="ml-2">{shownImpact.regressions} regression{shownImpact.regressions > 1 ? "s" : ""}</Badge>}</p>
                <ul className="space-y-2">
                  {shownImpact.changed.slice(0, 12).map((c) => (
                    <li key={c.code} className="rounded-xl border border-hair bg-white/50 px-3 py-2">
                      <p className="text-[12px] text-ink-500"><span className="font-mono">{c.code}</span> · {ROLE_LABELS[c.role] ?? c.role}{!c.now_matches_expectation && <span className="ml-1 text-crimson">· no longer meets expectation</span>}</p>
                      <p className="line-clamp-2">{c.prompt}</p>
                      <p className="mt-1 flex flex-wrap items-center gap-1"><ActionBadge action={c.before.input} /><span className="text-ink-400">→</span><ActionBadge action={c.after.input} /></p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Section>
          <VersionSimulator policyId={approval.policy_id} versionId={v.id} versionLabel={`v${v.version}`} />
        </div>

        <div className="space-y-6 xl:sticky xl:top-6 xl:self-start">
          <Section title="Decision">
            {pending && can("policies:approve") && !ownChange ? (
              <div className="space-y-3">
                <Field label="Comment for the author" htmlFor="decision-note" hint="Required when requesting changes or rejecting."><Textarea id="decision-note" rows={4} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
                <Button className="w-full" onClick={() => void decide("approve")} loading={busy === "approve"} data-testid="approve-policy"><Check className="h-4 w-4" />Approve</Button>
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => void decide("request-changes")} loading={busy === "request-changes"} disabled={!note.trim()}><RotateCcw className="h-4 w-4" />Changes</Button>
                  <Button variant="secondary" onClick={() => void decide("reject")} loading={busy === "reject"} disabled={!note.trim()}><X className="h-4 w-4" />Reject</Button>
                </div>
                {error && <ErrorState message={error} />}
              </div>
            ) : (
              <div className="text-[13.5px] text-ink-700">
                <ActionBadge action={approval.status} />
                <p className="mt-2">{pending ? (ownChange ? "You authored or submitted this version, so another approver must decide." : "You can view this request but not decide on it.")
                  : `Decided by ${approval.decided_by_email} on ${dateTime(approval.decided_at ?? approval.requested_at)}.`}</p>
                {approval.decision_note && <p className="mt-2 rounded-lg bg-cream-200/60 px-3 py-2">“{approval.decision_note}”</p>}
              </div>
            )}
          </Section>
          <Section title="Comments">
            <ol className="space-y-2 text-[13px]">
              {comments.data?.map((c) => <li key={c.id}><p className="text-[11.5px] text-ink-500">{c.author_email} · {dateTime(c.created_at)}</p><p>{c.body}</p></li>)}
              {!comments.data?.length && <p className="text-ink-500">No comments.</p>}
            </ol>
          </Section>
        </div>
      </div>
    </>
  );
}
