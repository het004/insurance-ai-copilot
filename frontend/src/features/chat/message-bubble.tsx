"use client";

import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Mic, Pause, Volume2, Wrench, WifiOff } from "lucide-react";
import { BrandAvatar } from "@/components/app-shell";
import type { ChatMessage } from "@/types";
import { CardRenderer, Citations } from "./card-renderer";
import { cn, humanize } from "@/lib/utils";

export function ToolBadges({ tools, onShowRun }: { tools: ChatMessage["tools"]; onShowRun?: () => void }) {
  if (!tools?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tools.map((t, i) => (
        <button type="button" key={i} title={JSON.stringify(t.args)} onClick={onShowRun}
          className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium transition hover:brightness-110",
            t.ok ? "border-primary/30 bg-primary/8 text-primary" : "border-danger/30 bg-danger/8 text-danger")}>
          <Wrench className="size-3" /> {humanize(t.name)}
        </button>
      ))}
      {onShowRun && (
        <button type="button" onClick={onShowRun} className="text-[10px] text-muted-foreground underline-offset-2 hover:underline">
          view steps
        </button>
      )}
    </div>
  );
}

export function MessageBubble({
  msg, speaking, onSpeak, onStop, onPrompt, onShowRun, interactive = true, onAdjust, adjusting,
}: {
  onAdjust?: (quoteId: string, changes: Record<string, unknown>) => void;
  adjusting?: string | null;
  interactive?: boolean;
  msg: ChatMessage;
  speaking: boolean;
  onSpeak: () => void;
  onStop: () => void;
  onPrompt: (p: string) => void;
  onShowRun?: () => void;
}) {
  if (msg.role === "user") {
    return (
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-[15px] text-white shadow-md shadow-primary/20">
          {msg.viaVoice && <Mic className="mb-0.5 mr-1.5 inline size-3.5 opacity-80" />}
          {msg.content}
        </div>
      </motion.div>
    );
  }
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
      <BrandAvatar className="mt-1" />
      <div className="min-w-0 flex-1 space-y-3">
        <ToolBadges tools={msg.tools} onShowRun={onShowRun} />
        <div className={cn("rounded-2xl rounded-tl-md border border-border bg-card-solid px-4 py-3 shadow-card", msg.error && "border-danger/40 text-danger")}>
          <div className="markdown" dir="auto"><ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown></div>
        </div>
        {msg.cards?.map((c, i) => (
          <motion.div key={i} initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 + i * 0.08 }}>
            <CardRenderer card={c} onPrompt={interactive ? onPrompt : undefined} onAdjust={onAdjust} adjusting={adjusting} />
          </motion.div>
        ))}
        {!!msg.citations?.length && <Citations citations={msg.citations} />}
        {!msg.error && (
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <button onClick={speaking ? onStop : onSpeak}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2 hover:bg-muted hover:text-foreground"
              aria-label={speaking ? "Stop speaking" : "Play response aloud"}>
              {speaking ? <Pause className="size-3.5" /> : <Volume2 className="size-3.5" />}
              {speaking ? "Stop" : "Play"}
            </button>
            {msg.mode === "offline" && (
              <span className="inline-flex items-center gap-1" title={msg.notice || "Answered by the demo engine"}>
                <WifiOff className="size-3" /> demo engine
              </span>
            )}
            {msg.mode === "gemini" && <span>Amaan AI</span>}
          </div>
        )}
      </div>
    </motion.div>
  );
}

/** Inline progress line under the conversation; the full detail lives in the "What's happening" panel. */
export function ThinkingIndicator({ label, onClick }: { label?: string; onClick?: () => void }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
      <motion.span className="mt-1" animate={{ scale: [1, 1.08, 1] }} transition={{ repeat: Infinity, duration: 1.6 }}>
        <BrandAvatar />
      </motion.span>
      <button type="button" onClick={onClick}
        className="flex items-center gap-3 rounded-2xl rounded-tl-md border border-border bg-card-solid/60 px-4 py-3 text-left">
        <span className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <motion.span key={i} className="size-1.5 rounded-full bg-primary"
              animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 0.9, delay: i * 0.15 }} />
          ))}
        </span>
        <motion.span key={label} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="text-xs text-muted-foreground">
          {label || "Thinking"}…
        </motion.span>
      </button>
    </motion.div>
  );
}
