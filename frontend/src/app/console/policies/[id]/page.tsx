"use client";

import { ArrowLeft, History, MessageSquare, Power, Rocket, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { DiffViewer } from "@/components/console/diff-viewer";
import { cleanDefinition, PolicyForm } from "@/components/console/policy-form";
import { Section } from "@/components/console/shell";
import { VersionSimulator } from "@/components/console/version-simulator";
import { VersionTimeline } from "@/components/console/version-timeline";
import { ActionBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Checkbox, Input, Textarea } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { dateTime, humanize, shortDate } from "@/lib/format";
import type { Catalogue, PolicyAuditItem, PolicyComment, PolicyDefinition, PolicyDetail, VersionDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

type Tab = "live" | "draft" | "history" | "comments";
const EDITABLE = ["DRAFT", "CHANGES_REQUESTED", "REJECTED"];

export default function PolicyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const toast = useToast();
  const writable = can("policies:write");
  const policy = useApi<PolicyDetail>(`/admin/policies/${id}`);
  const catalogue = useApi<Catalogue>("/admin/policies/catalogue");
  const comments = useApi<PolicyComment[]>(`/admin/policies/${id}/comments`);
  const [tab, setTab] = useState<Tab>("live");
  const [draft, setDraft] = useState<PolicyDefinition | null>(null);
  const [summary, setSummary] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [modal, setModal] = useState<null | "submit" | "activate" | "deactivate" | "rollback" | "audit">(null);
  const [rollbackId, setRollbackId] = useState<number | null>(null);
  const [rollbackActivate, setRollbackActivate] = useState(true);
  const [comment, setComment] = useState("");
  const versionDetail = useApi<VersionDetail>(selected ? `/admin/policies/${id}/versions/${selected}?compare_to=previous` : null);
  const workingDetail = useApi<VersionDetail>(policy.data?.working ? `/admin/policies/${id}/versions/${policy.data.working.id}?compare_to=active` : null);
  const auditHistory = useApi<PolicyAuditItem[]>(modal === "audit" ? `/admin/policies/${id}/audit-history` : null);

  const p = policy.data;
  const w = p?.working ?? null;
  const editable = !!w && EDITABLE.includes(w.status) && writable;

  useEffect(() => {
    if (!p) return;
    if (w) setDraft(w.snapshot);
    if (!selected && p.versions.length) setSelected(p.versions[0].id);
    if (w && tab === "live" && !p.active) setTab("draft");
  }, [p?.updated_at, w?.id, w?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async () => { await policy.reload(); void workingDetail.reload(); };
  const call = async (path: string, body: unknown, success: string) => {
    setError(null);
    try {
      await api(`/admin/policies/${id}/${path}`, { method: "POST", body });
      toast({ tone: "success", title: success });
      await refresh();
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, "error", "Request failed");
      setError(err);
      toast({ tone: "error", title: "Action not completed", body: err.message });
      throw err;
    }
  };

  const saveDraft = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      await call("versions", { ...cleanDefinition(draft), change_summary: summary }, "Draft saved — live traffic is unaffected");
      setSummary("");
    } catch { /* surfaced */ } finally { setSaving(false); }
  };
  const startDraft = () => { if (p?.active) { setDraft(p.active.snapshot); setTab("draft"); } };

  if (policy.loading || !catalogue.data) return <LoadingRows rows={6} />;
  if (policy.error || !p) return <ErrorState message={policy.error?.message ?? "Policy not found"} onRetry={policy.reload} />;

  const approved = p.versions.find((v) => v.status === "APPROVED");
  const tabs: [Tab, string][] = [["live", p.active ? `Live · v${p.active.version}` : "Live"], ["draft", w ? `Working · v${w.version}` : "New draft"], ["history", `History (${p.versions.length})`], ["comments", `Comments (${comments.data?.length ?? 0})`]];

  return (
    <>
      <Link href="/console/policies" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-ink-500 hover:text-ink"><ArrowLeft className="h-3.5 w-3.5" />All policies</Link>
      <div className="mb-6 flex flex-col gap-4 border-b border-hair pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="eyebrow mb-2">{humanize(p.risk_category)} · owned by {p.owner || "unassigned"}</p>
          <h1 className="text-[34px] leading-[1.1] sm:text-[40px]">{p.name}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px] text-ink-500">
            <ActionBadge action={p.status} />
            {p.active && <Badge tone="sage">v{p.active.version} live since {shortDate(p.active.activated_at)}</Badge>}
            {w && <Badge tone={w.status === "IN_REVIEW" ? "amber" : "neutral"}>v{w.version} {humanize(w.status.toLowerCase())}</Badge>}
            <span>Next review {shortDate(p.next_review_at)} · every {p.review_cadence_days} days</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => setModal("audit")}><History className="h-4 w-4" />Audit history</Button>
          {writable && w?.status === "DRAFT" && <Button variant="secondary" onClick={() => setModal("submit")} data-testid="submit-review"><Send className="h-4 w-4" />Submit for review</Button>}
          {w?.status === "IN_REVIEW" && <Link href="/console/approvals" className="inline-flex h-10 items-center rounded-full border border-amber/40 bg-amber-100 px-4 text-[13px] text-amber-700">Awaiting approval</Link>}
          {writable && approved && <Button onClick={() => setModal("activate")} data-testid="activate"><Rocket className="h-4 w-4" />Activate v{approved.version}</Button>}
          {writable && p.active && <Button variant="secondary" onClick={() => setModal("deactivate")}><Power className="h-4 w-4" />Deactivate</Button>}
        </div>
      </div>
      {error && <div className="mb-4"><ErrorState message={error.message} requestId={error.requestId} /></div>}

      <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <div>
          <div role="tablist" aria-label="Policy views" className="mb-5 flex flex-wrap gap-1 rounded-full border border-hair bg-cream-50 p-1">
            {tabs.map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                className={cn("rounded-full px-4 py-1.5 text-[13px] transition", tab === k ? "bg-forest text-cream" : "text-ink-700 hover:text-ink")}>{label}</button>
            ))}
          </div>

          {tab === "live" && (p.active ? (
            <div className="space-y-4">
              <p className="rounded-xl bg-sage-100/70 px-4 py-2.5 text-[13px] text-sage-700">
                This is the version enforced on live traffic. Approved by {p.active.approved_by_email ?? "—"}, activated by {p.active.activated_by_email ?? "—"} on {dateTime(p.active.activated_at ?? p.active.created_at)}.
              </p>
              <PolicyForm value={p.active.snapshot} onChange={() => undefined} catalogue={catalogue.data} readOnly />
              {writable && !w && <Button onClick={startDraft}>Edit as new draft</Button>}
            </div>
          ) : <EmptyState title="Nothing is live" body="This policy has no active version, so it isn't enforced. Approve and activate a version to enforce it." />)}

          {tab === "draft" && (
            !w && !draft ? <EmptyState title="No working draft" body="Changes to a live policy always start as a new draft." action={writable && p.active ? <Button onClick={startDraft}>Start a new draft</Button> : undefined} /> : (
              <div className="space-y-4">
                {w && !EDITABLE.includes(w.status) && (
                  <p className="rounded-xl bg-amber-100/70 px-4 py-2.5 text-[13px] text-amber-700">
                    v{w.version} is {humanize(w.status.toLowerCase())} and locked. {w.status === "APPROVED" ? "Activate it to put it live." : "An approver must decide before it can change."}
                  </p>
                )}
                {w && ["CHANGES_REQUESTED", "REJECTED"].includes(w.status) && workingDetail.data?.approval && (
                  <p className="rounded-xl bg-crimson-100/60 px-4 py-2.5 text-[13px] text-crimson-700">
                    {workingDetail.data.approval.decided_by_email}: “{workingDetail.data.approval.decision_note}” — edit the draft and resubmit.
                  </p>
                )}
                {workingDetail.data && workingDetail.data.compared_to && (
                  <Section title="Changes against the live version"><DiffViewer diff={workingDetail.data.diff} baseLabel={`v${workingDetail.data.compared_to.version} (live)`} targetLabel={`v${workingDetail.data.version.version}`} /></Section>
                )}
                {draft && <PolicyForm value={draft} onChange={setDraft} catalogue={catalogue.data} readOnly={!(editable || (!w && writable))} />}
                {(editable || (!w && writable)) && (
                  <div className="sticky bottom-4 flex flex-wrap items-center gap-3 rounded-2xl border border-hair bg-cream/95 p-3 shadow-soft backdrop-blur">
                    <Input aria-label="Change summary" placeholder="Change summary (recorded in version history)" className="min-w-[200px] flex-1" value={summary} onChange={(e) => setSummary(e.target.value)} />
                    <Button onClick={() => void saveDraft()} loading={saving} data-testid="save-draft">Save draft</Button>
                  </div>
                )}
              </div>
            )
          )}

          {tab === "history" && (
            <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
              <VersionTimeline versions={p.versions} selectedId={selected} onSelect={setSelected}
                onRollback={writable ? (vid) => { setRollbackId(vid); setModal("rollback"); } : undefined} />
              <Section title={versionDetail.data ? `v${versionDetail.data.version.version} · ${humanize(versionDetail.data.version.status.toLowerCase())}` : "Version"}>
                {!versionDetail.data ? <LoadingRows rows={3} /> : (
                  <div className="space-y-4 text-[13px]">
                    <dl className="grid grid-cols-2 gap-3">
                      {([["Created", shortDate(versionDetail.data.version.created_at), versionDetail.data.version.created_by_email],
                        ["Approved", versionDetail.data.version.approved_at ? shortDate(versionDetail.data.version.approved_at) : "—", versionDetail.data.version.approved_by_email],
                        ["Activated", versionDetail.data.version.activated_at ? shortDate(versionDetail.data.version.activated_at) : "—", versionDetail.data.version.activated_by_email],
                        ["Snapshot hash", versionDetail.data.version.snapshot_hash.slice(0, 16) + "…", null]] as [string, string, string | null][]).map(([k, v, who]) => (
                        <div key={k} className="min-w-0"><dt className="text-[11.5px] text-ink-500">{k}</dt><dd>{v}</dd>{who && <dd className="truncate text-[12px] text-ink-500" title={who}>{who}</dd>}</div>
                      ))}
                    </dl>
                    {versionDetail.data.compared_to ? (
                      <DiffViewer diff={versionDetail.data.diff} baseLabel={`v${versionDetail.data.compared_to.version}`} targetLabel={`v${versionDetail.data.version.version}`} />
                    ) : <p className="text-ink-500">First version — nothing to compare against.</p>}
                  </div>
                )}
              </Section>
            </div>
          )}

          {tab === "comments" && (
            <Section title="Discussion" description="Visible to policy authors, approvers and auditors.">
              <ol className="space-y-3">
                {comments.data?.map((c) => (
                  <li key={c.id} className="rounded-xl border border-hair bg-white/50 px-4 py-3 text-[13.5px]">
                    <p className="text-[12px] text-ink-500">{c.author_email} · {dateTime(c.created_at)}</p>
                    <p className="mt-1 whitespace-pre-wrap">{c.body}</p>
                  </li>
                ))}
                {!comments.data?.length && <p className="text-[13px] text-ink-500">No comments yet.</p>}
              </ol>
              {(writable || can("policies:approve")) && (
                <div className="mt-4 flex gap-2">
                  <Textarea aria-label="New comment" rows={2} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a comment" className="flex-1" />
                  <Button disabled={!comment.trim()} onClick={async () => {
                    await api(`/admin/policies/${id}/comments`, { method: "POST", body: { body: comment, version_id: w?.id ?? null } });
                    setComment(""); void comments.reload(); toast({ tone: "success", title: "Comment added" });
                  }}><MessageSquare className="h-4 w-4" />Post</Button>
                </div>
              )}
            </Section>
          )}
        </div>

        <div className="space-y-6">
          {(w || p.active) && <VersionSimulator key={(w ?? p.active)!.id} policyId={p.id} versionId={(w ?? p.active)!.id} versionLabel={`v${(w ?? p.active)!.version}`} />}
        </div>
      </div>

      <ConfirmDialog open={modal === "submit"} onClose={() => setModal(null)} title={`Submit v${w?.version} for review`}
        description="The draft locks and goes to the approval inbox. A different person must approve it." confirmLabel="Submit for review" withNote
        noteLabel="What changed and why" onConfirm={(note) => call("submit-for-review", { note }, "Submitted for approval")} />
      <ConfirmDialog open={modal === "activate"} onClose={() => setModal(null)} title={`Activate v${approved?.version}?`}
        description={p.active ? `v${approved?.version} replaces v${p.active.version} on live traffic immediately. v${p.active.version} is archived, not deleted.` : `v${approved?.version} starts being enforced on live traffic immediately.`}
        confirmLabel="Activate" withNote onConfirm={(note) => call("activate", { version_id: approved?.id, note }, `v${approved?.version} is now live`)} />
      <ConfirmDialog open={modal === "deactivate"} onClose={() => setModal(null)} title="Deactivate this policy?" tone="danger"
        description="Live traffic stops being checked against this policy until a version is activated again." confirmLabel="Deactivate" withNote noteRequired
        noteLabel="Reason (required, kept in the audit trail)" onConfirm={(note) => call("deactivate", { note }, "Policy deactivated")} />
      <ConfirmDialog open={modal === "rollback"} onClose={() => setModal(null)} title={`Roll back to v${p.versions.find((v) => v.id === rollbackId)?.version}`}
        description="Creates a new version that copies the earlier approved definition. History is never rewritten." confirmLabel="Create rollback version" withNote
        onConfirm={(note) => call("rollback", { version_id: rollbackId, note, activate: rollbackActivate }, "Rollback version created")}>
        <Checkbox checked={rollbackActivate} onChange={setRollbackActivate} label="Activate the rollback immediately" />
      </ConfirmDialog>
      <Dialog open={modal === "audit"} onClose={() => setModal(null)} title="Policy audit history" description="Every lifecycle event, mirrored into the hash-chained audit log." side>
        {!auditHistory.data ? <LoadingRows rows={5} /> : (
          <ol className="space-y-3" data-testid="policy-audit">
            {auditHistory.data.map((h) => (
              <li key={h.id} className="rounded-xl border border-hair bg-white/50 px-3 py-2.5 text-[13px]">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{humanize(h.event_type)}</span>
                  {h.version_number && <span className="text-ink-500">v{h.version_number}</span>}
                  {h.from_status && <ActionBadge action={h.from_status} />}{h.to_status && <><span className="text-ink-400">→</span><ActionBadge action={h.to_status} /></>}
                </div>
                <p className="mt-1 text-[12px] text-ink-500">{dateTime(h.created_at)} · {h.actor_email ?? "system"}{h.audit_event_id ? ` · audit #${h.audit_event_id}` : ""}</p>
                {h.note && <p className="mt-1 text-ink-700">{h.note}</p>}
              </li>
            ))}
          </ol>
        )}
      </Dialog>
    </>
  );
}
