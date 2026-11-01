import type { AgentRun, RunEvent, RunStep } from "@/types";

export function newRun(prompt: string): AgentRun {
  return { id: `local-${Date.now()}`, prompt, status: "running", steps: [], startedAt: Date.now() };
}

function upsert(steps: RunStep[], id: string, patch: Partial<RunStep>, create: () => RunStep): RunStep[] {
  const i = steps.findIndex((s) => s.id === id);
  if (i < 0) return [...steps, { ...create(), ...patch }];
  const copy = steps.slice();
  copy[i] = { ...copy[i], ...patch };
  return copy;
}

const closeRunning = (steps: RunStep[], ts: number) =>
  steps.map((s) => (s.status === "running" ? { ...s, status: "done" as const, endedAt: ts } : s));

/** Pure reducer: fold one streamed event into the run shown in the progress panel. */
export function applyEvent(run: AgentRun, ev: RunEvent): AgentRun {
  switch (ev.type) {
    case "run_started":
      return { ...run, id: ev.run_id, mode: ev.mode, model: ev.model };
    case "step":
      return {
        ...run,
        steps: upsert(run.steps, ev.id,
          { status: ev.status, endedAt: ev.status === "done" ? ev.ts : undefined, ...(ev.detail ? { detail: ev.detail } : {}) },
          () => ({ id: ev.id, kind: "think", label: ev.label, status: ev.status, startedAt: ev.ts })),
      };
    case "tool_call":
      return {
        ...run,
        steps: [...closeRunning(run.steps, ev.ts),
          { id: ev.id, kind: "tool", name: ev.name, label: ev.label, args: ev.args, status: "running", startedAt: ev.ts }],
      };
    case "tool_result":
      return {
        ...run,
        steps: upsert(run.steps, ev.id, { status: ev.ok ? "done" : "error", detail: ev.summary, endedAt: ev.ts },
          () => ({ id: ev.id, kind: "tool", name: ev.name, label: ev.name, status: "done", startedAt: ev.ts })),
      };
    case "tool_progress":
      return {
        ...run,
        steps: upsert(run.steps, ev.id,
          { status: ev.status, endedAt: ev.status === "running" ? undefined : ev.ts, ...(ev.detail ? { detail: ev.detail } : {}) },
          () => ({ id: ev.id, kind: "sub", parentId: ev.tool_call_id, label: ev.label, status: ev.status, startedAt: ev.ts })),
      };
    case "notice":
      return {
        ...run,
        steps: [...closeRunning(run.steps, ev.ts),
          { id: `notice-${ev.ts}`, kind: "notice", label: ev.message, detail: ev.detail, status: "error", startedAt: ev.ts, endedAt: ev.ts }],
      };
    case "final":
      return { ...run, status: "done", mode: ev.mode, endedAt: ev.ts, steps: closeRunning(run.steps, ev.ts) };
    case "error":
      return { ...run, status: "error", endedAt: Date.now(), steps: closeRunning(run.steps, Date.now()) };
  }
}

export const fmtMs = (ms: number) => (ms < 1000 ? `${Math.max(ms, 1)}ms` : `${(ms / 1000).toFixed(1)}s`);
