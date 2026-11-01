"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle, Building2, Car, Check, CreditCard, FileSpreadsheet, FileText, PartyPopper, ShieldAlert, ShieldCheck,
  ShoppingCart, Smartphone,
} from "lucide-react";
import type { PurchaseResult, QuoteResult } from "@/types";
import { INSURER_SHORT } from "@/lib/brand";
import { apiHref } from "@/services/api";
import { RetirementDetails } from "@/features/quote/quote-result";
import { LINE_ICON } from "@/features/quote/quote-result";
import { cn, fmtDate, fmtDateTime, sar, sarShort } from "@/lib/utils";

const METHOD_ICON: Record<string, React.ElementType> = {
  mada: CreditCard, "Apple Pay": Smartphone, "STC Pay": Smartphone, "Credit card": CreditCard, SADAD: Building2,
};

const ASSET_LABEL: Record<string, string> = {
  motor: "Vehicle", health: "Covered person", general: "Property", home: "Property", life: "Covered person", savings: "Plan",
};

function Review({ d, onPrompt }: { d: PurchaseResult; onPrompt?: (p: string) => void }) {
  const blocked = !d.underwriting.accepted;
  const AssetIcon = LINE_ICON[d.line] || Car;
  const vatFree = d.line === "life" || d.line === "savings";
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card-solid/70">
      <div className="flex items-start justify-between gap-3 border-b border-border bg-primary/8 px-4 py-3">
        <div>
          <p className="flex items-center gap-2 text-sm font-semibold"><ShoppingCart className="size-4 text-primary" /> Checkout · {INSURER_SHORT} {d.plan}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">Quote {d.quote_id} · for {d.customer.name}</p>
        </div>
        <div className="text-right">
          <p className="text-xl font-bold tabular-nums">{sar(d.total_premium)}</p>
          <p className="text-[10px] text-muted-foreground">per year {vatFree ? "· VAT-exempt" : "incl. 15% VAT"}</p>
        </div>
      </div>

      {d.retirement && d.projection && (
        <div className="border-b border-border p-4">
          <RetirementDetails q={{ retirement: d.retirement, projection: d.projection } as unknown as QuoteResult} />
        </div>
      )}
      <div className="grid gap-4 p-4 sm:grid-cols-2">
        <div className="space-y-2 text-sm">
          <p className="flex items-start gap-2"><AssetIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />{d.insured_asset}</p>
          <p className="text-xs text-muted-foreground">Cover: {fmtDate(d.start_date)} – {fmtDate(d.end_date)} · {d.location}</p>
          <p className="text-xs text-muted-foreground">
            {d.line === "motor" ? (d.idv > 0 ? `Insured Declared Value ${sarShort(d.idv)}` : d.sum_insured_label) : d.sum_insured_label}
          </p>
          <ul className="space-y-1 pt-1">
            {d.includes.slice(0, 4).map((i) => (
              <li key={i} className="flex gap-1.5 text-xs"><Check className="mt-0.5 size-3.5 shrink-0 text-success" />{i}</li>
            ))}
          </ul>
        </div>
        <dl className="space-y-1 text-xs">
          {d.breakdown.map((b) => (
            <div key={b.label} className="flex justify-between gap-2"><dt className="text-muted-foreground">{b.label}</dt>
              <dd className={cn("tabular-nums", b.amount < 0 && "text-success")}>{b.amount < 0 ? `− ${sar(-b.amount)}` : sar(b.amount)}</dd></div>
          ))}
          <div className="flex justify-between border-t border-border pt-1 font-semibold"><dt>Total</dt><dd>{sar(d.total_premium)}</dd></div>
          {d.gst_note && <p className="pt-1 text-[10px] text-muted-foreground">{d.gst_note}</p>}
        </dl>
      </div>

      {d.notes?.length > 0 && !blocked && (
        <div className="mx-4 mb-3 rounded-xl bg-primary/8 p-3 text-xs text-foreground/80">{d.notes.join(" ")}</div>
      )}
      {blocked && (
        <div className="mx-4 mb-4 flex gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3 text-xs text-warning">
          <ShieldAlert className="size-4 shrink-0" />
          <span>{d.underwriting.issues.join(" ")}</span>
        </div>
      )}

      {/* switch plan */}
      <div className="border-t border-border px-4 py-3">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Plan</p>
        <div className="flex flex-wrap gap-2">
          {d.alternatives.map((a) => {
            const current = a.coverage === d.coverage;
            return (
              <button key={a.coverage} type="button" disabled={!onPrompt || current}
                onClick={() => onPrompt?.(`Switch to the ${a.plan} plan`)}
                className={cn("min-w-[110px] flex-1 rounded-xl border px-3 py-2 text-left text-xs transition",
                  current ? "border-primary/60 bg-primary/10" : "border-border hover:border-primary/40 disabled:opacity-60")}>
                <p className="text-muted-foreground">{a.plan}{a.recommended ? " ✦" : ""}</p>
                <p className="font-semibold tabular-nums">{sar(a.total_premium)}</p>
                {current && <p className="text-[10px] font-medium text-primary">Selected</p>}
              </button>
            );
          })}
        </div>
      </div>

      {/* pay */}
      {!blocked && (
        <div className="border-t border-border p-4">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Pay with</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {d.payment_methods.map((m) => {
              const Icon = METHOD_ICON[m] || CreditCard;
              return (
                <button key={m} type="button" disabled={!onPrompt}
                  onClick={() => onPrompt?.(`Pay ${sar(d.total_premium)} by ${m}`)}
                  className="flex h-12 items-center justify-center gap-1.5 rounded-xl bg-brand px-2 text-xs font-medium text-white shadow-md shadow-primary/20 transition hover:brightness-110 disabled:opacity-50 sm:text-sm">
                  <Icon className="size-4" /> {m}
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-center text-[10px] text-muted-foreground">Demo checkout — payments are simulated, no money moves.</p>
        </div>
      )}
    </div>
  );
}

function Issued({ d }: { d: PurchaseResult }) {
  const pay = d.payment!;
  return (
    <motion.div initial={{ scale: 0.97, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
      className="overflow-hidden rounded-2xl border border-success/30 bg-card-solid/70">
      <div className="brand-wave relative p-5 text-white">
        <PartyPopper className="absolute right-4 top-4 size-6 opacity-80" />
        <p className="text-xs uppercase tracking-wider opacity-85">Mabrook! · Takaful certificate active today</p>
        <p className="mt-1 text-2xl font-bold tracking-tight">{d.policy_id}</p>
        <p className="text-sm opacity-90">{INSURER_SHORT} {d.line_label} · {d.plan}</p>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 p-4 text-xs sm:grid-cols-3">
        {[
          ["Participant", d.customer.name],
          [ASSET_LABEL[d.line] || "Insured", d.insured_asset],
          ["Period", `${fmtDate(d.start_date)} – ${fmtDate(d.end_date)}`],
          ["Contribution paid", sar(pay.amount)],
          ["Payment", `${pay.method} · ${pay.status}`],
          ["Bank reference", pay.bank_reference],
        ].map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="truncate font-medium" title={v}>{v}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap items-center gap-2 border-t border-border p-3">
        {d.document_url && (
          <a href={apiHref(d.document_url)} target="_blank" rel="noreferrer"
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-brand px-4 text-sm font-medium text-white">
            <FileText className="size-4" /> View policy schedule
          </a>
        )}
        <span className={cn("inline-flex items-center gap-1.5 text-xs", d.excel?.synced ? "text-success" : "text-warning")}>
          {d.excel?.synced ? <FileSpreadsheet className="size-4" /> : <AlertTriangle className="size-4" />}
          {d.excel?.synced ? "Added to Customer 360" : d.excel?.warning || "Customer 360 sync pending"}
        </span>
      </div>
      <p className="border-t border-border px-4 py-2 text-[10px] text-muted-foreground">
        <ShieldCheck className="mr-1 inline size-3" /> {pay.payment_id} · {pay.gateway} · {fmtDateTime(pay.paid_at)}
      </p>
    </motion.div>
  );
}

export function PurchaseCardView({ d, onPrompt }: { d: PurchaseResult; onPrompt?: (p: string) => void }) {
  return d.status === "issued" ? <Issued d={d} /> : <Review d={d} onPrompt={onPrompt} />;
}
