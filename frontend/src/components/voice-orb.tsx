"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Mic, Square, Volume2 } from "lucide-react";
import type { VoiceState } from "@/types";
import { cn } from "@/lib/utils";

const LABEL: Record<VoiceState, string> = {
  idle: "Tap to speak",
  listening: "Listening…",
  processing: "Thinking…",
  speaking: "Speaking…",
};

/** Large animated microphone button that visualises Listening / Processing / Speaking. */
export function VoiceOrb({
  state, onClick, size = "md", disabled,
}: { state: VoiceState; onClick: () => void; size?: "md" | "lg"; disabled?: boolean }) {
  const dim = size === "lg" ? "size-24" : "size-14";
  const icon = size === "lg" ? "size-9" : "size-6";
  const Icon = state === "listening" ? Square : state === "processing" ? Loader2 : state === "speaking" ? Volume2 : Mic;
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      aria-label={state === "listening" ? "Stop listening" : state === "speaking" ? "Stop speaking" : "Start voice input"}
      className={cn("relative grid shrink-0 place-items-center rounded-full text-white transition-transform active:scale-95 disabled:opacity-50", dim)}>
      <AnimatePresence>
        {(state === "listening" || state === "speaking") &&
          [0, 1, 2].map((i) => (
            <motion.span key={`${state}-${i}`} className={cn("absolute inset-0 rounded-full",
              state === "listening" ? "bg-danger/40" : "bg-accent/40")}
              initial={{ scale: 1, opacity: 0.6 }} animate={{ scale: 1.9, opacity: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.6, ease: "easeOut" }} />
          ))}
      </AnimatePresence>
      <motion.span
        className={cn("absolute inset-0 rounded-full shadow-xl",
          state === "listening" ? "bg-danger shadow-danger/40" : state === "speaking"
            ? "bg-gradient-to-br from-accent to-primary shadow-accent/40" : "bg-brand shadow-primary/40")}
        animate={state === "processing" ? { rotate: 360 } : { rotate: 0 }}
        transition={state === "processing" ? { duration: 2.4, repeat: Infinity, ease: "linear" } : {}} />
      <Icon className={cn("relative", icon, state === "processing" && "animate-spin", state === "listening" && "fill-white")} />
    </button>
  );
}

export function VoiceStatus({ state }: { state: VoiceState }) {
  const color = { idle: "bg-muted-foreground/50", listening: "bg-danger", processing: "bg-warning", speaking: "bg-accent" }[state];
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-muted/70 px-3 py-1 text-xs text-muted-foreground">
      <span className="relative flex size-2">
        {state !== "idle" && <span className={cn("absolute inline-flex size-full animate-ping rounded-full opacity-75", color)} />}
        <span className={cn("relative inline-flex size-2 rounded-full", color)} />
      </span>
      {state === "idle" ? "Ready" : LABEL[state]}
    </span>
  );
}

/** Animated waveform bars shown under the live transcript. */
export function Waveform({ active, className }: { active: boolean; className?: string }) {
  return (
    <div className={cn("flex h-6 items-center gap-[3px]", className)} aria-hidden>
      {Array.from({ length: 18 }).map((_, i) => (
        <motion.span key={i} className="w-[3px] rounded-full bg-current"
          animate={active ? { height: [4, 8 + ((i * 7) % 16), 4] } : { height: 4 }}
          transition={{ duration: 0.9, repeat: active ? Infinity : 0, delay: (i % 6) * 0.08 }} />
      ))}
    </div>
  );
}

export { LABEL as VOICE_LABEL };
