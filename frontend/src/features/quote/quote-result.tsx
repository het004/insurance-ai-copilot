"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  CalendarClock, Car, Check, Gauge, HeartHandshake, HeartPulse, House, Landmark, Loader2, PiggyBank, ShieldCheck,
  ShoppingCart, SlidersHorizontal, Sparkles, TrendingUp, UserRound, Wallet, X,
} from "lucide-react";
import { INSURER_SHORT } from "@/lib/brand";
import type { Adjustable, QuoteResult } from "@/types";
import { Badge, statusVariant } from "@/components/ui/badge";
import { cn, sar, sarShort } from "@/lib/utils";

export function RiskGauge({ score, band }: { score: number; band: string }) {
  const r = 34;
  const c = Math.PI * r;
  const color = band === "Low" ? "var(--success)" : band === "Medium" ? "var(--warning)" : "var(--danger)";
  return (
    <div className="relative flex w-28 flex-col items-center">
      <svg viewBox="0 0 80 46" className="w-28">
        <path d="M6 40 A34 34 0 0 1 74 40" fill="none" stroke="var(--muted)" strokeWidth="8" strokeLinecap="round" />
        <motion.path d="M6 40 A34 34 0 0 1 74 40" fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - score / 100) }}
          transition={{ duration: 1, ease: "easeOut" }} />
      </svg>
      <span className="-mt-6 text-xl font-semibold tabular-nums">{score}</span>
      <Badge variant={statusVariant(band)} className="mt-1">{band} risk</Badge>
    </div>
  );
}

export const LINE_ICON: Record<string, React.ElementType> = {
  health: HeartPulse, motor: Car, life: HeartHandshake, savings: PiggyBank, general: House, home: House,
};
export const LINE_LABEL: Record<string, string> = {
  health: "Health", motor: "Motor", life: "Life", savings: "Retirement & Savings", general: "General", home: "General",
};

const fmtAdj = (a: Adjustable, v: number | string | boolean) =>
  a.unit === "SAR" ? sar(Number(v)) : a.unit ? `${v} ${a.unit}` : String(v);

