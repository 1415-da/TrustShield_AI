"use client";

import { ArrowLeft, Check, Pencil, ShieldAlert, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { RichText } from "@/components/assistant/message";
import { Section } from "@/components/console/shell";
import { SlaChip } from "@/components/console/sla-chip";
import { ActionBadge, ScoreBar, SeverityBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { dateTime, humanize, ROLE_LABELS } from "@/lib/format";
import type { ReviewCaseDetail } from "@/lib/types";

type Decision = "approve" | "edit" | "reject" | "escalate";

export default function ReviewCasePage() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const canAct = can("reviews:act");
  const { data: c, error, loading, setData, reload } = useApi<ReviewCaseDetail>(`/reviewer/cases/${id}`);
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState("");
  const [busy, setBusy] = useState<Decision | "note" | null>(null);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  useEffect(() => { if (c) setEdited(c.draft_response ?? ""); }, [c?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (decision: Decision | "note") => {
    setBusy(decision);
    setActionError(null);
    try {
      const path = decision === "note" ? "notes" : decision;
      const body = decision === "edit" ? { note, edited_response: edited } : { note };
      const updated = await api<ReviewCaseDetail>(`/reviewer/cases/${id}/${path}`, { method: "POST", body });
      setData(updated);
      setNote("");
      setEditing(false);
    } catch (e) {
      setActionError(e instanceof ApiError ? e : new ApiError(0, "error", "Action failed"));
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <LoadingRows rows={6} />;
  if (error || !c) return <ErrorState message={error?.message ?? "Case not found"} onRetry={reload} />;
  const open = c.status === "PENDING" || c.status === "ESCALATED";
  const g = c.signals?.grounding as Record<string, number> | null | undefined;

  return (
    <>
      <Link href="/console/reviews" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-ink-500 hover:text-ink"><ArrowLeft className="h-3.5 w-3.5" />Review queue</Link>
      <div className="mb-6 flex flex-col gap-3 border-b border-hair pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow mb-2">Case #{c.id} · {ROLE_LABELS[c.requester_role] ?? c.requester_role}{c.requester_department ? `, ${c.requester_department}` : ""}</p>
          <h1 className="text-[32px] leading-tight sm:text-[36px]">{c.reason}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <SeverityBadge severity={c.priority} /><ActionBadge action={c.status} /><SlaChip c={c} />
            <span className="text-[12px] text-ink-500">Opened {dateTime(c.created_at)}</span>
          </div>
        </div>
        <p className="font-mono text-[11px] text-ink-400">request {c.request_id}</p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr_340px]">
        {/* Column 1: request + draft */}
        <div className="space-y-6">
          <Section title="Employee request" description="Sensitive values were masked before storage.">
            <p className="rounded-xl bg-ink px-4 py-3 text-[14.5px] leading-relaxed text-cream" data-testid="case-prompt">{c.prompt_masked}</p>
          </Section>
          <Section title={c.final_response ? "Delivered response" : "AI draft"} description={c.draft_response === null && !c.final_response ? "Escalated before reaching the model. Approving will generate an answer, which is still checked on output." : undefined}
            actions={open && canAct && c.draft_response !== null && !editing && <Button size="sm" variant="secondary" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" />Edit</Button>}>
            {editing ? (
              <div className="space-y-2">
                <Textarea aria-label="Edited response" rows={9} value={edited} onChange={(e) => setEdited(e.target.value)} data-testid="edit-response" />
                <p className="text-[12px] text-ink-500">Your edit is re-scanned for personal data before it is delivered.</p>
              </div>
            ) : (
              <div className="rounded-xl border border-hair bg-white/60 px-4 py-3 text-[14px] leading-relaxed text-ink-700" data-testid="case-draft">
                {c.final_response ?? c.draft_response ? <RichText text={(c.final_response ?? c.draft_response)!} /> : <span className="italic text-ink-400">No draft — the model was not called.</span>}
              </div>
            )}
          </Section>
        </div>

        {/* Column 2: evidence + risk */}
        <div className="space-y-6">
          <Section title="Risk explanation">
            {g && (
              <div className="mb-4 space-y-2">
                {["confidence", "groundedness", "query_support", "citation_presence"].map((k) => (
                  <div key={k} className="text-[12.5px]"><span className="text-ink-700">{humanize(k)}</span><ScoreBar value={Number(g[k] ?? 0)} tone={Number(g[k] ?? 0) < 0.4 ? "crimson" : Number(g[k] ?? 0) < 0.6 ? "amber" : "forest"} label={k} /></div>
                ))}
                <p className="text-[11.5px] text-ink-500">Risk signals, not guarantees.</p>
              </div>
            )}
            <ul className="space-y-2">
              {c.policy_matches.map((m, i) => (
                <li key={i} className="rounded-xl border border-hair bg-white/50 px-3 py-2.5 text-[12.5px]">
                  <div className="flex flex-wrap items-center gap-1.5"><span className="font-medium">{m.policy_name}</span><span className="ml-auto"><ActionBadge action={m.action} /></span></div>
                  <p className="mt-0.5 text-ink-700">{m.rule_name}</p>
                  <p className="mt-1 font-mono text-[11px] text-ink-500">{m.match_field} · {m.evidence}</p>
                </li>
              ))}
              {!c.policy_matches.length && <p className="text-[13px] text-ink-500">No rule matches recorded.</p>}
            </ul>
          </Section>
          <Section title="Retrieved policy evidence">
            {c.sources.length ? (
              <ul className="space-y-2.5">
                {c.sources.map((s) => (
                  <li key={`${s.index}-${s.chunk_id}`} className="border-l-2 border-forest/40 pl-3 text-[12.5px]">
                    <p className="font-medium">[{s.index}] {s.title}{s.heading ? ` · ${s.heading}` : ""}</p>
                    <div className="mt-0.5 leading-relaxed text-ink-700"><RichText text={s.snippet} /></div>
                  </li>
                ))}
              </ul>
            ) : <p className="text-[13px] text-ink-500">No evidence was retrieved for this request.</p>}
          </Section>
        </div>

        {/* Column 3: decision */}
        <div className="space-y-6 xl:sticky xl:top-6 xl:self-start">
          <Section title="Decision">
            {open && canAct ? (
              <div className="space-y-3">
                <p className="text-[12.5px] text-ink-500">Suggested: <span className="font-medium text-ink">{humanize(c.suggested_action.toLowerCase())}</span></p>
                <Field label="Reviewer note" htmlFor="note"><Textarea id="note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why you decided this (kept in the audit trail)" /></Field>
                {editing ? (
                  <div key="editing" className="flex gap-2">
                    <Button className="flex-1" onClick={() => void act("edit")} loading={busy === "edit"} disabled={!edited.trim()}><Check className="h-4 w-4" />Send edited answer</Button>
                    <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
                  </div>
                ) : (
                  <div key="deciding" className="grid grid-cols-2 gap-2">
                    <Button onClick={() => void act("approve")} loading={busy === "approve"} data-testid="approve"><Check className="h-4 w-4" />Approve</Button>
                    <Button variant="secondary" onClick={() => void act("reject")} loading={busy === "reject"}><X className="h-4 w-4" />Reject</Button>
                    <Button variant="secondary" className="col-span-2" onClick={() => void act("escalate")} loading={busy === "escalate"} disabled={c.status === "ESCALATED"}><ShieldAlert className="h-4 w-4" />Escalate to security</Button>
                    <Button variant="ghost" className="col-span-2" onClick={() => void act("note")} loading={busy === "note"} disabled={!note.trim()}>Add note only</Button>
                  </div>
                )}
                {actionError && <ErrorState message={actionError.message} />}
              </div>
            ) : (
              <div className="text-[13.5px]">
                <ActionBadge action={c.status} />
                <p className="mt-2 text-ink-700">{open ? "You can view this case but not act on it." : `Resolved ${c.resolved_at ? dateTime(c.resolved_at) : ""}${c.resolved_by_email ? ` by ${c.resolved_by_email}` : ""}.`}</p>
              </div>
            )}
          </Section>
          <Section title="Activity">
            <ol className="space-y-3 text-[12.5px]">
              <li className="flex gap-2"><Badge>Created</Badge><span className="text-ink-500">{dateTime(c.created_at)}</span></li>
              {c.actions.map((a) => (
                <li key={a.id}>
                  <div className="flex flex-wrap items-center gap-2"><ActionBadge action={a.action} /><span className="text-ink-700">{a.reviewer_email}</span></div>
                  <p className="mt-0.5 text-ink-500">{dateTime(a.created_at)}</p>
                  {a.note && <p className="mt-1 rounded-lg bg-cream-200/60 px-2.5 py-1.5 text-ink-700">{a.note}</p>}
                </li>
              ))}
            </ol>
          </Section>
        </div>
      </div>
    </>
  );
}
