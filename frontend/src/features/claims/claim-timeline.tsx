"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Circle, ClipboardCheck, FileSearch, FileText, Flag, ShieldCheck } from "lucide-react";
import type { Claim } from "@/types";
import { Badge, statusVariant } from "@/components/ui/badge";
import { cn, fmtDate, fmtDateTime, sar } from "@/lib/utils";

const ICONS: Record<string, React.ElementType> = {
  Reported: Flag, "Under Review": FileSearch, Assessment: ClipboardCheck, Approved: ShieldCheck, Closed: CheckCircle2,
};

export function ClaimTimeline({ claim, orientation = "auto" }: { claim: Claim; orientation?: "auto" | "vertical" }) {
  const currentIdx = claim.timeline.findIndex((s) => s.status === claim.status);
  return (
    <ol className={cn("relative grid gap-0", orientation === "auto" ? "sm:grid-cols-5" : "")}>
      {claim.timeline.map((step, i) => {
        const Icon = ICONS[step.status] || Circle;
        const current = i === currentIdx;
        return (
          <motion.li key={step.status} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
            className={cn("relative flex gap-3 pb-4", orientation === "auto" && "sm:flex-col sm:items-center sm:pb-0 sm:text-center")}>
            {i < claim.timeline.length - 1 && (
              <span className={cn("absolute left-[15px] top-8 h-[calc(100%-2rem)] w-0.5",
                orientation === "auto" && "sm:left-[calc(50%+18px)] sm:top-[15px] sm:h-0.5 sm:w-[calc(100%-36px)]",
                step.completed && claim.timeline[i + 1].completed ? "bg-success" : "bg-border")} />
            )}
            <span className={cn("relative z-10 grid size-8 shrink-0 place-items-center rounded-full border-2",
              step.completed ? "border-success bg-success text-white" : "border-border bg-card-solid text-muted-foreground",
              current && claim.status !== "Closed" && "ring-4 ring-success/25")}>
              <Icon className="size-4" />
            </span>
            <div className={cn("min-w-0", orientation === "auto" && "sm:mt-2")}>
              <p className={cn("text-xs font-medium", !step.completed && "text-muted-foreground")}>{step.status}</p>
              {step.at && <p className="text-[10px] text-muted-foreground">{fmtDateTime(step.at)}</p>}
              {step.note && <p className={cn("mt-0.5 text-[11px] text-muted-foreground", orientation === "auto" && "sm:hidden")}>{step.note}</p>}
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}

export function ClaimSummaryCard({ claim, actions }: { claim: Claim; actions?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card-solid/70">
      <div className="flex flex-wrap items-start justify-between gap-3 p-4">
        <div>
          <p className="flex items-center gap-2 text-xs text-muted-foreground"><FileText className="size-3.5" /> Claim ID</p>
          <p className="text-lg font-semibold tracking-tight">{claim.claim_id}</p>
          <p className="text-xs text-muted-foreground">{claim.incident_type} · {fmtDate(claim.incident_date)} · {claim.location}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant={statusVariant(claim.status)}>{claim.status}</Badge>
          <span className="text-[11px] text-muted-foreground">{claim.progress}% complete</span>
        </div>
      </div>
      <div className="mx-4 h-1.5 overflow-hidden rounded-full bg-muted">
        <motion.div className="h-full rounded-full bg-success" initial={{ width: 0 }} animate={{ width: `${claim.progress}%` }} />
      </div>
      <div className="p-4"><ClaimTimeline claim={claim} /></div>
      <div className="grid gap-3 border-t border-border p-4 text-xs sm:grid-cols-2">
        <div>
          <p className="mb-1 font-medium">What happened</p>
          <p className="text-muted-foreground">{claim.description}</p>
          <p className="mt-2 text-muted-foreground">
            Policy {claim.policy_id}{claim.estimated_amount ? ` · Est. ${sar(claim.estimated_amount)}` : ""}
          </p>
        </div>
        {claim.next_steps.length > 0 && (
          <div>
            <p className="mb-1 font-medium">Next steps</p>
            <ol className="list-decimal space-y-0.5 pl-4 text-muted-foreground">
              {claim.next_steps.map((s) => <li key={s}>{s}</li>)}
            </ol>
          </div>
        )}
      </div>
      {actions && <div className="flex flex-wrap gap-2 border-t border-border p-3">{actions}</div>}
    </div>
  );
}
