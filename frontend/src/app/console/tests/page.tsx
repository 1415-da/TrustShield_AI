"use client";

import { CheckCircle2, FlaskConical, Plus, XCircle } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { PageHeader, Section, Stat } from "@/components/console/shell";
import { ActionBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Select, Textarea } from "@/components/ui/field";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { dateTime, humanize, pct, ROLE_LABELS } from "@/lib/format";
import type { TestCase, TestResult, TestRun } from "@/lib/types";
import { cn } from "@/lib/utils";

const INPUT_ACTIONS = ["ALLOW", "REDACT", "REVIEW", "BLOCK", "ESCALATE"];
const OUTPUT_ACTIONS = ["SHOW", "SHOW_WITH_WARNING", "REDACT", "SEND_TO_REVIEW", "BLOCK"];

export default function TestCenterPage() {
  const cases = useApi<TestCase[]>("/admin/tests");
  const runs = useApi<TestRun[]>("/admin/tests/runs");
  const [runId, setRunId] = useState<number | null>(null);
  useEffect(() => { if (!runId && runs.data?.length) setRunId(runs.data[0].id); }, [runs.data, runId]);
  const current = useApi<TestRun>(runId ? `/admin/tests/runs/${runId}` : null);
  const running = current.data?.status === "running";
  const poll = useApi<TestRun>(running && runId ? `/admin/tests/runs/${runId}` : null, 1500);
  const run = poll.data ?? current.data;
  const done = run?.status === "completed";
  const results = useApi<TestResult[]>(done && runId ? `/admin/tests/runs/${runId}/results` : null);
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [category, setCategory] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", category: "custom", role_key: "employee", prompt: "", expected_input_actions: ["ALLOW"], expected_output_actions: [] as string[] });

  useEffect(() => { if (poll.data?.status === "completed") { void runs.reload(); void current.reload(); } }, [poll.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api<TestRun>("/admin/tests/run", { method: "POST", body: {} });
      setRunId(r.id);
      await runs.reload();
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not start run"); } finally { setBusy(false); }
  };

  const addCase = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try { await api("/admin/tests", { method: "POST", body: { ...form, name: form.name || form.prompt.slice(0, 80) } }); setAdding(false); await cases.reload(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Could not add test"); }
  };

  const categories = useMemo(() => [...new Set((cases.data ?? []).map((c) => c.category))].sort(), [cases.data]);
  const rows = (results.data ?? []).filter((r) => (!onlyFailed || !r.passed || r.false_positive || r.false_negative) && (!category || r.category === category));

  return (
    <>
      <PageHeader eyebrow="Evaluation" title="Test center" description="Labelled scenarios run through the real gateway in dry-run mode. Measures pass rate, false positives and false negatives."
        actions={<><Button variant="secondary" onClick={() => setAdding(true)}><Plus className="h-4 w-4" />Add test</Button><Button onClick={() => void start()} loading={busy || running} data-testid="run-suite"><FlaskConical className="h-4 w-4" />{running ? "Running…" : "Run suite"}</Button></>} />
      {error && <div className="mb-4"><ErrorState message={error} /></div>}
      <section className="panel mb-6 grid grid-cols-2 gap-y-6 p-6 md:grid-cols-5" aria-label="Run summary">
        {!run ? <p className="col-span-full text-[13px] text-ink-500">No runs yet. {cases.data ? `${cases.data.length} scenarios ready.` : ""}</p> : (
          <>
            <Stat label="Pass rate" value={done ? pct(run.summary.pass_rate) : "…"} sub={done ? `${run.passed} / ${run.total}` : "running"} tone="forest" />
            <Stat label="False positives" value={done ? run.false_positives : "…"} sub={done ? `rate ${pct(run.summary.false_positive_rate, 1)} of ${run.summary.safe_cases} safe` : ""} />
            <Stat label="False negatives" value={done ? run.false_negatives : "…"} sub={done ? `rate ${pct(run.summary.false_negative_rate, 1)} of ${run.summary.restrictive_cases} risky` : ""} tone={done && run.false_negatives ? "crimson" : undefined} />
            <Stat label="Avg latency" value={done ? `${Math.round(run.summary.avg_latency_ms ?? 0)}ms` : "…"} sub="per scenario, mock model" />
            <div className="border-l border-hair pl-4">
              <p className="eyebrow">Run</p>
              <Select aria-label="Select run" className="mt-2" value={runId ?? ""} onChange={(e) => setRunId(Number(e.target.value))}>
                {runs.data?.map((r) => <option key={r.id} value={r.id}>#{r.id} · {dateTime(r.started_at)}</option>)}
              </Select>
            </div>
          </>
        )}
      </section>
      {done && run.summary.by_category && (
        <Section title="By category" className="mb-6">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(run.summary.by_category).map(([k, v]) => (
              <button key={k} onClick={() => setCategory(category === k ? "" : k)} className={cn("flex items-center justify-between rounded-xl border px-3 py-2 text-left text-[13px] transition", category === k ? "border-forest bg-forest-50" : "border-hair bg-white/50 hover:border-forest/40")}>
                <span>{humanize(k)}</span><span className={cn("num font-medium", v.passed < v.total ? "text-crimson" : "text-forest")}>{v.passed}/{v.total}</span>
              </button>
            ))}
          </div>
        </Section>
      )}
      <Section title="Results" actions={<Checkbox checked={onlyFailed} onChange={setOnlyFailed} label="Failures and FP/FN only" />}>
        {running ? <LoadingRows rows={5} /> : !results.data ? <p className="text-[13px] text-ink-500">Run the suite to see results.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-[13px]" data-testid="results-table">
              <thead className="border-b border-hair text-[12px] text-ink-500"><tr><th className="py-2.5 font-medium">Case</th><th className="font-medium">Prompt</th><th className="font-medium">Role</th><th className="font-medium">Expected</th><th className="font-medium">Actual</th><th className="text-right font-medium">Result</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-hair align-top last:border-0">
                    <td className="py-3 pr-3"><span className="font-mono text-[12px]">{r.code}</span><p className="text-[11.5px] text-ink-500">{humanize(r.category)}</p></td>
                    <td className="max-w-[320px] py-3 pr-3 text-ink-700">{r.prompt}{r.failure_reason && <p className="mt-1 text-[12px] text-crimson">{r.failure_reason}</p>}</td>
                    <td className="py-3 pr-3 text-ink-500">{ROLE_LABELS[r.role_key] ?? r.role_key}</td>
                    <td className="py-3 pr-3 text-[12px] text-ink-500">{r.expected_input_actions.join(" / ")}{r.expected_output_actions.length ? ` → ${r.expected_output_actions.join(" / ")}` : ""}</td>
                    <td className="py-3 pr-3"><span className="flex flex-wrap gap-1"><ActionBadge action={r.actual_input_action} />{r.actual_output_action && <ActionBadge action={r.actual_output_action} />}</span></td>
                    <td className="py-3 text-right">
                      <span className="inline-flex items-center gap-1.5">
                        {r.false_positive && <Badge tone="amber">FP</Badge>}{r.false_negative && <Badge tone="crimson">FN</Badge>}
                        {r.passed ? <CheckCircle2 className="h-4 w-4 text-sage-700" aria-label="Passed" /> : <XCircle className="h-4 w-4 text-crimson" aria-label="Failed" />}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <Dialog open={adding} onClose={() => setAdding(false)} title="Add a test case">
        <form onSubmit={addCase} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Code" htmlFor="tc-code"><Input id="tc-code" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="T50" /></Field>
            <Field label="Role" htmlFor="tc-role"><Select id="tc-role" value={form.role_key} onChange={(e) => setForm({ ...form, role_key: e.target.value })}>{Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
          </div>
          <Field label="Prompt" htmlFor="tc-prompt"><Textarea id="tc-prompt" required rows={3} value={form.prompt} onChange={(e) => setForm({ ...form, prompt: e.target.value })} /></Field>
          <Field label="Category" htmlFor="tc-cat"><Input id="tc-cat" required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></Field>
          <Field label="Acceptable input decisions"><div className="flex flex-wrap gap-3">{INPUT_ACTIONS.map((a) => <Checkbox key={a} label={a} checked={form.expected_input_actions.includes(a)} onChange={(v) => setForm({ ...form, expected_input_actions: v ? [...form.expected_input_actions, a] : form.expected_input_actions.filter((x) => x !== a) })} />)}</div></Field>
          <Field label="Acceptable output decisions" hint="Leave empty to accept any"><div className="flex flex-wrap gap-3">{OUTPUT_ACTIONS.map((a) => <Checkbox key={a} label={a.replace(/_/g, " ")} checked={form.expected_output_actions.includes(a)} onChange={(v) => setForm({ ...form, expected_output_actions: v ? [...form.expected_output_actions, a] : form.expected_output_actions.filter((x) => x !== a) })} />)}</div></Field>
          <Button type="submit" className="w-full" disabled={!form.expected_input_actions.length}>Add test case</Button>
        </form>
      </Dialog>
    </>
  );
}
