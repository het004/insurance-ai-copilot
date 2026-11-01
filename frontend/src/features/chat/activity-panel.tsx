"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle, Brain, CheckCircle2, ChevronDown, Cpu, Loader2, PanelRightClose, Sparkles, Volume2, Wrench, XCircle,
} from "lucide-react";
import type { AgentRun, RunStep, VoiceState } from "@/types";
import { cn, humanize } from "@/lib/utils";
import { fmtMs } from "./run-state";

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, [active]);
  return now;
}

function StepIcon({ step }: { step: RunStep }) {
  if (step.status === "running") return <Loader2 className="size-4 animate-spin text-primary" />;
  if (step.kind === "notice") return <AlertTriangle className="size-4 text-warning" />;
  if (step.status === "error") return <XCircle className="size-4 text-danger" />;
  if (step.kind === "tool") return <Wrench className="size-4 text-primary" />;
  return <CheckCircle2 className="size-4 text-success" />;
}

function ArgChips({ args }: { args?: Record<string, unknown> }) {
  const entries = Object.entries(args || {}).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!entries.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {entries.map(([k, v]) => (
        <span key={k} className="max-w-full truncate rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
          {k}: <span className="text-foreground">{typeof v === "string" ? v : JSON.stringify(v)}</span>
        </span>
      ))}
    </div>
  );
}

function SubStepRow({ step, now }: { step: RunStep; now: number }) {
  const dur = (step.endedAt ?? now) - step.startedAt;
  return (
    <motion.li initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} className="relative flex gap-2.5 pb-2.5 pl-9">
      <span className="absolute left-[11px] top-0 h-full w-px bg-border" />
      <span className={cn("mt-1 grid size-3.5 shrink-0 place-items-center rounded-full",
        step.status === "running" ? "bg-primary/20" : step.status === "error" ? "bg-danger/20" : "bg-success/20")}>
        {step.status === "running" ? <Loader2 className="size-2.5 animate-spin text-primary" />
          : <span className={cn("size-1.5 rounded-full", step.status === "error" ? "bg-danger" : "bg-success")} />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <span className="text-xs text-foreground/85">{step.label}</span>
          <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">{fmtMs(dur)}</span>
        </div>
        {step.detail && <p className={cn("text-[11px]", step.status === "error" ? "text-danger" : "text-muted-foreground")}>{step.detail}</p>}
      </div>
    </motion.li>
  );
}

function StepRow(props: { step: RunStep; last: boolean; now: number }) {
  return props.step.kind === "sub" ? <SubStepRow step={props.step} now={props.now} /> : <MainStepRow {...props} />;
}

function MainStepRow({ step, last, now }: { step: RunStep; last: boolean; now: number }) {
  const [open, setOpen] = useState(false);
  const dur = (step.endedAt ?? now) - step.startedAt;
  const expandable = step.kind === "tool" && !!step.args && Object.keys(step.args).length > 0;
  return (
    <motion.li layout initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} className="relative flex gap-3 pb-4">
      {!last && <span className="absolute left-[11px] top-7 h-[calc(100%-1.25rem)] w-px bg-border" />}
      <span className={cn("relative z-10 grid size-6 shrink-0 place-items-center rounded-full bg-card-solid ring-1 ring-border",
        step.status === "running" && "ring-primary/50")}>
        <StepIcon step={step} />
      </span>
      <div className="min-w-0 flex-1">
        <button type="button" disabled={!expandable} onClick={() => setOpen((o) => !o)}
          className="flex w-full items-start justify-between gap-2 text-left">
          <span className={cn("text-[13px] leading-5", step.status === "running" ? "font-medium" : "text-foreground/90")}>
            {step.label}
            {step.kind === "tool" && step.name && (
              <span className="ml-1.5 font-mono text-[10px] text-muted-foreground">{step.name}()</span>
            )}
          </span>
          <span className="flex shrink-0 items-center gap-1 text-[10px] tabular-nums text-muted-foreground">
            {step.kind !== "notice" && (step.status === "running" || dur > 0) && fmtMs(dur)}
            {expandable && <ChevronDown className={cn("size-3 transition", open && "rotate-180")} />}
          </span>
        </button>
        {step.detail && (
          <p className={cn("mt-0.5 text-xs", step.status === "error" ? "text-danger" : "text-muted-foreground")}>{step.detail}</p>
        )}
        <AnimatePresence>
          {open && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
              <ArgChips args={step.args} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.li>
  );
}

