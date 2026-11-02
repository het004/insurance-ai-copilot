"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Car, HeartHandshake, HeartPulse, House, Loader2, PanelRightOpen, Sprout, RotateCcw, SendHorizontal, Sparkles,
  UserRoundCheck, Volume2, VolumeX } from "lucide-react";
import type { AgentRun, ChatMessage, Identity, VoiceState } from "@/types";
import { IdentityChip } from "@/features/identity/identity-cards";
import { ASSISTANT_NAME, ASSISTANT_NAME_AR, INSURER_NAME, INSURER_SHORT } from "@/lib/brand";
import { SPEECH_LANG } from "@/lib/utils";
import { api } from "@/services/api";
import { useSpeechRecognition } from "@/hooks/use-speech-recognition";
import { useSpeechSynthesis } from "@/hooks/use-speech-synthesis";
import { VoiceOrb, VoiceStatus, Waveform, VOICE_LABEL } from "@/components/voice-orb";
import { MessageBubble, ThinkingIndicator } from "./message-bubble";
import { ActivityPanel } from "./activity-panel";
import { applyEvent, newRun } from "./run-state";
import { cn } from "@/lib/utils";

const STORE = "copilot.chat.v3";
export const PORTFOLIO_PROMPTS = [
  { label: "Motor", q: "I want motor insurance" },
  { label: "Health", q: "I want an individual health plan" },
  { label: "Life", q: "I want a life protection plan" },
  { label: "Retirement & Savings", q: "I want a retirement savings plan" },
  { label: "General (home)", q: "I want home insurance" },
];
export const EXAMPLE_PROMPTS = [
  "What policies do I have?",
  "I had an accident",
  "Renew my policy",
  "Is sandstorm damage covered?",
];
export const START_PROMPTS = {
  existing: `I'm an existing ${INSURER_SHORT} customer`,
  new: "I'm a new customer",
};

const uid = () => Math.random().toString(36).slice(2, 10);

interface Stored { sessionId?: string; messages: ChatMessage[]; runs: AgentRun[] }
function load(): Stored {
  try {
    const s = JSON.parse(localStorage.getItem(STORE) || "") as Stored;
    // a run that was mid-flight when the page closed can't resume
    s.runs = (s.runs || []).map((r) => (r.status === "running" ? { ...r, status: "error" as const } : r));
    return { messages: s.messages || [], runs: s.runs, sessionId: s.sessionId };
  } catch {
    return { messages: [], runs: [] };
  }
}