/** Sliders / selects / toggles that re-price the quote live (debounced) — like an insurer's quote page. */
export function QuoteAdjusters({ items, onChange, busy }: {
  items: Adjustable[]; onChange: (changes: Record<string, unknown>) => void; busy?: boolean;
}) {
  const [vals, setVals] = useState<Record<string, number | string | boolean>>(
    () => Object.fromEntries(items.map((a) => [a.key, a.value])));
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => setVals(Object.fromEntries(items.map((a) => [a.key, a.value]))), [items]);
  const commit = (key: string, v: number | string | boolean, delay = 0) => {
    setVals((s) => ({ ...s, [key]: v }));
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange({ [key]: v }), delay);
  };
  return (
    <div className="border-b border-border bg-muted/40 px-5 py-4">
      <p className="mb-3 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        <SlidersHorizontal className="size-3.5" /> Adjust your cover
        {busy && <span className="ml-auto flex items-center gap-1 normal-case tracking-normal text-primary"><Loader2 className="size-3 animate-spin" /> Recalculating…</span>}
      </p>
      <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
        {items.map((a) => {
          const v = vals[a.key];
          return (
            <div key={a.key} className="min-w-0">
              <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
                <span className="text-muted-foreground">{a.label}</span>
                {a.type === "range" && <span className="font-semibold tabular-nums text-navy">{fmtAdj(a, v as number)}</span>}
              </div>
              {a.type === "range" && (
                <>
                  <input type="range" min={a.min} max={a.max} step={a.step} value={Number(v)} disabled={busy}
                    onChange={(e) => commit(a.key, Number(e.target.value), 550)}
                    className="h-6 w-full accent-[var(--primary)]" aria-label={a.label} />
                  <div className="flex justify-between gap-2 text-[10px] text-muted-foreground">
                    <span>{fmtAdj(a, a.min ?? 0)}</span>{a.hint && <span className="truncate">{a.hint}</span>}<span>{fmtAdj(a, a.max ?? 0)}</span>
                  </div>
                </>
              )}
              {a.type === "select" && (
                <div className="flex flex-wrap gap-1.5">
                  {a.options?.map((o) => (
                    <button key={String(o.value)} type="button" disabled={busy} onClick={() => commit(a.key, o.value)}
                      className={cn("rounded-lg border px-2.5 py-1.5 text-xs transition",
                        String(v) === String(o.value) ? "border-primary bg-primary text-white" : "border-border bg-card-solid hover:border-primary/50")}>
                      {o.label}
                    </button>
                  ))}
                </div>
              )}
              {a.type === "toggle" && (
                <button type="button" disabled={busy} onClick={() => commit(a.key, !v)} className="flex items-center gap-2 text-xs">
                  <span className={cn("relative h-5 w-9 rounded-full transition", v ? "bg-primary" : "bg-muted-foreground/30")}>
                    <span className={cn("absolute top-0.5 size-4 rounded-full bg-white shadow transition-all", v ? "left-[18px]" : "left-0.5")} />
                  </span>
                  <span>{v ? "Included" : "Not included"}</span>
                  {a.hint && <span className="text-muted-foreground">· {a.hint}</span>}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Retirement Plan specifics: the two periods, instalment, fund, protection and beneficiary. */
export function RetirementDetails({ q }: { q: QuoteResult }) {
  const r = q.retirement!;
  const pj = q.projection!;
  const rows: [React.ElementType, string, string][] = [
    [CalendarClock, "Contribution period", r.contribution_period],
    [Wallet, "You pay", r.instalment],
    [Landmark, "Fund", `${r.fund} · ${r.fund_risk} risk`],
    [CalendarClock, "Retirement income", r.income_period],
    [ShieldCheck, "Takaful protection", `${sar(r.protection)}${r.ci_rider ? " + critical illness" : ""}`],
    [UserRound, "Beneficiary", r.beneficiary || "—"],
  ];
  return (
    <div className="space-y-3">
      {pj.monthly_income && (
        <div className="rounded-xl bg-primary/8 p-4">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Projected retirement income from age {pj.retirement_age}</p>
          <p className="mt-1 text-2xl font-bold tabular-nums text-navy">{sar(pj.monthly_income.mid)}<span className="text-sm font-medium text-muted-foreground"> / month</span></p>
          <p className="text-xs text-muted-foreground">for {pj.income_years} years · range {sar(pj.monthly_income.low)} – {sar(pj.monthly_income.high)} at {pj.rates?.low}%–{pj.rates?.high}% growth · not guaranteed</p>
        </div>
      )}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-xs">
        {rows.map(([Icon, k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="flex items-center gap-1 text-muted-foreground"><Icon className="size-3" />{k}</dt>
            <dd className="font-medium break-words">{v}</dd>
          </div>
        ))}
      </dl>
      {r.declarations && (
        <p className="text-[11px] text-muted-foreground">
          Declarations: {r.declarations.us_person ? "US person (FATCA)" : "Not a US person"} · {r.declarations.pep ? "PEP" : "Not a PEP"}
          {r.declarations.source_of_funds ? ` · Source of funds: ${r.declarations.source_of_funds}` : ""}
        </p>
      )}
    </div>
  );
}

/** Illustrative fund projection for Retirement & Savings quotes. */
export function ProjectionCard({ q }: { q: QuoteResult }) {
  const pj = q.projection!;
  const max = pj.high || 1;
  const rt = pj.rates ?? { low: 3, mid: 5, high: 7 };
  const bars: [string, number, string][] = [["Paid in", pj.total_contributions, "bg-muted-foreground/40"],
    [`At ${rt.low}%`, pj.low, "bg-accent/60"], [`At ${rt.mid}%`, pj.mid, "bg-primary"], [`At ${rt.high}%`, pj.high, "bg-navy"]];
  return (
    <div className="w-full min-w-[200px] md:w-56">
      <p className="mb-2 flex items-center gap-1 text-[11px] text-muted-foreground"><TrendingUp className="size-3" /> Fund {pj.retirement_age ? `at age ${pj.retirement_age}` : `after ${pj.years} years`}</p>
      <div className="space-y-1.5">
        {bars.map(([k, v, c]) => (
          <div key={k} className="text-[11px]">
            <div className="flex justify-between"><span className="text-muted-foreground">{k}</span><span className="font-semibold tabular-nums">{sarShort(v)}</span></div>
            <div className="h-1.5 rounded-full bg-muted"><motion.div className={cn("h-full rounded-full", c)} initial={{ width: 0 }} animate={{ width: `${(v / max) * 100}%` }} /></div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-muted-foreground">{pj.note}</p>
    </div>
  );
}

export function QuoteResultCard({
  quote, compact = false, onBuy, onAdjust, adjusting = false,
}: {
  quote: QuoteResult; compact?: boolean; onBuy?: (plan: string, coverage: string) => void;
  onAdjust?: (changes: Record<string, unknown>) => void; adjusting?: boolean;
}) {
  const p = quote.premium;
  const rows: [string, number][] = quote.breakdown?.length
    ? quote.breakdown.map((b) => [b.label, b.amount])
    : [["Own damage", p.own_damage], ["NCB discount", -p.ncb_discount], ["Third party", p.third_party],
       ["Personal accident", p.personal_accident], ["Add-ons", p.add_ons], ["VAT (15%)", p.gst]];
  const LineIcon = LINE_ICON[quote.line || "motor"] || Car;
  const subject = quote.subject ||
    `${quote.vehicle_label} · ${quote.vehicle_age === 0 ? "Brand new" : `${quote.vehicle_age} yrs old`} · ${quote.location}`;
  const vatFree = quote.line === "life" || quote.line === "savings";
  const savings = quote.line === "savings" && !!quote.projection;
  const retirement = !!quote.retirement;
  const instalment = retirement && !!p.frequency && p.frequency !== "monthly";
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card-solid shadow-card">
      <div className="brand-wave relative p-5 text-white">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="flex items-center gap-1.5 text-xs uppercase tracking-wider opacity-80">
              <LineIcon className="size-3.5" /> {INSURER_SHORT} {LINE_LABEL[quote.line || "motor"]} · {quote.quote_id}
            </p>
            <h4 className="mt-1 text-lg font-semibold text-white">{quote.plan}</h4>
            <p className="text-xs opacity-85">{subject}</p>
          </div>
          <div className="text-right">
            <motion.p key={p.total_premium} initial={{ opacity: 0.3, y: -4 }} animate={{ opacity: 1, y: 0 }}
              className={cn("text-2xl font-bold tabular-nums md:text-3xl", adjusting && "animate-pulse")}>
              {instalment ? sar(p.instalment) : savings ? sar(p.monthly ?? p.total_premium / 12) : sar(p.total_premium)}
            </motion.p>
            <p className="text-[11px] opacity-80">
              {instalment ? `per ${p.frequency === "quarterly" ? "quarter" : p.frequency === "semi_annual" ? "half-year" : "year"}`
                : savings ? "per month" : "per year"} {vatFree ? "· VAT-exempt" : "incl. 15% VAT"}
            </p>
          </div>
        </div>
      </div>

      {onAdjust && !!quote.adjustables?.length && (
        <QuoteAdjusters items={quote.adjustables} onChange={onAdjust} busy={adjusting} />
      )}

      <div className={cn("grid gap-5 p-5 md:grid-cols-[1fr_auto]", adjusting && "opacity-60 transition-opacity")}>
        <div className="space-y-4">
          {retirement ? <RetirementDetails q={quote} /> : <p className="text-sm text-muted-foreground">{quote.plan_summary}</p>}
          {quote.recommendation && !retirement && (
            <div className={cn("flex gap-2 rounded-xl p-3 text-xs",
              quote.recommendation.coverage === quote.coverage ? "bg-success/10 text-success" : "bg-primary/10 text-primary")}>
              <Sparkles className="mt-0.5 size-4 shrink-0" />
              <span>
                <b>{quote.recommendation.coverage === quote.coverage ? "Recommended for you. " : `We recommend ${quote.recommendation.plan}. `}</b>
                <span className="text-foreground/80">{quote.recommendation.reason}</span>
              </span>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <ul className="space-y-1.5 text-xs">
              {quote.coverage_details.includes.slice(0, compact ? 4 : 10).map((i) => (
                <li key={i} className="flex gap-2"><Check className="mt-0.5 size-3.5 shrink-0 text-success" />{i}</li>
              ))}
            </ul>
            {!compact && (
              <ul className="space-y-1.5 text-xs text-muted-foreground">
                {quote.coverage_details.excludes.map((i) => (
                  <li key={i} className="flex gap-2"><X className="mt-0.5 size-3.5 shrink-0 text-danger" />{i}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="flex flex-col items-center justify-center gap-1 md:border-l md:border-border md:pl-5">
          {savings ? <ProjectionCard q={quote} /> : <>
            <p className="mb-1 flex items-center gap-1 text-[11px] text-muted-foreground"><Gauge className="size-3" /> Risk score</p>
            <RiskGauge score={quote.risk.score} band={quote.risk.band} />
          </>}
          {quote.sum_insured_label
            ? <p className="mt-2 max-w-[160px] text-center text-[11px] text-muted-foreground">{quote.sum_insured_label}{quote.line === "motor" && quote.sum_insured ? ` ${sarShort(quote.sum_insured)}` : ""}</p>
            : quote.premium.idv > 0 && <p className="mt-2 text-[11px] text-muted-foreground">IDV {sarShort(quote.premium.idv)}</p>}
        </div>
      </div>

      {!compact && (
        <div className="grid gap-5 border-t border-border p-5 md:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-medium">Contribution breakdown</p>
            <dl className="space-y-1 text-xs">
              {rows.filter(([, v]) => v !== 0).map(([k, v]) => (
                <div key={k} className="flex justify-between"><dt className="text-muted-foreground">{k}</dt>
                  <dd className={cn("tabular-nums", v < 0 && "text-success")}>{v < 0 ? `− ${sar(-v)}` : sar(v)}</dd></div>
              ))}
              <div className="flex justify-between border-t border-border pt-1 font-semibold"><dt>Total</dt><dd>{sar(p.total_premium)}</dd></div>
            </dl>
            {quote.gst_note && <p className="mt-1.5 text-[10px] text-muted-foreground">{quote.gst_note}</p>}
          </div>
          <div>
            <p className="mb-2 text-xs font-medium">{savings ? "Plan details" : "Risk factors"}</p>
            <ul className="space-y-1 text-xs text-muted-foreground">
              {quote.risk.factors.map((f) => <li key={f}>• {f}</li>)}
            </ul>
          </div>
        </div>
      )}

      <div className="border-t border-border p-4">
        {onBuy && <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{retirement ? "Compare funds · projected fund at retirement" : "Choose a plan"}</p>}
        <div className="flex flex-wrap gap-2">
          {quote.alternatives.map((a) => {
            const Tag = onBuy ? "button" : "div";
            return (
              <Tag key={a.fund || a.coverage}
                {...(a.fund && onAdjust ? { type: "button" as const, onClick: () => onAdjust({ fund: a.fund }) }
                  : onBuy && !a.fund ? { type: "button" as const, onClick: () => onBuy(a.plan, a.coverage) } : {})}
                className={cn("min-w-[120px] flex-1 rounded-xl border px-3 py-2 text-left text-xs",
                  (a.fund ? a.fund === quote.params?.fund : a.coverage === quote.coverage) ? "border-primary/50 bg-primary/8" : "border-border",
                  onBuy && "transition hover:border-primary/60 hover:bg-primary/10")}>
                <p className="flex items-center gap-1 text-muted-foreground">
                  {a.plan} {a.recommended && <Sparkles className="size-3 text-primary" />}
                </p>
                <p className="font-semibold tabular-nums">{a.projected_value ? `≈ ${sarShort(a.projected_value)}${a.fund ? "" : " at 5%"}` : sar(a.total_premium)}</p>
                {a.fund ? (onAdjust && <p className="mt-0.5 text-[10px] font-medium text-primary">Switch fund →</p>)
                  : onBuy && <p className="mt-0.5 text-[10px] font-medium text-primary">Buy this →</p>}
              </Tag>
            );
          })}
        </div>
        {onBuy && (
          <button type="button" disabled={adjusting} onClick={() => onBuy(quote.plan, quote.coverage)}
            className="mt-3 flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand text-sm font-medium text-white shadow-lg shadow-primary/25">
            <ShoppingCart className="size-4" /> {adjusting ? "Recalculating…" : <>Buy {quote.plan} · {savings ? `${sar(quote.premium.monthly ?? 0)}/month` : sar(quote.premium.total_premium)}</>}
          </button>
        )}
      </div>
    </div>
  );
}
