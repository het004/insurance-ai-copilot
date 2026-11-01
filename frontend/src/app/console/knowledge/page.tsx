"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { BookOpenText, Database, FileText, Loader2, Mic, Pause, Search, Upload, Volume2 } from "lucide-react";
import type { KnowledgeAnswer, KnowledgeSource } from "@/types";
import { consoleApi as api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ErrorBanner, PageContainer, PageHeader } from "@/components/page-header";
import { Citations } from "@/features/chat/card-renderer";
import { useSpeechRecognition } from "@/hooks/use-speech-recognition";
import { useSpeechSynthesis } from "@/hooks/use-speech-synthesis";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "Does my car insurance cover flood damage?",
  "What documents do I need for a theft claim?",
  "How does No Claim Bonus work?",
  "What is excluded under motor insurance?",
  "Can I cancel my policy and get a refund?",
  "What is a super top-up?",
];

export default function KnowledgePage() {
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState<KnowledgeAnswer | null>(null);
  const [asked, setAsked] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [mode, setMode] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const tts = useSpeechSynthesis();

  const loadSources = () => api.sources().then((r) => { setSources(r.sources); setMode(r.retrieval_mode); }).catch(() => {});
  useEffect(() => { loadSources(); }, []);

  const ask = async (question: string, speak = false) => {
    const text = question.trim();
    if (!text) return;
    setQ(text);
    setAsked(text);
    setLoading(true);
    setError(null);
    tts.stop();
    try {
      const a = await api.ask(text);
      setAnswer(a);
      if (speak) tts.speak(a.answer, "kb");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };
  const stt = useSpeechRecognition({ onFinal: (t) => ask(t, true) });

  const onUpload = async (f?: File) => {
    if (!f) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const r = await api.upload(f);
      setUploadMsg(`Indexed ${r.source} into ${r.chunks} chunk(s). Ask a question about it!`);
      loadSources();
    } catch (e) {
      setUploadMsg((e as Error).message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <PageContainer className="space-y-5">
      <PageHeader title="Knowledge assistant" subtitle="Manage the documents the Copilot answers from — upload, test questions, inspect sources" icon={<BookOpenText className="size-5" />} />

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-4">
          <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="glass flex items-center gap-2 rounded-2xl p-2">
            <Search className="ml-2 size-5 shrink-0 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about coverage, claims, exclusions…"
              className="h-12 border-0 bg-transparent focus-visible:ring-0" />
            <button type="button" onClick={stt.toggle} aria-label="Ask by voice"
              className={cn("grid size-12 shrink-0 place-items-center rounded-xl", stt.listening ? "bg-danger text-white" : "bg-muted")}>
              <Mic className="size-5" />
            </button>
            <Button type="submit" size="icon" className="size-12" disabled={loading || !q.trim()} aria-label="Ask">
              {loading ? <Loader2 className="animate-spin" /> : <Search />}
            </Button>
          </form>
          {stt.listening && <p className="px-2 text-sm text-danger">Listening… {stt.transcript}</p>}
          {stt.error && <p className="px-2 text-sm text-danger">{stt.error}</p>}

          {!answer && !loading && (
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => ask(s)} className="glass rounded-full px-3.5 py-2 text-sm hover:border-primary/40">{s}</button>
              ))}
            </div>
          )}
          {error && <ErrorBanner message={error} />}

          <AnimatePresence mode="wait">
            {loading && (
              <motion.div key="l" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <Card className="space-y-3 p-5">
                  <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Retrieving from knowledge base…</p>
                  <div className="h-3 w-3/4 animate-pulse rounded bg-muted" /><div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
                </Card>
              </motion.div>
            )}
            {answer && !loading && (
              <motion.div key={asked} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <Card className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium text-muted-foreground">“{asked}”</p>
                    <button onClick={() => (tts.speaking ? tts.stop() : tts.speak(answer.answer, "kb"))}
                      className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs text-muted-foreground hover:bg-muted">
                      {tts.speaking ? <Pause className="size-3.5" /> : <Volume2 className="size-3.5" />} {tts.speaking ? "Stop" : "Listen"}
                    </button>
                  </div>
                  <div className="markdown mt-3"><ReactMarkdown>{answer.answer}</ReactMarkdown></div>
                  <div className="mt-3 flex gap-2">
                    <Badge variant="muted">{answer.mode === "gemini" ? "AI grounded answer" : "Extractive answer (offline)"}</Badge>
                    <Badge variant="muted">{answer.retrieval === "vector" ? "ChromaDB vector search" : "Keyword retrieval"}</Badge>
                  </div>
                  <Citations citations={answer.sources} className="mt-4 border-t border-border pt-4" />
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle><Database className="size-4 text-primary" /> Knowledge sources</CardTitle>
            <Badge variant="muted">{mode === "vector" ? "ChromaDB" : "Keyword"}</Badge>
          </CardHeader>
          <CardContent className="space-y-2">
            {sources.map((s) => (
              <div key={s.source} className="flex items-center gap-2.5 rounded-xl bg-muted/50 px-3 py-2">
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{s.title}</p>
                  <p className="text-[11px] text-muted-foreground">{s.chunks} chunks{s.uploaded ? " · uploaded" : ""}</p>
                </div>
              </div>
            ))}
            <input ref={fileRef} type="file" accept=".pdf,.md,.txt" className="hidden" onChange={(e) => onUpload(e.target.files?.[0])} />
            <Button variant="outline" className="mt-2 w-full" disabled={uploading} onClick={() => fileRef.current?.click()}>
              {uploading ? <Loader2 className="animate-spin" /> : <Upload />} Upload policy document
            </Button>
            <p className="text-[11px] text-muted-foreground">PDF, Markdown or text. It's chunked, embedded and searchable immediately — also from the AI Copilot chat.</p>
            {uploadMsg && <p className="text-xs text-primary">{uploadMsg}</p>}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}