function RunCard({ run, now, voice }: { run: AgentRun; now: number; voice?: VoiceState }) {
  const elapsed = (run.endedAt ?? now) - run.startedAt;
  const tools = run.steps.filter((s) => s.kind === "tool").length;
  return (
    <div className="rounded-2xl border border-border bg-card-solid/60 p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="line-clamp-2 text-sm font-medium">“{run.prompt}”</p>
        <span className={cn("inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
          run.status === "running" ? "bg-primary/15 text-primary" : run.status === "error" ? "bg-danger/15 text-danger" : "bg-success/15 text-success")}>
          {run.status === "running" ? <Loader2 className="size-3 animate-spin" /> : run.status === "error" ? <XCircle className="size-3" /> : <CheckCircle2 className="size-3" />}
          {run.status === "running" ? `Working · ${fmtMs(elapsed)}` : run.status === "error" ? "Failed" : `Done in ${fmtMs(elapsed)}`}
        </span>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">
        {run.mode === "gemini" ? run.model || "Amaan AI" : run.mode === "offline" ? "Amaan · demo engine"
          : run.mode === "engine" ? `Live re-pricing · ${run.model || "rating engine"}` : "Starting…"}
        {tools > 0 && ` · ${tools} tool call${tools > 1 ? "s" : ""}`}
      </p>
      <ol className="mt-4">
        {run.steps.map((s, i) => <StepRow key={s.id} step={s} now={now} last={i === run.steps.length - 1 && voice !== "speaking"} />)}
        {voice === "speaking" && run.status === "done" && (
          <motion.li initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
            <span className="grid size-6 place-items-center rounded-full bg-accent/20"><Volume2 className="size-3.5 text-accent" /></span>
            <span className="text-[13px] text-muted-foreground">Speaking the reply aloud…</span>
          </motion.li>
        )}
      </ol>
    </div>
  );
}

export function ActivityPanel({
  runs, selectedId, onSelect, onClose, voice, className,
}: {
  runs: AgentRun[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onClose?: () => void;
  voice?: VoiceState;
  className?: string;
}) {
  const running = runs.some((r) => r.status === "running");
  const now = useNow(running);
  const current = runs.find((r) => r.id === selectedId) || runs[runs.length - 1];
  const earlier = runs.filter((r) => r !== current).slice().reverse();

  return (
    <aside className={cn("glass flex min-h-0 flex-col overflow-hidden rounded-2xl", className)} aria-label="What's happening">
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="relative grid size-7 place-items-center rounded-lg bg-primary/12 text-primary">
            <Sparkles className="size-4" />
            {running && <span className="absolute -right-0.5 -top-0.5 size-2 animate-ping rounded-full bg-primary" />}
          </span>
          <h2 className="text-sm font-semibold">What&apos;s happening</h2>
        </div>
        {onClose && (
          <button onClick={onClose} aria-label="Close panel" className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted">
            <PanelRightClose className="size-4" />
          </button>
        )}
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {!current ? (
          <div className="grid h-full place-items-center text-center">
            <div className="max-w-[240px]">
              <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-muted"><Brain className="size-5 text-muted-foreground" /></span>
              <p className="mt-3 text-sm font-medium">Nothing running yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Ask something and you&apos;ll see each step live here — how Amaan plans, which tools it calls, and what they returned.
              </p>
            </div>
          </div>
        ) : (
          <RunCard run={current} now={now} voice={current.status === "done" && current === runs[runs.length - 1] ? voice : undefined} />
        )}

        {earlier.length > 0 && (
          <div>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Earlier in this chat</p>
            <div className="space-y-1.5">
              {earlier.map((r) => {
                const tools = r.steps.filter((s) => s.kind === "tool");
                return (
                  <button key={r.id} onClick={() => onSelect(r.id)}
                    className="w-full rounded-xl border border-border px-3 py-2 text-left transition hover:border-primary/40 hover:bg-muted/40">
                    <p className="truncate text-xs font-medium">{r.prompt}</p>
                    <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
                      {r.status === "error" ? "Failed" : fmtMs((r.endedAt ?? r.startedAt) - r.startedAt)}
                      {tools.length ? ` · ${tools.map((t) => humanize(t.name || "")).join(", ")}` : " · no tools"}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-border px-4 py-2.5 text-[10px] text-muted-foreground">
        <Cpu className="size-3" /> LangGraph agent · 16 tools · steps stream live
      </div>
    </aside>
  );
}
