"use client";

import { ArrowUp, ExternalLink, Hash, Hourglass, LayoutDashboard, LogOut, Menu, MessageSquareText, ShieldCheck, ShieldX, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { RichText } from "@/components/assistant/message";
import { ShieldMark } from "@/components/brand/logo";
import { TrustBadge } from "@/components/trust/badges";
import { Badge } from "@/components/ui/badge";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { CONSOLE_PERMISSIONS, useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { ENTITY_LABELS, timeAgo } from "@/lib/format";
import type { WorkspaceChannel, WorkspaceItem, WorkspaceReply } from "@/lib/types";
import { cn } from "@/lib/utils";

function initials(name: string) {
  return name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}

function BotReply({ reply, mine }: { reply: WorkspaceReply; mine: boolean }) {
  if (reply.kind === "private") {
    return <p className="text-[12.5px] italic text-ink-500">{reply.text}</p>;
  }
  if (reply.kind === "notice") {
    return <p className="rounded-xl bg-amber-100/60 px-3 py-2 text-[13px] text-amber-700">{reply.text}</p>;
  }
  const pending = reply.status === "pending_review";
  const status = reply.trust_status ?? "verified";
  const e = reply.explanation;
  return (
    <div className={cn("rounded-2xl border px-4 py-3", pending ? "border-amber/30 bg-amber-100/40" : status === "blocked" ? "border-crimson/15 bg-crimson-100/40" : "border-hair bg-white/70")}>
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <TrustBadge status={status} warning={!!e?.warning} />
        {e?.reviewed && <span className="text-[11.5px] text-ink-500">Reviewed by Compliance</span>}
      </div>
      {pending ? (
        <p className="flex items-center gap-2 text-[13.5px] text-amber-700"><Hourglass className="h-3.5 w-3.5" />Your request is being reviewed by the compliance team. The answer will appear here.</p>
      ) : (
        <div className="text-[14px] leading-relaxed"><RichText text={reply.text} /></div>
      )}
      {status === "blocked" && e?.policies?.[0] && (
        <p className="mt-2 text-[12.5px] text-ink-700"><span className="font-medium">{e.policies[0].name}.</span> {e.policies[0].reason}</p>
      )}
      {status === "redacted" && e?.redactions?.length ? (
        <p className="mt-2 text-[12px] text-lilac-700">Masked: {e.redactions.map((r) => ENTITY_LABELS[r.entity_type] ?? r.entity_type).join(", ")}</p>
      ) : null}
      {!!reply.citations?.length && !pending && (
        <p className="mt-2 text-[12px] text-ink-500">Sources: {reply.citations.slice(0, 3).map((c) => `[${c.index}] ${c.title}`).join(" · ")}</p>
      )}
      {mine && reply.conversation_id && (
        <Link href={`/assistant?c=${reply.conversation_id}`} className="mt-2 inline-flex items-center gap-1 text-[12px] text-forest hover:underline">
          View in TrustShield <ExternalLink className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}

function Item({ item }: { item: WorkspaceItem }) {
  return (
    <li className="group animate-rise" data-testid="ws-item" data-trust={item.reply.trust_status ?? item.reply.kind}>
      <div className="flex gap-3">
        <span className={cn("mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[12px] font-semibold", item.is_mine ? "bg-forest text-cream" : "bg-lilac text-lilac-700")}>
          {initials(item.author.name)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px]"><span className="font-semibold">{item.author.name}</span> <span className="text-ink-500">· {item.author.department}</span> <span className="text-[11.5px] text-ink-400">{timeAgo(item.created_at)}</span>
            {item.source === "slack" && <Badge className="ml-2">via Slack</Badge>}</p>
          {item.withheld ? (
            <p className="mt-0.5 flex items-center gap-1.5 text-[13.5px] italic text-ink-500"><ShieldX className="h-3.5 w-3.5" />Message withheld by TrustShield policy.</p>
          ) : (
            <p className="mt-0.5 whitespace-pre-wrap text-[14.5px] leading-relaxed">{item.text}</p>
          )}
          <div className="mt-2 flex gap-2.5 border-l-2 border-forest/25 pl-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-forest-50"><ShieldMark className="h-4 w-4" /></span>
            <div className="min-w-0 flex-1">
              <p className="mb-1 text-[12px] font-semibold text-forest">TrustShield
                {item.is_mine && ["blocked", "needs_review"].includes(item.reply.trust_status ?? "") && <span className="font-normal text-ink-500"> · only you can see this</span>}</p>
              <BotReply reply={item.reply} mine={item.is_mine} />
            </div>
          </div>
        </div>
      </div>
    </li>
  );
}

export default function WorkspacePage() {
  const { user, loading, logout, can } = useAuth();
  const router = useRouter();
  const channels = useApi<WorkspaceChannel[]>(user ? "/workspace/channels" : null);
  const [active, setActive] = useState<WorkspaceChannel | null>(null);
  const [items, setItems] = useState<WorkspaceItem[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [drawer, setDrawer] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const pending = items.some((i) => i.is_mine && i.reply.status === "pending_review");
  const feed = useApi<WorkspaceItem[]>(active ? `/workspace/channels/${active.id}/messages` : null, pending ? 5000 : 15000);

  useEffect(() => {
    if (!loading && !user) router.replace("/login?next=/workspace");
  }, [loading, user, router]);
  useEffect(() => {
    if (!active && channels.data?.length) {
      const wanted = new URLSearchParams(window.location.search).get("channel");
      setActive(channels.data.find((c) => c.name === wanted) ?? channels.data[0]);
    }
  }, [channels.data, active]);
  useEffect(() => { if (feed.data) setItems(feed.data); }, [feed.data]);
  useEffect(() => bottom.current?.scrollIntoView({ block: "end" }), [items.length, active?.id]);

  const send = async () => {
    if (!active || !text.trim()) return;
    setSending(true);
    setError(null);
    const body = { text: text.trim(), client_msg_id: crypto.randomUUID?.() ?? String(Date.now()) };
    try {
      const item = await api<WorkspaceItem>(`/workspace/channels/${active.id}/messages`, { method: "POST", body });
      setItems((xs) => [...xs.filter((x) => x.event_id !== item.event_id), item]);
      setText("");
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "error", "Message not sent"));
    } finally {
      setSending(false);
    }
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (!sending) void send(); }
  };

  if (loading || !user) return <div className="flex h-screen items-center justify-center"><Skeleton className="h-10 w-48" /></div>;

  const sidebar = (
    <div className="flex h-full flex-col bg-forest text-cream">
      <div className="flex items-center justify-between px-5 pb-5 pt-5">
        <div className="flex items-center gap-2.5"><ShieldMark /><div><p className="font-serif text-[19px] leading-none">NovaCorp</p><p className="mt-1 text-[11px] text-cream/60">Connected workspace</p></div></div>
        <button className="rounded-full p-1.5 hover:bg-cream/10 lg:hidden" onClick={() => setDrawer(false)} aria-label="Close channels"><X className="h-4 w-4" /></button>
      </div>
      <p className="px-5 pb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-cream/50">Channels</p>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3" aria-label="Channels">
        {channels.loading && [0, 1, 2].map((i) => <div key={i} className="mx-2 my-2 h-6 animate-pulse rounded bg-cream/10" />)}
        {channels.data?.map((c) => (
          <button key={c.id} onClick={() => { setActive(c); setItems([]); setDrawer(false); }} aria-current={active?.id === c.id ? "page" : undefined}
            className={cn("flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-[14px] transition", active?.id === c.id ? "bg-cream/15 text-cream" : "text-cream/75 hover:bg-cream/[0.08] hover:text-cream")}>
            <Hash className="h-3.5 w-3.5 opacity-70" />{c.name}
          </button>
        ))}
      </nav>
      <div className="space-y-1 border-t border-cream/15 p-3 text-[13px]">
        <Link href="/assistant" className="flex items-center gap-2 rounded-xl px-3 py-2 text-cream/80 hover:bg-cream/[0.08]"><MessageSquareText className="h-4 w-4" />Private assistant</Link>
        {CONSOLE_PERMISSIONS.some(can) && <Link href="/console" className="flex items-center gap-2 rounded-xl px-3 py-2 text-cream/80 hover:bg-cream/[0.08]"><LayoutDashboard className="h-4 w-4" />Console</Link>}
        <div className="flex items-center justify-between rounded-xl px-3 py-2">
          <span className="min-w-0"><span className="block truncate font-medium">{user.full_name}</span><span className="text-[11.5px] text-cream/60">{user.department}</span></span>
          <button onClick={logout} className="rounded-full p-2 text-cream/70 hover:bg-cream/10" aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="hidden w-[260px] shrink-0 lg:block">{sidebar}</aside>
      {drawer && <div className="fixed inset-0 z-40 lg:hidden"><div className="absolute inset-0 bg-ink/30" onClick={() => setDrawer(false)} /><aside className="relative h-full w-[270px] animate-rise">{sidebar}</aside></div>}
      <main id="main" className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-[64px] flex-wrap items-center gap-x-4 gap-y-1 border-b border-hair px-4 py-3 sm:px-6">
          <button className="rounded-full p-2 hover:bg-ink/5 lg:hidden" onClick={() => setDrawer(true)} aria-label="Open channels"><Menu className="h-4 w-4" /></button>
          <div className="min-w-0 flex-1">
            <h1 className="flex items-center gap-1 font-sans text-[17px] font-semibold"><Hash className="h-4 w-4 text-ink-400" />{active?.name ?? "…"}</h1>
            <p className="truncate text-[12.5px] text-ink-500">{active?.description}</p>
          </div>
          {active?.policy_hint && (
            <p className="flex max-w-md items-center gap-1.5 rounded-full border border-forest/20 bg-forest-50 px-3 py-1 text-[12px] text-forest" data-testid="channel-hint">
              <ShieldCheck className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{active.policy_hint}</span>
            </p>
          )}
        </header>
        <div className="scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
            {feed.loading && !items.length ? <div className="space-y-6">{[0, 1].map((i) => <Skeleton key={i} className="h-32" />)}</div>
              : !items.length ? (
                <div className="py-16 text-center">
                  <p className="font-serif text-[28px]">Start the conversation in #{active?.name}</p>
                  <p className="mt-2 text-[14px] text-ink-500">Questions here are answered by TrustShield with the same policies, citations and review as the assistant.</p>
                </div>
              ) : <ul className="space-y-7" aria-live="polite">{items.map((i) => <Item key={i.event_id} item={i} />)}</ul>}
            {error && <div className="mt-4"><ErrorState message={error.message} requestId={error.requestId} /></div>}
            <div ref={bottom} />
          </div>
        </div>
        <div className="border-t border-hair px-4 pb-5 pt-3 sm:px-6">
          <form onSubmit={(e) => { e.preventDefault(); void send(); }} className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-ink/15 bg-white/80 p-2 pl-4 focus-within:border-forest focus-within:ring-2 focus-within:ring-forest/10">
            <label htmlFor="ws-input" className="sr-only">Message #{active?.name}</label>
            <textarea id="ws-input" rows={1} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKey} maxLength={4000}
              placeholder={`Message #${active?.name ?? ""}`} className="max-h-40 flex-1 resize-none bg-transparent py-2 text-[15px] placeholder:text-ink-400 focus:outline-none focus-visible:ring-0" data-testid="ws-input" />
            <button type="submit" disabled={!text.trim() || sending} aria-label="Send"
              className={cn("flex h-10 w-10 items-center justify-center rounded-xl transition", text.trim() && !sending ? "bg-forest text-cream" : "bg-ink/10 text-ink-400")}>
              {sending ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" /> : <ArrowUp className="h-4 w-4" />}
            </button>
          </form>
          <p className="mx-auto mt-2 max-w-3xl text-center text-[11.5px] text-ink-400">Every message is checked by TrustShield before it reaches the AI model.</p>
        </div>
      </main>
    </div>
  );
}
