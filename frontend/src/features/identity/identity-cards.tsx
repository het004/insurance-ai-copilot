"use client";

import { motion } from "framer-motion";
import {
  BadgeCheck, Car, CheckCircle2, FileSpreadsheet, Landmark, PencilLine, ShieldAlert, UserRoundCheck, UserRoundSearch,
} from "lucide-react";
import type { CustomerCard, Identity, IdentityResult, KycResult, RegisteredResult } from "@/types";
import { cn, fmtDate } from "@/lib/utils";

function CustomerSummary({ c, tone = "success" }: { c: CustomerCard; tone?: "success" | "primary" }) {
  return (
    <div className="flex items-center gap-3">
      <span className={cn("grid size-11 shrink-0 place-items-center rounded-2xl text-sm font-semibold text-white",
        tone === "success" ? "bg-success" : "bg-brand")}>
        {c.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{c.name}</p>
        <p className="truncate text-xs text-muted-foreground">{c.customer_id} · {c.phone_masked} · {c.city}</p>
      </div>
      <div className="text-right text-[11px] text-muted-foreground">
        <p><b className="text-foreground">{c.active_policies}</b> policies</p>
        <p><b className="text-foreground">{c.open_claims}</b> open claims</p>
      </div>
    </div>
  );
}

export function IdentityCardView({ d, onPrompt }: { d: IdentityResult; onPrompt?: (p: string) => void }) {
  if (!d.found || !d.customer) {
    return (
      <div className="rounded-2xl border border-warning/30 bg-warning/8 p-4">
        <p className="flex items-center gap-2 text-sm font-medium"><UserRoundSearch className="size-4 text-warning" /> No registered customer found</p>
        <p className="mt-1 text-xs text-muted-foreground">We searched Customer 360 for “{d.identifier}”.</p>
        {onPrompt && (
          <button onClick={() => onPrompt("I'm a new customer")} className="mt-3 h-10 rounded-xl bg-brand px-4 text-sm font-medium text-white">
            Register as a new customer
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-success/30 bg-success/8 p-4">
      <p className="mb-3 flex items-center gap-2 text-xs font-medium text-success">
        <UserRoundCheck className="size-4" /> Verified via {d.customer.verified_via} · Customer 360
      </p>
      <CustomerSummary c={d.customer} />
    </div>
  );
}

export function KycCardView({ d, onPrompt }: { d: KycResult; onPrompt?: (p: string) => void }) {
  if (d.already_registered && d.customer) {
    return (
      <div className="rounded-2xl border border-success/30 bg-success/8 p-4">
        <p className="mb-3 flex items-center gap-2 text-xs font-medium text-success"><BadgeCheck className="size-4" /> Already registered — linked to existing profile</p>
        <CustomerSummary c={d.customer} />
      </div>
    );
  }
  const k = d.draft;
  if (!k) return null;
  const rows: [string, string][] = [
    ["Name", k.name], ["Date of birth", fmtDate(k.date_of_birth)], ["Nationality", k.nationality || "—"],
    ["National Address", k.address], ["Mobile", k.phone], ["Email", k.email || "— (add if you like)"],
    [k.id_type, `${k.id_reference}${k.id_expiry ? ` · valid till ${fmtDate(k.id_expiry)}` : ""}`],
  ];
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card-solid/70">
      <div className="flex items-center justify-between gap-2 border-b border-border bg-primary/8 px-4 py-3">
        <p className="flex items-center gap-2 text-sm font-semibold"><Landmark className="size-4 text-primary" /> Verified with Nafath · details from Yakeen</p>
        <span className="rounded-full bg-warning/20 px-2 py-0.5 text-[10px] font-medium text-warning">Simulated sources</span>
      </div>
      <dl className="grid gap-x-4 gap-y-2 p-4 text-sm sm:grid-cols-[110px_1fr]">
        {rows.map(([label, v]) => (
          <div key={label} className="contents">
            <dt className="text-xs text-muted-foreground sm:pt-0.5">{label}</dt>
            <dd className={cn("-mt-1 sm:mt-0", k.customer_corrections?.includes(label.toLowerCase()) && "text-primary")}>{v}</dd>
          </div>
        ))}
      </dl>
      {k.vehicle && (
        <div className="mx-4 mb-4 flex items-center gap-3 rounded-xl bg-muted/60 p-3 text-xs">
          <Car className="size-5 text-primary" />
          <div>
            <p className="font-medium">{k.vehicle.make_model} {k.vehicle.model_year ?? ""} · {k.vehicle.registration_number}</p>
            <p className="text-muted-foreground">{k.vehicle.colour ?? ""}{k.vehicle.registration_expiry ? ` · Istimara valid till ${fmtDate(k.vehicle.registration_expiry)}` : ""} · via Elm</p>
          </div>
        </div>
      )}
      <div className="border-t border-border px-4 py-3">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Sources checked</p>
        <ul className="grid gap-1 sm:grid-cols-2">
          {k.lookups.map((l) => (
            <li key={l.key} className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
              <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-success" />
              <span><span className="text-foreground/85">{l.source.replace(" — simulated", "")}</span> · {l.detail}</span>
            </li>
          ))}
        </ul>
      </div>
      {onPrompt && (
        <div className="flex flex-wrap gap-2 border-t border-border p-3">
          <button onClick={() => onPrompt("Yes, these details are correct")} className="h-11 flex-1 rounded-xl bg-brand px-4 text-sm font-medium text-white">
            Yes, register me
          </button>
          <button onClick={() => onPrompt("Some details need correcting")}
            className="flex h-11 items-center gap-1.5 rounded-xl border border-border px-4 text-sm">
            <PencilLine className="size-4" /> Something&apos;s wrong
          </button>
        </div>
      )}
    </div>
  );
}

export function RegisteredCardView({ d }: { d: RegisteredResult }) {
  if (!d.registered || !d.customer) {
    return d.draft ? <KycCardView d={{ draft: d.draft }} /> : null;
  }
  return (
    <motion.div initial={{ scale: 0.97 }} animate={{ scale: 1 }} className="overflow-hidden rounded-2xl border border-success/30 bg-success/8">
      <div className="p-4">
        <p className="mb-3 flex items-center gap-2 text-xs font-medium text-success"><BadgeCheck className="size-4" /> Registered · welcome aboard</p>
        <CustomerSummary c={d.customer} tone="primary" />
      </div>
      <div className={cn("flex items-center gap-2 border-t px-4 py-2.5 text-xs",
        d.excel?.synced ? "border-success/20 text-success" : "border-warning/30 text-warning")}>
        {d.excel?.synced ? <FileSpreadsheet className="size-4" /> : <ShieldAlert className="size-4" />}
        {d.excel?.synced ? "Added to Customer 360 (art_customer_360.xlsx)" : d.excel?.warning || "Customer 360 sync pending"}
      </div>
    </motion.div>
  );
}

/** Small chip in the chat header showing who the Copilot is talking to. */
export function IdentityChip({ identity, onClick }: { identity?: Identity | null; onClick?: () => void }) {
  const status = identity?.status ?? "guest";
  const label = status === "verified" ? identity?.customer_name?.split(" ")[0] ?? "Verified"
    : status === "kyc_pending" ? "Confirming KYC" : "Guest";
  return (
    <button type="button" onClick={onClick} title={status === "verified" ? `Verified via ${identity?.verified_via}` : "Not identified yet"}
      className={cn("inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-medium",
        status === "verified" ? "bg-success/15 text-success" : status === "kyc_pending" ? "bg-warning/20 text-warning" : "bg-muted text-muted-foreground")}>
      {status === "verified" ? <UserRoundCheck className="size-3.5" /> : <UserRoundSearch className="size-3.5" />}
      {label}{status === "verified" && identity?.customer_id ? <span className="hidden opacity-70 sm:inline">· {identity.customer_id}</span> : null}
    </button>
  );
}
