"use client";

import { FileText, RefreshCw, Trash2, Upload } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { PageHeader, Section } from "@/components/console/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { DocumentDetail, DocumentItem } from "@/lib/types";

export default function DocumentsPage() {
  const { can } = useAuth();
  const writable = can("documents:write");
  const docs = useApi<DocumentItem[]>("/admin/documents");
  const processing = docs.data?.some((d) => d.status === "processing");
  const poll = useApi<DocumentItem[]>(processing ? "/admin/documents" : null, 1500);
  const list = poll.data ?? docs.data;
  const [viewId, setViewId] = useState<number | null>(null);
  const detail = useApi<DocumentDetail>(viewId ? `/admin/documents/${viewId}` : null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [trust, setTrust] = useState("trusted");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("trust_level", trust);
    try {
      await api("/admin/documents", { method: "POST", form });
      setTitle("");
      if (fileRef.current) fileRef.current.value = "";
      await docs.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const reindex = async (id: number) => { await api(`/admin/documents/${id}/reindex`, { method: "POST" }); await docs.reload(); };
  const remove = async (d: DocumentItem) => {
    if (!window.confirm(`Delete “${d.title}”? It will no longer be used to answer questions.`)) return;
    await api(`/admin/documents/${d.id}`, { method: "DELETE" });
    await docs.reload();
  };

  return (
    <>
      <PageHeader eyebrow="Retrieval" title="Knowledge sources" description="Policy documents the assistant answers from. Each is chunked, embedded, and cited in answers." />
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div>
          {docs.error && <ErrorState message={docs.error.message} onRetry={docs.reload} />}
          {docs.loading ? <LoadingRows rows={6} /> : !list?.length ? <EmptyState title="No documents yet" body="Upload a Markdown or text policy to start answering questions." /> : (
            <ul className="space-y-2.5">
              {list.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center gap-4 rounded-2xl border border-hair bg-cream-50 px-4 py-3.5">
                  <FileText className="h-5 w-5 shrink-0 text-forest" strokeWidth={1.6} />
                  <button onClick={() => setViewId(d.id)} className="min-w-0 flex-1 text-left">
                    <p className="truncate font-medium hover:text-forest">{d.title}</p>
                    <p className="text-[12px] text-ink-500">{d.filename} · {d.chunk_count} chunks · {d.source === "seed" ? "policy library" : "uploaded"} {timeAgo(d.created_at)}</p>
                  </button>
                  <div className="flex items-center gap-2">
                    {d.trust_level === "untrusted" && <Badge tone="amber">Untrusted source</Badge>}
                    <Badge tone={d.status === "indexed" ? "sage" : d.status === "failed" ? "crimson" : "amber"}>{d.status}</Badge>
                    {writable && (
                      <>
                        <button onClick={() => void reindex(d.id)} className="rounded-full p-2 text-ink-400 hover:bg-ink/5 hover:text-ink" aria-label={`Reindex ${d.title}`}><RefreshCw className="h-4 w-4" /></button>
                        <button onClick={() => void remove(d)} className="rounded-full p-2 text-ink-400 hover:bg-crimson-100 hover:text-crimson" aria-label={`Delete ${d.title}`}><Trash2 className="h-4 w-4" /></button>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        {writable && (
          <Section title="Upload a policy" description="Markdown, TXT, or text-based PDF exports. Max 1 MB.">
            <form onSubmit={upload} className="space-y-4">
              <Field label="File" htmlFor="doc-file"><Input id="doc-file" ref={fileRef} type="file" accept=".md,.markdown,.txt,.text,.pdf" required className="h-auto py-2 file:mr-3 file:rounded-full file:border-0 file:bg-forest-50 file:px-3 file:py-1 file:text-[12px] file:text-forest" /></Field>
              <Field label="Title" htmlFor="doc-title" hint="Defaults to the file name"><Input id="doc-title" value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
              <Field label="Trust level" htmlFor="doc-trust" hint="Untrusted sources are still scanned for injected instructions on every retrieval.">
                <Select id="doc-trust" value={trust} onChange={(e) => setTrust(e.target.value)}><option value="trusted">Trusted (official policy)</option><option value="untrusted">Untrusted (wiki, imports)</option></Select>
              </Field>
              {error && <ErrorState message={error} />}
              <Button type="submit" loading={busy} className="w-full"><Upload className="h-4 w-4" />Upload and index</Button>
            </form>
          </Section>
        )}
      </div>
      <Dialog open={viewId !== null} onClose={() => setViewId(null)} title={detail.data?.title ?? "Document"} description={detail.data ? `${detail.data.chunk_count} chunks · ${detail.data.trust_level}` : undefined} side>
        {!detail.data ? <LoadingRows rows={4} /> : (
          <ol className="space-y-3">
            {detail.data.chunks.map((c) => (
              <li key={c.id} className="rounded-xl border border-hair bg-white/50 p-3 text-[13px]">
                <p className="eyebrow mb-1">Chunk {c.ordinal + 1}{c.heading ? ` · ${c.heading}` : ""}</p>
                <p className="whitespace-pre-wrap leading-relaxed text-ink-700">{c.text}</p>
              </li>
            ))}
          </ol>
        )}
      </Dialog>
    </>
  );
}
