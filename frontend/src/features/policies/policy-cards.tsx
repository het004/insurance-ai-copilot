"use client";

import { Bike, Car, HeartHandshake, HeartPulse, House, PiggyBank, RefreshCcw, Truck } from "lucide-react";
import type { Policy, RenewalResult } from "@/types";
import { Badge, statusVariant } from "@/components/ui/badge";
import { cn, fmtDate, sar, sarShort } from "@/lib/utils";

export function policyIcon(type: string) {
  if (type.includes("Motorcycle")) return Bike;
  if (type === "Life") return HeartHandshake;
  if (type.startsWith("Retirement")) return PiggyBank;
  if (type.includes("Commercial")) return Truck;
  if (type.startsWith("Motor")) return Car;
  if (type === "Health") return HeartPulse;
  return House;
}

export function PolicyRow({ p, action }: { p: Policy; action?: React.ReactNode }) {
  const Icon = policyIcon(p.policy_type);
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card-solid/60 p-3">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary"><Icon className="size-5" /></span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium">{p.policy_type}</p>
          <Badge variant={statusVariant(p.status)}>{p.status}{p.renewal_due ? ` · ${p.days_to_expiry}d` : ""}</Badge>
          {p.details?.purchased_via === "AI Copilot chat" && <Badge variant="default">Bought via Copilot</Badge>}
        </div>
        <p className="truncate text-xs text-muted-foreground">{p.insured_asset}</p>
        <p className="text-[11px] text-muted-foreground">{p.policy_id} · {p.product_name} · till {fmtDate(p.end_date)}</p>
      </div>
      <div className="text-right">
        <p className="text-sm font-semibold tabular-nums">{sar(p.premium)}</p>
        <p className="text-[11px] text-muted-foreground">Cover {sarShort(p.sum_insured)}</p>
        {action}
      </div>
    </div>
  );
}

export function PolicyList({ policies }: { policies: Policy[] }) {
  const visible = policies.filter((p) => p.status !== "Renewed");
  return <div className="space-y-2">{visible.map((p) => <PolicyRow key={p.policy_id} p={p} />)}</div>;
}

export function RenewalCard({ r, actions }: { r: RenewalResult; actions?: React.ReactNode }) {
  const up = r.renewal_premium > r.current_premium;
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card-solid/70">
      <div className="flex items-center justify-between gap-3 p-4">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-accent/20 text-accent"><RefreshCcw className="size-5" /></span>
          <div>
            <p className="text-sm font-semibold">{r.status === "renewed" ? "Policy renewed" : "Renewal quotation"}</p>
            <p className="text-xs text-muted-foreground">{r.policy.policy_type} · {r.policy.insured_asset}</p>
          </div>
        </div>
        <Badge variant={r.status === "renewed" ? "success" : "warning"}>
          {r.status === "renewed" ? "Renewed" : `${r.policy.days_to_expiry} days left`}
        </Badge>
      </div>
      <div className="grid grid-cols-3 gap-px bg-border text-center">
        {[
          ["Current", sar(r.current_premium)],
          ["Renewal", sar(r.renewal_premium)],
          [r.policy.policy_type.startsWith("Motor") ? "No Claim Discount" : "Change", r.policy.policy_type.startsWith("Motor") ? `${r.ncb_current}% → ${r.ncb_renewal}%` : `${r.change_percent > 0 ? "+" : ""}${r.change_percent}%`],
        ].map(([k, v]) => (
          <div key={k} className="bg-card-solid p-3">
            <p className="text-[11px] text-muted-foreground">{k}</p>
            <p className={cn("text-sm font-semibold tabular-nums", k === "Renewal" && (up ? "text-warning" : "text-success"))}>{v}</p>
          </div>
        ))}
      </div>
      <div className="space-y-1.5 p-4 text-xs">
        <p>{r.recommendation}</p>
        <p className="text-muted-foreground">{r.add_on_tip}</p>
        {r.early_renewal_discount_percent > 0 && <p className="text-success">Includes {r.early_renewal_discount_percent}% early-renewal discount.</p>}
        <p className="text-muted-foreground">New period: {fmtDate(r.new_start_date)} – {fmtDate(r.new_end_date)}</p>
        {r.new_policy_id && (
          <p className="rounded-lg bg-success/10 p-2 text-success">
            New policy <b>{r.new_policy_id}</b> · Payment ref {r.payment?.reference}
          </p>
        )}
      </div>
      {actions && <div className="flex gap-2 border-t border-border p-3">{actions}</div>}
    </div>
  );
}
