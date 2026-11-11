"use client";

import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/console/shell";
import { ActionBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { ROLE_LABELS, shortDate } from "@/lib/format";
import type { PolicyExceptionItem, PolicySummary } from "@/lib/types";

type Pending = { ex: PolicyExceptionItem; action: "approve" | "reject" | "revoke" } | null;

export default function ExceptionsPage() {
  const { can, user } = useAuth();
  const toast = useToast();
  const list = useApi<PolicyExceptionItem[]>("/admin/policy-exceptions");
  const policyList = useApi<PolicySummary[]>(can("policies:write") ? "/admin/policies" : null);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<Pending>(null);
  const [form, setForm] = useState({ policy_id: "", subject_type: "role", subject: "", justification: "", expires_at: "" });
  const [error, setError] = useState<string | null>(null);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api("/admin/policy-exceptions", { method: "POST", body: { ...form, policy_id: Number(form.policy_id), expires_at: `${form.expires_at}T23:59:00` } });
      toast({ tone: "success", title: "Exception requested", body: "It has no effect until a compliance approver approves it." });
      setOpen(false);
      void list.reload();
    } catch (err) { setError(err instanceof ApiError ? err.message : "Request failed"); }
  };
  const decide = async (note: string) => {
    if (!pending) return;
    try {
      await api(`/admin/policy-exceptions/${pending.ex.id}/${pending.action}`, { method: "POST", body: { note } });
      toast({ tone: "success", title: `Exception ${pending.action === "approve" ? "approved" : pending.action === "reject" ? "rejected" : "revoked"}` });
      void list.reload();
    } catch (err) {
      toast({ tone: "error", title: "Not completed", body: err instanceof ApiError ? err.message : undefined });
      throw err;
    }
  };

  const status = (e: PolicyExceptionItem) => (e.status === "APPROVED" && e.is_expired ? "EXPIRED" : e.status);
  return (
    <>
      <PageHeader eyebrow="Policy exceptions" title="Exceptions" description="Time-boxed, approved exemptions from a single policy for a user, role, or department. Every exception expires."
        actions={can("policies:write") && <Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Request exception</Button>} />
      {list.error && <ErrorState message={list.error.message} onRetry={list.reload} />}
      {list.loading ? <LoadingRows rows={4} /> : !list.data?.length ? <EmptyState title="No exceptions" body="Exceptions appear here when someone needs a documented, temporary exemption." /> : (
        <div className="panel overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-[13.5px]">
            <thead className="border-b border-hair text-[12px] text-ink-500"><tr><th className="px-5 py-3 font-medium">Policy & subject</th><th className="px-3 font-medium">Justification</th><th className="px-3 font-medium">Window</th><th className="px-3 font-medium">Status</th><th className="px-5 text-right font-medium" /></tr></thead>
            <tbody>
              {list.data.map((e) => (
                <tr key={e.id} className="border-b border-hair align-top last:border-0">
                  <td className="px-5 py-3.5"><p className="font-medium">{e.policy_name}</p><p className="text-[12.5px] text-ink-500">{e.subject_type}: {e.subject_type === "role" ? ROLE_LABELS[e.subject] ?? e.subject : e.subject}</p></td>
                  <td className="max-w-[320px] px-3 py-3.5 text-ink-700">{e.justification}<p className="mt-1 text-[12px] text-ink-500">Requested by {e.requested_by_email}{e.decided_by_email ? ` · ${e.decided_by_email}: ${e.decision_note}` : ""}</p></td>
                  <td className="px-3 py-3.5 text-ink-500">{shortDate(e.starts_at)} → {shortDate(e.expires_at)}</td>
                  <td className="px-3 py-3.5"><ActionBadge action={status(e)} /></td>
                  <td className="px-5 py-3.5 text-right">
                    <span className="inline-flex gap-1">
                      {e.status === "REQUESTED" && can("policies:approve") && e.requested_by_email !== user?.email && <>
                        <Button size="sm" onClick={() => setPending({ ex: e, action: "approve" })}>Approve</Button>
                        <Button size="sm" variant="secondary" onClick={() => setPending({ ex: e, action: "reject" })}>Reject</Button></>}
                      {e.status === "APPROVED" && !e.is_expired && can("policies:write") && <Button size="sm" variant="ghost" onClick={() => setPending({ ex: e, action: "revoke" })}>Revoke</Button>}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Dialog open={open} onClose={() => setOpen(false)} title="Request a policy exception" description="Exceptions apply only after a compliance approver approves them, and last at most 365 days.">
        <form onSubmit={create} className="space-y-4">
          <Field label="Policy" htmlFor="ex-policy"><Select id="ex-policy" required value={form.policy_id} onChange={(e) => setForm({ ...form, policy_id: e.target.value })}>
            <option value="">Choose a policy</option>{policyList.data?.filter((p) => p.active_version).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
          <div className="grid grid-cols-[140px_1fr] gap-3">
            <Field label="Applies to" htmlFor="ex-type"><Select id="ex-type" value={form.subject_type} onChange={(e) => setForm({ ...form, subject_type: e.target.value, subject: "" })}>
              <option value="role">Role</option><option value="department">Department</option><option value="user">User</option></Select></Field>
            <Field label={form.subject_type === "user" ? "User email" : form.subject_type === "role" ? "Role" : "Department"} htmlFor="ex-subject">
              {form.subject_type === "role" ? (
                <Select id="ex-subject" required value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}><option value="">Choose</option>
                  {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
              ) : <Input id="ex-subject" required value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />}
            </Field>
          </div>
          <Field label="Business justification" htmlFor="ex-why"><Textarea id="ex-why" required minLength={10} rows={3} value={form.justification} onChange={(e) => setForm({ ...form, justification: e.target.value })} /></Field>
          <Field label="Expires on" htmlFor="ex-exp"><Input id="ex-exp" type="date" required value={form.expires_at} onChange={(e) => setForm({ ...form, expires_at: e.target.value })} /></Field>
          {error && <ErrorState message={error} />}
          <Button type="submit" className="w-full">Submit request</Button>
        </form>
      </Dialog>
      <ConfirmDialog open={!!pending} onClose={() => setPending(null)} title={pending ? `${pending.action[0].toUpperCase()}${pending.action.slice(1)} this exception?` : ""}
        description={pending?.action === "approve" ? "The subject will be exempt from this policy until the exception expires." : undefined}
        tone={pending?.action === "approve" ? "primary" : "danger"} confirmLabel={pending ? pending.action[0].toUpperCase() + pending.action.slice(1) : ""}
        withNote noteRequired={pending?.action !== "approve"} onConfirm={decide}>
        {pending && <p className="text-[13px]"><Badge>{pending.ex.policy_name}</Badge> for {pending.ex.subject}</p>}
      </ConfirmDialog>
    </>
  );
}
