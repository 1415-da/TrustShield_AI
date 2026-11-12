"use client";

import { useEffect, useState } from "react";

import { PageHeader, Section } from "@/components/console/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Switch } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { ROLE_LABELS, timeAgo } from "@/lib/format";
import type { Role, User } from "@/lib/types";

export default function UsersPage() {
  const { user: me } = useAuth();
  const users = useApi<User[]>("/admin/users");
  const roles = useApi<Role[]>("/admin/roles");
  const catalogue = useApi<Record<string, string>>("/admin/permissions");
  const [editing, setEditing] = useState<User | null>(null);
  const [roleDraft, setRoleDraft] = useState<string[]>([]);
  const [matrix, setMatrix] = useState<Record<number, string[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [savedRole, setSavedRole] = useState<number | null>(null);
  const toast = useToast();
  const platform = (me?.organization?.id ?? 1) === 1;
  const [inviting, setInviting] = useState(false);
  const blankInvite = () => ({ full_name: "", email: "", department: "General Operations", role_keys: ["employee"],
    temporary_password: `Welcome-${Math.random().toString(36).slice(2, 8)}-${Math.floor(1000 + Math.random() * 9000)}` });
  const [invite, setInvite] = useState(blankInvite);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteBusy, setInviteBusy] = useState(false);

  const sendInvite = async () => {
    setInviteBusy(true);
    setInviteError(null);
    try {
      const created = await api<User>("/admin/users", { method: "POST", body: invite });
      users.setData([...(users.data ?? []), created]);
      toast({ tone: "success", title: `${created.full_name} added`, body: `Share the temporary password securely: ${invite.temporary_password}` });
      setInviting(false);
      setInvite(blankInvite());
    } catch (e) { setInviteError(e instanceof ApiError ? e.message : "Couldn't add this person"); }
    finally { setInviteBusy(false); }
  };

  useEffect(() => { if (roles.data) setMatrix(Object.fromEntries(roles.data.map((r) => [r.id, r.permissions]))); }, [roles.data]);

  const patchUser = async (u: User, body: Partial<{ role_keys: string[]; is_active: boolean }>) => {
    setError(null);
    try {
      const updated = await api<User>(`/admin/users/${u.id}`, { method: "PATCH", body });
      users.setData((users.data ?? []).map((x) => (x.id === u.id ? updated : x)));
      setEditing(null);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Update failed"); }
  };

  const saveRole = async (r: Role) => {
    setError(null);
    try {
      await api(`/admin/roles/${r.id}`, { method: "PATCH", body: { permissions: matrix[r.id] } });
      setSavedRole(r.id);
      void roles.reload();
    } catch (e) { setError(e instanceof ApiError ? e.message : "Update failed"); }
  };

  return (
    <>
      <PageHeader eyebrow="Access" title="Users & roles" description="Roles carry permission scopes. Data scopes (compensation, financial) control what the assistant may reveal to whom."
        actions={<Button onClick={() => { setInviteError(null); setInviting(true); }} data-testid="invite-user">Add person</Button>} />
      {error && <div className="mb-4"><ErrorState message={error} /></div>}
      <Section title="People" className="mb-6">
        {users.loading ? <LoadingRows rows={6} /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-[13.5px]">
              <thead className="border-b border-hair text-[12px] text-ink-500"><tr><th className="py-2.5 font-medium">Name</th><th className="font-medium">Department</th><th className="font-medium">Roles</th><th className="font-medium">Last sign-in</th><th className="text-right font-medium">Active</th></tr></thead>
              <tbody>
                {users.data?.map((u) => (
                  <tr key={u.id} className="border-b border-hair last:border-0">
                    <td className="py-3"><p className="font-medium">{u.full_name}</p><p className="text-[12px] text-ink-500">{u.email}</p></td>
                    <td className="text-ink-700">{u.department}</td>
                    <td>
                      <button onClick={() => { setEditing(u); setRoleDraft(u.role_keys); }} className="flex flex-wrap gap-1 text-left" aria-label={`Edit roles for ${u.full_name}`}>
                        {u.role_keys.map((k) => <Badge key={k} tone={k === "trustshield_admin" ? "forest" : "neutral"}>{ROLE_LABELS[k] ?? k}</Badge>)}
                      </button>
                    </td>
                    <td className="text-ink-500">{u.last_login_at ? timeAgo(u.last_login_at) : "Never"}</td>
                    <td className="text-right"><Switch checked={u.is_active} onChange={(v) => void patchUser(u, { is_active: v })} label={`${u.full_name} active`} disabled={u.id === me?.id} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <Section title="Role permissions" description={platform ? "Changes apply on the user's next request and are recorded in the audit log."
        : "Roles are defined by the platform and shared by every workspace. Assign them to people above; ask your platform administrator to change what a role can do."}>
        {!roles.data || !catalogue.data ? <LoadingRows rows={4} /> : (
          <div className="grid gap-4 lg:grid-cols-2">
            {roles.data.map((r) => (
              <div key={r.id} className="rounded-2xl border border-hair bg-white/50 p-4">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div><p className="font-serif text-[19px]">{r.name}</p><p className="text-[12.5px] text-ink-500">{r.description}</p></div>
                  {platform && <Button size="sm" variant="secondary" onClick={() => void saveRole(r)}>{savedRole === r.id ? "Saved" : "Save"}</Button>}
                </div>
                <div className="grid gap-1.5 sm:grid-cols-2">
                  {Object.entries(catalogue.data!).map(([perm, label]) => (
                    <Checkbox key={perm} disabled={!platform} checked={(matrix[r.id] ?? []).includes(perm)} label={<span title={label}><span className="font-mono text-[12px]">{perm}</span></span>}
                      onChange={(v) => { setSavedRole(null); setMatrix({ ...matrix, [r.id]: v ? [...(matrix[r.id] ?? []), perm] : (matrix[r.id] ?? []).filter((p) => p !== perm) }); }} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
      <Dialog open={inviting} onClose={() => setInviting(false)} title="Add a person" description="They sign in with this temporary password. Everything they do is scoped to your workspace.">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void sendInvite(); }}>
          <Field label="Full name" htmlFor="inv-name"><Input id="inv-name" required minLength={2} value={invite.full_name} onChange={(e) => setInvite({ ...invite, full_name: e.target.value })} /></Field>
          <Field label="Work email" htmlFor="inv-email"><Input id="inv-email" type="email" required value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} /></Field>
          <Field label="Department" htmlFor="inv-dept"><Input id="inv-dept" value={invite.department} onChange={(e) => setInvite({ ...invite, department: e.target.value })} /></Field>
          <div>
            <p className="mb-1.5 text-[12.5px] font-medium text-ink-700">Roles</p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {Object.entries(ROLE_LABELS).map(([k, v]) => (
                <Checkbox key={k} checked={invite.role_keys.includes(k)} label={v}
                  onChange={(on) => setInvite({ ...invite, role_keys: on ? [...invite.role_keys, k] : invite.role_keys.filter((x) => x !== k) })} />
              ))}
            </div>
          </div>
          <Field label="Temporary password" htmlFor="inv-pw" hint="At least 10 characters. Share it with them over a secure channel.">
            <Input id="inv-pw" required minLength={10} value={invite.temporary_password} onChange={(e) => setInvite({ ...invite, temporary_password: e.target.value })} className="font-mono" />
          </Field>
          {inviteError && <ErrorState message={inviteError} />}
          <Button type="submit" className="w-full" loading={inviteBusy} disabled={!invite.role_keys.length}>Add to workspace</Button>
        </form>
      </Dialog>
      <Dialog open={!!editing} onClose={() => setEditing(null)} title={`Roles for ${editing?.full_name ?? ""}`}>
        <div className="space-y-2">
          {Object.entries(ROLE_LABELS).map(([k, v]) => (
            <Checkbox key={k} checked={roleDraft.includes(k)} label={v} onChange={(on) => setRoleDraft(on ? [...roleDraft, k] : roleDraft.filter((x) => x !== k))} />
          ))}
          <Button className="mt-4 w-full" disabled={!roleDraft.length} onClick={() => editing && void patchUser(editing, { role_keys: roleDraft })}>Save roles</Button>
        </div>
      </Dialog>
    </>
  );
}
