"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  BadgeCheck, Calculator, CreditCard, FileSpreadsheet, FileWarning, Fingerprint, Lightbulb, Mail, MapPin, MessageSquareText,
  Phone, RefreshCcw, Search, ShieldCheck, Sparkles, UserRound,
} from "lucide-react";
import type { Customer360 } from "@/types";
import { consoleApi } from "@/services/api";
import { useConsole } from "@/features/console/console-context";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ErrorBanner, PageContainer, PageHeader, Skeleton } from "@/components/page-header";
import { PolicyRow } from "@/features/policies/policy-cards";
import { cn, fmtDate, fmtDateTime, humanize, sar, sarShort } from "@/lib/utils";

const fade = (i: number) => ({ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, transition: { delay: i * 0.04 } });

export default function Customer360Page() {
  const { customerId, setCustomerId, overview, error: ovError, refresh } = useConsole();
  const [data, setData] = useState<Customer360 | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(() => {
    setError(null);
    consoleApi.customer360(customerId).then(setData).catch((e) => setError(e.message));
  }, [customerId]);
  useEffect(load, [load]);
  // refresh the open profile when the overview polls (new quotes/claims from the chat)
  useEffect(() => {
    if (overview) load();
  }, [overview, load]);

  const customers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (overview?.customers ?? []).filter((c) =>
      !q || [c.name, c.customer_id, c.phone, c.email, c.city].some((v) => (v || "").toLowerCase().includes(q)));
  }, [overview, search]);
  const chatting = new Set((overview?.active_sessions ?? []).map((s) => s.customer_id));
  const excel = overview?.excel;

  return (
    <PageContainer className="space-y-5">
      <PageHeader title="Customer 360" subtitle="Customer master maintained in art_customer_360.xlsx · used by the Copilot when a registered customer chats"
        icon={<UserRound className="size-5" />}
        actions={
          <div className="flex items-center gap-2">
            <a href={consoleApi.workbookUrl} className="inline-flex h-10 items-center gap-2 rounded-xl border border-border px-3 text-sm hover:bg-muted">
              <FileSpreadsheet className="size-4 text-success" /> Download Excel
            </a>
            <button onClick={() => { consoleApi.syncWorkbook().finally(refresh); }}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-border px-3 text-sm hover:bg-muted">
              <RefreshCcw className="size-4" /> Sync
            </button>
          </div>
        } />

      {excel?.pending_sync && (
        <div className="rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {excel.last_error || "Customer 360 workbook has unsynced changes."}
        </div>
      )}
      {(ovError || error) && <ErrorBanner message={(ovError || error)!} onRetry={() => { refresh(); load(); }} />}

      <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
        {/* Customer list (from Excel) */}
        <Card className="h-fit lg:sticky lg:top-0">
          <CardHeader className="pb-2">
            <CardTitle><FileSpreadsheet className="size-4 text-success" /> Customers sheet</CardTitle>
            <CardDescription>{overview?.customers.length ?? "…"} rows</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-3 size-4 text-muted-foreground" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, ID, mobile (05…), city…" className="pl-9" />
            </div>
            <div className="max-h-[60vh] space-y-1.5 overflow-y-auto pr-1 scrollbar-thin">
              {customers.map((c) => (
                <button key={c.customer_id} onClick={() => setCustomerId(c.customer_id)}
                  className={cn("w-full rounded-xl border px-3 py-2.5 text-left transition",
                    c.customer_id === customerId ? "border-primary/50 bg-primary/10" : "border-border hover:bg-muted/50")}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-medium">{c.name}</p>
                    {chatting.has(c.customer_id) && (
                      <span className="flex items-center gap-1 text-[10px] text-success">
                        <span className="size-1.5 animate-pulse rounded-full bg-success" /> chatting
                      </span>
                    )}
                  </div>
                  <p className="truncate text-[11px] text-muted-foreground">{c.customer_id} · {c.city}</p>
                  {c.onboarded_via === "AI Copilot chat" && <Badge variant="default" className="mt-1"><Sparkles /> Onboarded via Copilot</Badge>}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* 360 detail */}
        {!data ? (
          <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-64" /></div>
        ) : (
          <Detail data={data} chatting={chatting.has(data.customer.id)} />
        )}
      </div>
    </PageContainer>
  );
}

function Detail({ data, chatting }: { data: Customer360; chatting: boolean }) {
  const { customer: c, summary: s } = data;
  const cx = c as Customer360["customer"] & { id_type?: string; id_reference?: string; kyc_source?: string; onboarded_via?: string; registered_at?: string };
  const initials = c.name.split(" ").map((n) => n[0]).slice(0, 2).join("");
  const visible = data.policies.filter((p) => p.status !== "Renewed");
  return (
    <div className="min-w-0 space-y-5">
      <motion.div {...fade(0)} className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {([["Active policies", s.active_policies], ["Annual premium", sar(s.total_annual_premium)], ["Total cover", sarShort(s.total_sum_insured)],
          ["Open claims", s.open_claims], ["Renewals due", s.renewals_due]] as const).map(([k, v], i) => (
          <Card key={k} className={cn("p-4", i === 4 && "col-span-2 md:col-span-1")}>
            <p className="text-xs text-muted-foreground">{k}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">{v}</p>
          </Card>
        ))}
      </motion.div>

      <div className="grid gap-5 xl:grid-cols-3">
        <motion.div {...fade(1)}>
          <Card className="h-full">
            <CardHeader><CardTitle><UserRound className="size-4 text-primary" /> Profile</CardTitle>
              <Badge variant={statusVariant(c.kyc_status)}><BadgeCheck /> KYC {c.kyc_status}</Badge></CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <span className="grid size-14 place-items-center rounded-2xl bg-brand text-lg font-semibold text-white">{initials}</span>
                <div className="min-w-0">
                  <p className="truncate font-semibold">{c.name}</p>
                  <p className="text-xs text-muted-foreground">{c.id} · {c.segment} · since {c.customer_since?.slice(0, 4)}</p>
                  {chatting && <p className="mt-0.5 flex items-center gap-1 text-[11px] text-success"><span className="size-1.5 animate-pulse rounded-full bg-success" /> Chatting with Copilot now</p>}
                </div>
              </div>
              <ul className="mt-4 space-y-2.5 text-sm">
                <li className="flex gap-2.5"><Phone className="mt-0.5 size-4 text-muted-foreground" />{c.phone || "—"}</li>
                <li className="flex gap-2.5"><Mail className="mt-0.5 size-4 text-muted-foreground" /><span className="break-all">{c.email || "—"}</span></li>
                <li className="flex gap-2.5"><MapPin className="mt-0.5 size-4 shrink-0 text-muted-foreground" />{c.address}</li>
              </ul>
              <div className="mt-4 space-y-1 rounded-xl bg-muted/50 p-3 text-xs">
                <p className="flex items-center gap-1.5 font-medium"><Fingerprint className="size-3.5" /> KYC & onboarding</p>
                <p className="text-muted-foreground">{cx.id_type} {cx.id_reference} · {(c as unknown as { nationality?: string }).nationality || "—"} · DOB {fmtDate(c.date_of_birth)}</p>
                <p className="text-muted-foreground">Source: {cx.kyc_source || "—"}</p>
                <p className="text-muted-foreground">Onboarded via {cx.onboarded_via || "—"}{cx.registered_at ? ` · ${fmtDateTime(cx.registered_at)}` : ""}</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div {...fade(2)} className="xl:col-span-2">
          <Card className="h-full">
            <CardHeader><CardTitle><Lightbulb className="size-4 text-warning" /> Recommended actions</CardTitle>
              <CardDescription>Next-best actions the Copilot can offer this customer</CardDescription></CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2">
              {data.recommended_actions.map((a) => (
                <div key={a.title} className="rounded-xl border border-border bg-card-solid/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{a.title}</p>
                    <Badge variant={a.priority === "high" ? "danger" : a.priority === "medium" ? "warning" : "muted"}>{a.priority}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{a.detail}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <motion.div {...fade(3)}>
          <Card className="h-full">
            <CardHeader><CardTitle><ShieldCheck className="size-4 text-primary" /> Policies</CardTitle>
              <CardDescription>{visible.length} on record</CardDescription></CardHeader>
            <CardContent className="space-y-2">
              {visible.length === 0 && <p className="text-sm text-muted-foreground">No policies yet.</p>}
              {visible.map((p) => <PolicyRow key={p.policy_id} p={p} />)}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div {...fade(4)}>
          <Card className="h-full">
            <CardHeader><CardTitle><MessageSquareText className="size-4 text-accent" /> Copilot conversations</CardTitle>
              <CardDescription>Latest requests from this customer</CardDescription></CardHeader>
            <CardContent className="space-y-2">
              {!data.conversations?.length && <p className="text-sm text-muted-foreground">No conversations yet.</p>}
              {data.conversations?.map((r, i) => (
                <div key={i} className="rounded-xl border border-border bg-card-solid/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-medium">“{r.prompt}”</p>
                    <span className="shrink-0 text-[10px] text-muted-foreground">{fmtDateTime(r.created_at)}</span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{r.reply?.replace(/[*#]/g, "")}</p>
                  {!!r.tools?.length && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {r.tools.map((t, j) => <span key={j} className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] text-primary">{humanize(t)}</span>)}
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div {...fade(5)}>
          <Card className="h-full">
            <CardHeader><CardTitle><FileWarning className="size-4 text-danger" /> Claims</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {data.claims.length === 0 && <p className="text-sm text-muted-foreground">No claims.</p>}
              {data.claims.map((cl) => (
                <a key={cl.claim_id} href={`/console/claims?id=${cl.claim_id}`}
                  className="block rounded-xl border border-border bg-card-solid/60 p-3 transition hover:border-primary/40">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{cl.claim_id}</p>
                    <Badge variant={statusVariant(cl.status)}>{cl.status}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{cl.incident_type} · {fmtDate(cl.incident_date)}{cl.estimated_amount ? ` · ${sar(cl.estimated_amount)}` : ""}</p>
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted"><div className="h-full bg-success" style={{ width: `${cl.progress}%` }} /></div>
                </a>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div {...fade(6)}>
          <Card className="h-full">
            <CardHeader><CardTitle><Calculator className="size-4 text-primary" /> Quotations</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {data.quotes.length === 0 && <p className="text-sm text-muted-foreground">No quotes yet.</p>}
              {data.quotes.map((q) => (
                <div key={q.quote_id} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-card-solid/60 p-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{q.product}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {q.quote_id} · {fmtDate(q.created_at)}
                      {q.details?.vehicle_label ? ` · ${q.details.vehicle_label}` : ""}{q.details?.location ? `, ${q.details.location}` : ""}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold tabular-nums">{sar(q.premium)}</p>
                    {q.details?.purchased_policy_id
                      ? <Badge variant="success" className="mt-0.5">Purchased · {String(q.details.purchased_policy_id)}</Badge>
                      : q.risk_score != null && <p className="text-[11px] text-muted-foreground">Risk {q.risk_score}</p>}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      <motion.div {...fade(7)}>
        <Card>
          <CardHeader><CardTitle><CreditCard className="size-4 text-success" /> Payments</CardTitle>
            <CardDescription>Simulated gateway transactions · also in the Payments sheet</CardDescription></CardHeader>
          <CardContent>
            {!data.payments?.length ? <p className="text-sm text-muted-foreground">No payments yet.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-left text-xs">
                  <thead className="text-muted-foreground">
                    <tr>{["Date", "Payment ID", "Policy", "Method", "Amount", "Status"].map((h) => <th key={h} className="pb-2 font-medium">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {data.payments.map((pm) => (
                      <tr key={pm.payment_id} className="border-t border-border">
                        <td className="py-2">{fmtDateTime(pm.created_at)}</td>
                        <td className="py-2 font-mono text-[11px]">{pm.payment_id}</td>
                        <td className="py-2">{pm.policy_id}</td>
                        <td className="py-2">{pm.method}</td>
                        <td className="py-2 tabular-nums">{sar(pm.amount)}</td>
                        <td className="py-2"><Badge variant="success">{pm.status}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
