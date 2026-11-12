"use client";

import { Hash, LayoutDashboard, LogOut, Menu, Plus, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Composer, type ComposerMode } from "@/components/assistant/composer";
import { MessageView } from "@/components/assistant/message";
import { Logo } from "@/components/brand/logo";
import { Dot } from "@/components/ui/badge";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { CONSOLE_PERMISSIONS, useAuth } from "@/hooks/useAuth";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { readableMasks, ROLE_LABELS, timeAgo } from "@/lib/format";
import type { AgentActionItem, ChatMessage, ChatResponse, ConversationDetail, ConversationSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "What is the international vendor refund policy?",
  "Can I expense a client dinner abroad?",
  "How many days of unused leave can I carry forward?",
  "How quickly must I report a lost laptop?",
];

const STATUS_DOT: Record<string, string> = { verified: "text-sage", redacted: "text-lilac-700", needs_review: "text-amber", blocked: "text-crimson" };

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function AssistantPage() {
  const { user, loading, logout, can } = useAuth();
  const orgName = user?.organization?.name ?? "Your organization";
  const router = useRouter();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [lastPrompt, setLastPrompt] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [mode, setMode] = useState<ComposerMode>("ask");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Deep link from the connected workspace / Slack: /assistant?c=<conversation id>
    const c = Number(new URLSearchParams(window.location.search).get("c"));
    if (c) setActiveId(c);
  }, []);
  useEffect(() => {
    if (!loading && !user) router.replace("/login?next=/assistant");
    else if (!loading && user && !can("assistant:use")) router.replace("/console");
  }, [loading, user, can, router]);

  const convs = useApi<ConversationSummary[]>(user ? "/assistant/conversations" : null);
  const hasPending = messages.some((m) => m.status === "pending_review");
  const detail = useApi<ConversationDetail>(activeId ? `/assistant/conversations/${activeId}` : null, hasPending ? 6000 : undefined);

  useEffect(() => {
    if (detail.data && detail.data.id === activeId) setMessages(detail.data.messages);
  }, [detail.data, activeId]);
  useEffect(() => {
    if (!hasPending && activeId) void convs.reload();
  }, [hasPending]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [messages.length, sending]);

  const send = useCallback(async (text?: string) => {
    const prompt = (text ?? draft).trim();
    if (!prompt) return;
    setSending(true);
    setError(null);
    setLastPrompt(prompt);
    setDraft("");
    const optimistic: ChatMessage = {
      id: -Date.now(), conversation_id: activeId ?? 0, role: "user", content: prompt, status: "delivered", trust_status: null,
      request_id: "", explanation: null, citations: [], created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, optimistic]);
    try {
      if (mode === "action") {
        const action = await api<AgentActionItem>("/agent/actions", { method: "POST", body: {
          request: prompt, conversation_id: activeId, record_in_conversation: true, idempotency_key: crypto.randomUUID?.() } });
        const conv = await api<ConversationDetail>(`/assistant/conversations/${action.conversation_id}`);
        setMessages(conv.messages);
        if (action.conversation_id !== activeId) setActiveId(action.conversation_id);
        void convs.reload();
        return;
      }
      const res = await api<ChatResponse>("/assistant/chat", { method: "POST", body: { message: prompt, conversation_id: activeId } });
      setMessages((m) => [...m.filter((x) => x.id !== optimistic.id), res.user_message, res.message]);
      if (res.conversation_id !== activeId) setActiveId(res.conversation_id);
      void convs.reload();
    } catch (e) {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setDraft(prompt);
      setError(e instanceof ApiError ? e : new ApiError(0, "error", "Something went wrong."));
    } finally {
      setSending(false);
    }
  }, [draft, activeId, convs, mode]);

  const openConversation = (id: number | null) => {
    setActiveId(id);
    setMessages([]);
    setError(null);
    setDrawer(false);
  };

  if (loading || !user) {
    return <div className="flex h-screen items-center justify-center"><Skeleton className="h-10 w-48" /></div>;
  }

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-5 pb-4 pt-5">
        <Logo href="/assistant" />
        <button className="rounded-full p-1.5 hover:bg-ink/5 lg:hidden" onClick={() => setDrawer(false)} aria-label="Close menu"><X className="h-4 w-4" /></button>
      </div>
      <div className="px-3">
        <button onClick={() => openConversation(null)} className="flex w-full items-center gap-2 rounded-xl border border-hair bg-white/60 px-3 py-2.5 text-[13.5px] font-medium transition hover:border-forest/40" data-testid="new-chat">
          <Plus className="h-4 w-4 text-forest" /> New conversation
        </button>
      </div>
      <p className="eyebrow px-5 pb-2 pt-6">History</p>
      <nav className="scrollbar-thin flex-1 space-y-0.5 overflow-y-auto px-3" aria-label="Conversation history">
        {convs.loading && <div className="space-y-2 px-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-9" />)}</div>}
        {convs.data?.length === 0 && <p className="px-2 text-[13px] text-ink-500">Your conversations will appear here.</p>}
        {convs.data?.map((c) => (
          <button
            key={c.id}
            onClick={() => openConversation(c.id)}
            className={cn("group flex w-full items-start gap-2.5 rounded-xl px-3 py-2 text-left transition", c.id === activeId ? "bg-lilac/60" : "hover:bg-ink/[0.04]")}
          >
            <Dot className={cn("mt-2", STATUS_DOT[c.last_trust_status ?? "verified"])} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13.5px]">{readableMasks(c.title)}</span>
              <span className="block text-[11.5px] text-ink-400">{c.pending_reviews ? "Awaiting review · " : ""}{timeAgo(c.updated_at)}</span>
            </span>
          </button>
        ))}
      </nav>
      <div className="border-t border-hair p-3">
        <Link href="/workspace" className="mb-1 flex items-center gap-2 rounded-xl px-3 py-2 text-[13px] text-ink-700 hover:bg-ink/[0.04]" data-testid="open-workspace"><Hash className="h-4 w-4" />Team channels</Link>
        {CONSOLE_PERMISSIONS.some(can) && (
          <Link href="/console" className="mb-1 flex items-center gap-2 rounded-xl px-3 py-2 text-[13px] text-ink-700 hover:bg-ink/[0.04]"><LayoutDashboard className="h-4 w-4" />Open console</Link>
        )}
        <div className="flex items-center justify-between rounded-xl px-3 py-2">
          <div className="min-w-0">
            <p className="truncate text-[13.5px] font-medium">{user.full_name}</p>
            <p className="text-[11.5px] text-ink-500">{ROLE_LABELS[user.primary_role] ?? user.primary_role} · {user.department}</p>
          </div>
          <button onClick={logout} className="rounded-full p-2 text-ink-500 hover:bg-ink/5 hover:text-ink" aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="hidden w-[280px] shrink-0 border-r border-hair bg-cream-50/70 lg:block">{sidebar}</aside>
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/20" onClick={() => setDrawer(false)} />
          <aside className="relative h-full w-[290px] bg-cream shadow-lift animate-rise">{sidebar}</aside>
        </div>
      )}

      <main id="main" className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-hair px-4 sm:px-6">
          <div className="flex items-center gap-2">
            <button className="rounded-full p-2 hover:bg-ink/5 lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu"><Menu className="h-4 w-4" /></button>
            <h1 className="font-sans text-[14px] font-medium text-ink-700">{orgName} Assistant</h1>
          </div>
          <p className="flex items-center gap-1.5 text-[12px] text-ink-500"><ShieldCheck className="h-3.5 w-3.5 text-forest" />Protected by TrustShield</p>
        </header>

        <div className="scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
            {!activeId && messages.length === 0 ? (
              <div className="pt-[8vh] animate-rise">
                <p className="eyebrow">{orgName} internal assistant</p>
                <h2 className="mt-3 text-[40px] leading-tight sm:text-[48px]">{greeting()}, {user.full_name.split(" ")[0]}.</h2>
                <p className="mt-3 max-w-lg text-ink-700">Ask about expenses, leave, procurement, IT access or security. Answers cite {orgName} policy, and requests are checked before they reach the AI model.</p>
                <div className="mt-10 grid gap-2.5 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => void send(s)} disabled={sending} className="rounded-2xl border border-hair bg-cream-50 px-4 py-3.5 text-left text-[14px] leading-snug transition hover:border-forest/40 hover:bg-white" data-testid="suggestion">
                      {s}
                    </button>
                  ))}
                </div>
                <p className="mt-8 text-[12.5px] text-ink-500">Please don&apos;t paste customer or colleague personal data. If you do, TrustShield masks it before it reaches the model.</p>
              </div>
            ) : (
              <div className="space-y-7" aria-live="polite">
                {detail.loading && messages.length === 0 && <div className="space-y-4"><Skeleton className="ml-auto h-10 w-2/3" /><Skeleton className="h-28 w-5/6" /></div>}
                {detail.error && messages.length === 0 && <ErrorState message={detail.error.message} onRetry={detail.reload} />}
                {messages.map((m) => <MessageView key={m.id} message={m} />)}
                {sending && (
                  <div className="flex items-center gap-3 text-[13px] text-ink-500" role="status">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-forest-50"><ShieldCheck className="h-4 w-4 text-forest" /></span>
                    <span className="flex gap-1">{[0, 1, 2].map((i) => <span key={i} className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-forest" style={{ animationDelay: `${i * 150}ms` }} />)}</span>
                    {mode === "action" ? "Checking permissions and approval rules…" : "Checking policies…"}
                  </div>
                )}
              </div>
            )}
            {error && (
              <div className="mt-6">
                <ErrorState message={error.message} requestId={error.requestId} onRetry={lastPrompt ? () => void send(lastPrompt) : undefined} />
              </div>
            )}
            <div ref={bottom} />
          </div>
        </div>

        <div className="border-t border-hair bg-cream/90 px-4 pb-5 pt-3 backdrop-blur sm:px-6">
          <div className="mx-auto max-w-3xl">
            <Composer value={draft} onChange={setDraft} onSend={() => void send()} busy={sending} mode={mode} onModeChange={can("actions:request") ? setMode : undefined} />
            <p className="mt-2 text-center text-[11.5px] text-ink-400">Answers are checked against {orgName} policy. Confidence scores are risk signals, not guarantees.</p>
          </div>
        </div>
      </main>
    </div>
  );
}