export function ChatView() {
  const params = useSearchParams();
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);        // desktop column
  const [drawerOpen, setDrawerOpen] = useState(false);     // mobile / tablet drawer
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [hydrated, setHydrated] = useState(false);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [lang, setLang] = useState<"en" | "ar">("en");
  const [adjusting, setAdjusting] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const handled = useRef(false);

  const tts = useSpeechSynthesis();

  // ---- persistence (conversation + run history survive reloads)
  useEffect(() => {
    const s = load();
    setMessages(s.messages);
    setRuns(s.runs);
    setSessionId(s.sessionId);
    if (s.sessionId) api.identity(s.sessionId).then(setIdentity).catch(() => setIdentity(null));
    try {
      setAutoSpeak(localStorage.getItem("copilot.autoSpeak") !== "0");
      setPanelOpen(localStorage.getItem("copilot.panel") !== "0");
      setLang(localStorage.getItem("copilot.lang") === "ar" ? "ar" : "en");
    } catch {}
    setHydrated(true);
  }, []);
  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORE, JSON.stringify({ sessionId, messages: messages.slice(-60), runs: runs.slice(-30) }));
    } catch {}
  }, [messages, runs, sessionId, hydrated]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(
    async (text: string, viaVoice = false) => {
      const content = text.trim();
      if (!content || loading) return;
      tts.stop();
      setInput("");
      setMessages((m) => [...m, { id: uid(), role: "user", content, createdAt: Date.now(), viaVoice }]);
      setLoading(true);

      let run = newRun(content);
      setRuns((r) => [...r, run]);
      setSelectedRun(null); // follow the live run
      const commit = (next: AgentRun) => {
        const prevId = run.id;
        run = next;
        setRuns((rs) => rs.map((r) => (r.id === prevId ? next : r)));
      };

      try {
        await api.chatStream(content, sessionId, (ev) => {
          commit(applyEvent(run, ev));
          if (ev.type === "run_started") {
            setSessionId(ev.session_id);
            setIdentity(ev.identity);
          }
          if (ev.type === "final") {
            if (ev.identity) setIdentity(ev.identity);
            const id = uid();
            commit({ ...run, messageId: id });
            setMessages((m) => [...m, {
              id, role: "assistant", content: ev.reply, createdAt: Date.now(), tools: ev.tools_used, cards: ev.cards,
              citations: ev.citations, mode: ev.mode, notice: ev.notice, runId: run.id,
            }]);
            if (autoSpeak || viaVoice) tts.speak(ev.reply, id);
          }
          if (ev.type === "error") throw new Error(ev.message);
        }, lang);
        if (run.status === "running") throw new Error("The connection closed before Amaan finished.");
      } catch (e) {
        commit(applyEvent(run, { type: "error", message: (e as Error).message }));
        setMessages((m) => [...m, { id: uid(), role: "assistant", content: (e as Error).message, createdAt: Date.now(), error: true, runId: run.id }]);
      } finally {
        setLoading(false);
      }
    },
    [loading, sessionId, autoSpeak, tts, lang],
  );

  /** Slider / toggle on a quote card → live re-price; the run streams into the What's happening panel. */
  const adjust = useCallback(async (messageId: string, quoteId: string, changes: Record<string, unknown>) => {
    setAdjusting(quoteId);
    let run = newRun("Adjusted the quote");
    setRuns((r) => [...r, run]);
    setSelectedRun(null);
    const commit = (next: AgentRun) => {
      const prevId = run.id;
      run = next;
      setRuns((rs) => rs.map((r) => (r.id === prevId ? next : r)));
    };
    try {
      await api.repriceStream(quoteId, changes, sessionId, (ev) => {
        commit(applyEvent(run, ev));
        if (ev.type === "run_started" && "message" in ev && ev.message) commit({ ...run, prompt: String(ev.message) });
        if (ev.type === "final" && ev.cards?.[0]) {
          const nq = ev.cards[0];
          setMessages((ms) => ms.map((m) => (m.id !== messageId ? m : {
            ...m, cards: m.cards?.map((c) => (c.type === "quote" && c.data.quote_id === ev.replaces_quote ? nq : c)),
          })));
        }
        if (ev.type === "error") throw new Error(ev.message);
      });
    } catch (e) {
      commit(applyEvent(run, { type: "error", message: (e as Error).message }));
    } finally {
      setAdjusting(null);
    }
  }, [sessionId]);

  const switchLang = (next: "en" | "ar") => {
    setLang(next);
    try { localStorage.setItem("copilot.lang", next); } catch {}
  };

  const [serverStt, setServerStt] = useState(false);
  useEffect(() => { api.health().then((h) => setServerStt(!!h.stt_server)).catch(() => {}); }, []);
  const stt = useSpeechRecognition({ onFinal: (t) => send(t, true), lang: lang === "ar" ? "ar-SA" : SPEECH_LANG, server: serverStt });

  // ---- deep links: /chat?q=...  and /chat?voice=1
  useEffect(() => {
    if (!hydrated || handled.current) return;
    const q = params.get("q");
    const voice = params.get("voice");
    if (!q && !voice) return;
    handled.current = true;
    router.replace("/chat");
    if (q) send(q);
    else if (voice) stt.start();
  }, [hydrated, params, router, send, stt]);

  const voiceState: VoiceState = stt.listening ? "listening" : loading ? "processing" : tts.speaking ? "speaking" : "idle";
  const onOrb = () => {
    if (voiceState === "listening") stt.stop();
    else if (voiceState === "speaking") tts.stop();
    else if (voiceState === "idle") stt.start();
  };

  const reset = () => {
    tts.stop();
    if (sessionId) api.resetChat(sessionId).catch(() => {});
    setSessionId(undefined);
    setMessages([]);
    setRuns([]);
    setSelectedRun(null);
    setIdentity(null);
  };

  const toggleAutoSpeak = () => {
    const next = !autoSpeak;
    setAutoSpeak(next);
    if (!next) tts.stop();
    try {
      localStorage.setItem("copilot.autoSpeak", next ? "1" : "0");
    } catch {}
  };

  const setDesktopPanel = (open: boolean) => {
    setPanelOpen(open);
    try {
      localStorage.setItem("copilot.panel", open ? "1" : "0");
    } catch {}
  };

  const showRun = (runId?: string) => {
    if (!runId) return;
    setSelectedRun(runId);
    setDesktopPanel(true);
    setDrawerOpen(true);
  };

  const empty = hydrated && messages.length === 0;
  const lastAssistant = useMemo(() => [...messages].reverse().find((m) => m.role === "assistant" && !m.error), [messages]);
  const liveRun = runs[runs.length - 1];
  const running = liveRun?.status === "running";
  const liveStep = running ? [...liveRun.steps].reverse().find((s) => s.status === "running") : undefined;

  const panelProps = { runs, selectedId: selectedRun, onSelect: setSelectedRun, voice: voiceState };

  return (
    <div className="flex h-full gap-3 p-3 md:gap-4 md:p-4">
      {/* ============ LEFT: conversation ============ */}
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-card-solid/80 shadow-card">
        <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            <h1 className="hidden truncate text-sm font-semibold tracking-tight sm:block md:text-base">
              {ASSISTANT_NAME} <span className="arabic font-bold text-primary" lang="ar">{ASSISTANT_NAME_AR}</span>
            </h1>
            <IdentityChip identity={identity} />
            <VoiceStatus state={voiceState} />
          </div>
          <div className="flex items-center gap-1">
            <div className="mr-1 flex rounded-lg border border-border p-0.5 text-xs" role="group" aria-label="Language">
              <button onClick={() => switchLang("en")} className={cn("rounded-md px-2 py-1", lang === "en" ? "bg-primary text-white" : "text-muted-foreground")}>EN</button>
              <button onClick={() => switchLang("ar")} className={cn("arabic rounded-md px-2 py-1", lang === "ar" ? "bg-primary text-white" : "text-muted-foreground")} lang="ar">عربي</button>
            </div>
            {lastAssistant && (
              <button onClick={() => tts.speak(lastAssistant.content, lastAssistant.id)} title="Replay last response"
                className="hidden h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs text-muted-foreground hover:bg-muted sm:inline-flex">
                <RotateCcw className="size-3.5" /> Replay
              </button>
            )}
            <button onClick={toggleAutoSpeak} title={autoSpeak ? "Auto-speak on" : "Auto-speak off"}
              className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted">
              {autoSpeak ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
            </button>
            {messages.length > 0 && (
              <button onClick={reset} className="h-9 rounded-lg px-2.5 text-xs text-muted-foreground hover:bg-muted">New chat</button>
            )}
            {/* open panel: drawer below lg, column on lg+ when collapsed */}
            <button onClick={() => setDrawerOpen(true)} aria-label="What's happening"
              className="relative grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted lg:hidden">
              {running ? <Loader2 className="size-4 animate-spin text-primary" /> : <Sparkles className="size-4" />}
            </button>
            {!panelOpen && (
              <button onClick={() => setDesktopPanel(true)} aria-label="Show what's happening"
                className="hidden h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs text-muted-foreground hover:bg-muted lg:inline-flex">
                {running ? <Loader2 className="size-3.5 animate-spin text-primary" /> : <PanelRightOpen className="size-3.5" />}
                What&apos;s happening
              </button>
            )}
          </div>
        </div>

        <div ref={scrollRef} className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-5">
            {empty && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center pt-4 text-center md:pt-10">
                <VoiceOrb state={voiceState} onClick={onOrb} size="lg" />
                <p className="arabic mt-6 text-lg font-bold text-primary" lang="ar" dir="rtl">أهلاً وسهلاً</p>
                <h2 className="mt-1 text-2xl font-semibold tracking-tight md:text-3xl">
                  Ahlan wa sahlan! I&apos;m <span className="text-gradient">{ASSISTANT_NAME}</span>, your {INSURER_SHORT} assistant
                </h2>
                <p className="mt-2 max-w-md text-sm text-muted-foreground">
                  Which plan are you looking for? Pick one, or just talk — I&apos;ll verify you with Nafath and fetch your details for you.
                </p>
                <div className="mt-6 grid w-full grid-cols-2 gap-2.5 sm:grid-cols-5">
                  {PORTFOLIO_PROMPTS.map(({ label, q }, i) => {
                    const Icon = [Car, HeartPulse, HeartHandshake, Sprout, House][i];
                    return (
                      <button key={label} onClick={() => send(q)}
                        className={cn("flex flex-col items-center gap-2 rounded-2xl border border-border bg-card-solid p-4 text-center text-sm font-medium text-navy shadow-card transition hover:-translate-y-0.5 hover:border-primary/50",
                          i === 4 && "col-span-2 sm:col-span-1")}>
                        <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="size-5" /></span>
                        {label}
                      </button>
                    );
                  })}
                </div>
                <button onClick={() => send(START_PROMPTS.existing)}
                  className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-primary/30 px-4 py-3 text-sm font-medium text-primary transition hover:bg-primary/5">
                  <UserRoundCheck className="size-4" /> Already with {INSURER_SHORT}? Manage your plans and claims
                </button>
                <p className="mt-6 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Or just ask</p>
                <div className="mt-2 flex flex-wrap justify-center gap-2">
                  {EXAMPLE_PROMPTS.map((p) => (
                    <button key={p} onClick={() => send(p)}
                      className="rounded-full border border-border bg-card-solid px-4 py-2 text-sm text-navy transition hover:border-primary/40 hover:text-primary">
                      {p}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
            {messages.map((m, i) => (
              <MessageBubble key={m.id} msg={m} speaking={tts.speakingId === m.id}
                onAdjust={loading ? undefined : (qid, ch) => adjust(m.id, qid, ch)} adjusting={adjusting}
                onSpeak={() => tts.speak(m.content, m.id)} onStop={tts.stop}
                interactive={i === messages.length - 1 && !loading} onPrompt={(p) => send(p)}
                onShowRun={m.runId ? () => showRun(m.runId) : undefined} />
            ))}
            {loading && <ThinkingIndicator label={liveStep?.label} onClick={() => setDrawerOpen(true)} />}
          </div>
        </div>

        <div className="px-3 pb-3 md:px-4 md:pb-4">
          <div className="mx-auto max-w-3xl">
            <AnimatePresence>
              {(stt.listening || stt.error || stt.transcript) && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
                  className={cn("mb-2 flex items-center gap-3 rounded-2xl border border-border bg-card-solid/70 px-4 py-3 text-sm",
                    stt.error && !stt.listening && "border-danger/40 text-danger")}>
                  {stt.listening || stt.transcript ? (
                    <>
                      <Waveform active className="text-danger" />
                      <span className="min-w-0 flex-1 truncate">{stt.transcript || <span className="text-muted-foreground">{VOICE_LABEL.listening} speak now</span>}</span>
                      <button onClick={stt.stop} className="text-xs font-medium text-muted-foreground hover:text-foreground">Done</button>
                    </>
                  ) : (
                    <>
                      <span className="flex-1">{stt.error}</span>
                      <button onClick={stt.clearError} className="text-xs underline">Dismiss</button>
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
            <form onSubmit={(e) => { e.preventDefault(); send(input); }}
              className="flex items-end gap-2 rounded-3xl border border-border bg-card-solid/70 p-2 shadow-lg shadow-black/5">
              <VoiceOrb state={voiceState} onClick={onOrb} />
              <textarea value={input} rows={1} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
                placeholder={lang === "ar" ? "اكتب رسالتك أو اضغط على المايك…" : stt.supported ? `Ask ${ASSISTANT_NAME} anything, or tap the mic…` : "Type your message…"}
                dir={lang === "ar" ? "rtl" : "ltr"}
                className="max-h-36 min-h-14 min-w-0 flex-1 resize-none bg-transparent px-2 py-4 text-[15px] outline-none placeholder:text-muted-foreground" />
              <button type="submit" disabled={!input.trim() || loading} aria-label="Send"
                className="grid size-14 shrink-0 place-items-center rounded-full bg-brand text-white transition disabled:opacity-25">
                <SendHorizontal className="size-5" />
              </button>
            </form>
            <p className="mt-2 text-center text-[10px] text-muted-foreground">Proof of concept for {INSURER_NAME} · individual plans · prices, Nafath/Yakeen checks and payments are simulated</p>
          </div>
        </div>
      </section>

      {/* ============ RIGHT: "What's happening" (desktop column) ============ */}
      <AnimatePresence initial={false}>
        {panelOpen && (
          <motion.div key="panel" initial={{ width: 0, opacity: 0 }} animate={{ width: 360, opacity: 1 }} exit={{ width: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }} className="hidden shrink-0 overflow-hidden lg:flex">
            <ActivityPanel {...panelProps} onClose={() => setDesktopPanel(false)} className="w-[360px]" />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ============ RIGHT: drawer for mobile / tablet ============ */}
      <AnimatePresence>
        {drawerOpen && (
          <motion.div key="drawer" className="fixed inset-0 z-50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <button aria-label="Close" className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setDrawerOpen(false)} />
            <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 320, damping: 34 }}
              className="absolute inset-y-0 right-0 flex w-full max-w-sm p-3"
              style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top))", paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}>
              <ActivityPanel {...panelProps} onClose={() => setDrawerOpen(false)} className="w-full bg-card-solid" />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
