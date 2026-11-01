"use client";

import { BookOpen, Car, UserRound } from "lucide-react";
import type { ChatCard, Citation } from "@/types";
import { QuoteResultCard } from "@/features/quote/quote-result";
import { ClaimSummaryCard } from "@/features/claims/claim-timeline";
import { PolicyList, PolicyRow, RenewalCard } from "@/features/policies/policy-cards";
import { PurchaseCardView } from "@/features/purchase/purchase-card";
import { IdentityCardView, KycCardView, RegisteredCardView } from "@/features/identity/identity-cards";
import { sar } from "@/lib/utils";
import { cn } from "@/lib/utils";

export function CardRenderer({ card, onPrompt, onAdjust, adjusting }: {
  card: ChatCard; onPrompt?: (p: string) => void;
  onAdjust?: (quoteId: string, changes: Record<string, unknown>) => void; adjusting?: string | null;
}) {
  switch (card.type) {
    case "identity":
      return <IdentityCardView d={card.data} onPrompt={onPrompt} />;
    case "kyc":
      return <KycCardView d={card.data} onPrompt={onPrompt} />;
    case "registered":
      return <RegisteredCardView d={card.data} />;
    case "quote":
      return <QuoteResultCard quote={card.data} compact
        onAdjust={onAdjust ? (ch) => onAdjust(card.data.quote_id, ch) : undefined}
        adjusting={adjusting === card.data.quote_id}
        onBuy={onPrompt ? (plan) => onPrompt(card.data.coverage === "retirement_plan"
          ? `I want to buy this Retirement Plan (quote ${card.data.quote_id})`
          : `I want to buy the ${plan} plan (quote ${card.data.quote_id})`) : undefined} />;
    case "purchase":
      return <PurchaseCardView d={card.data} onPrompt={onPrompt} />;
    case "vehicle": {
      const v = card.data.vehicle;
      return (
        <div className="flex items-center gap-3 rounded-2xl border border-border bg-card-solid p-4 shadow-card">
          <span className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary"><Car className="size-5" /></span>
          <div className="text-sm">
            <p className="font-semibold text-navy">{v.make_model} {v.model_year ?? ""}</p>
            <p className="text-xs text-muted-foreground">{v.registration_number}{v.colour ? ` · ${v.colour}` : ""} · Istimara via Elm (simulated)</p>
          </div>
        </div>
      );
    }
    case "policies":
      return Array.isArray(card.data) ? <PolicyList policies={card.data} /> : <PolicyRow p={card.data} />;
    case "claim":
      if (Array.isArray(card.data)) {
        return (
          <div className="space-y-2">
            {card.data.slice(0, 3).map((c) => (
              <button key={c.claim_id} onClick={() => onPrompt?.(`Track claim ${c.claim_id}`)}
                className="flex w-full items-center justify-between rounded-xl border border-border bg-card-solid/60 p-3 text-left text-xs hover:bg-muted">
                <span><b className="text-sm">{c.claim_id}</b><br /><span className="text-muted-foreground">{c.incident_type}</span></span>
                <span className="text-muted-foreground">{c.status}</span>
              </button>
            ))}
          </div>
        );
      }
      return <ClaimSummaryCard claim={card.data} />;
    case "renewal":
      return (
        <RenewalCard r={card.data} actions={card.data.status === "quote" && onPrompt ? (
          <>
            <button onClick={() => onPrompt("Yes, please renew it")} className="h-10 flex-1 rounded-xl bg-brand text-sm font-medium text-white">Confirm renewal</button>
            <button onClick={() => onPrompt("Not now")} className="h-10 rounded-xl border border-border px-4 text-sm">Not now</button>
          </>
        ) : undefined} />
      );
    case "profile": {
      const d = card.data;
      return (
        <div className="rounded-2xl border border-border bg-card-solid/70 p-4">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-accent/25"><UserRound className="size-5" /></span>
            <div className="flex-1">
              <p className="text-sm font-semibold">{d.customer.name}</p>
              <p className="text-xs text-muted-foreground">{d.customer.segment} · {d.customer.city} · since {d.customer.customer_since.slice(0, 4)}</p>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
            {[["Policies", d.summary.active_policies], ["Open claims", d.summary.open_claims], ["Contributions/yr", sar(d.summary.total_annual_premium)]].map(([k, v]) => (
              <div key={k} className="rounded-xl bg-muted/60 p-2"><p className="text-muted-foreground">{k}</p><p className="font-semibold">{v}</p></div>
            ))}
          </div>
        </div>
      );
    }
  }
}

export function Citations({ citations, className }: { citations: Citation[]; className?: string }) {
  if (!citations.length) return null;
  return (
    <div className={cn("space-y-1.5", className)}>
      <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        <BookOpen className="size-3" /> Sources
      </p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c) => (
          <details key={`${c.source}-${c.ref}`} className="group max-w-full rounded-lg border border-border bg-card-solid/60 text-xs open:w-full">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-2.5 py-1.5">
              <span className="grid size-4 place-items-center rounded bg-primary/15 text-[10px] font-semibold text-primary">{c.ref}</span>
              <span className="truncate">{c.title}</span>
              <span className="hidden text-muted-foreground sm:inline">· {c.section}</span>
            </summary>
            <p className="border-t border-border px-3 py-2 leading-relaxed text-muted-foreground">{c.content.slice(0, 600)}{c.content.length > 600 ? "…" : ""}</p>
          </details>
        ))}
      </div>
    </div>
  );
}
