"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { FastForward, FilePlus2, FileWarning, ListChecks, Loader2, Mic, Search, Upload } from "lucide-react";
import type { Claim, Policy } from "@/types";
import { consoleApi as api } from "@/services/api";
import { useConsole } from "@/features/console/console-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { ErrorBanner, PageContainer, PageHeader } from "@/components/page-header";
import { ClaimSummaryCard } from "@/features/claims/claim-timeline";
import { useSpeechRecognition } from "@/hooks/use-speech-recognition";
import { cn, fmtDate, sar } from "@/lib/utils";

type Tab = "create" | "track" | "view";
const TYPES = ["Accident - Own Damage", "Accident - Third Party", "Theft", "Windshield", "Flood / Natural Calamity", "Fire",
  "Health - Hospitalisation", "Home - Damage", "Home - Burglary"];
const today = () => new Date().toISOString().slice(0, 10);

function ClaimsInner() {
  const params = useSearchParams();
  const [tab, setTab] = useState<Tab>(params.get("id") ? "track" : "create");
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selected, setSelected] = useState<Claim | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { customerId } = useConsole();
  const refresh = useCallback(() => api.claims(customerId).then(setClaims).catch((e) => setError(e.message)), [customerId]);
  useEffect(() => {
    refresh();
    const id = params.get("id");
    if (id) api.claim(id).then(setSelected).catch((e) => setError(e.message));
  }, [params, refresh]);

  const advance = async (c: Claim) => {
    const next = await api.advanceClaim(c.claim_id);
    setSelected(next);
    refresh();
  };

  const advanceBtn = (c: Claim) =>
    c.status !== "Closed" ? (
      <Button size="sm" variant="secondary" onClick={() => advance(c)}><FastForward /> Simulate next stage</Button>
    ) : null;

  return (
    <PageContainer className="space-y-5">
      <PageHeader title="Claims" subtitle="Back-office view: register, track and progress claims for the selected customer" icon={<FileWarning className="size-5" />} />
      <div className="glass inline-flex rounded-2xl p-1">
        {([["create", "Create claim", FilePlus2], ["track", "Track claim", Search], ["view", "View claims", ListChecks]] as const).map(([id, label, Icon]) => (
          <button key={id} onClick={() => setTab(id)}
            className={cn("relative flex h-11 items-center gap-2 rounded-xl px-3 text-sm sm:px-4", tab === id ? "text-foreground" : "text-muted-foreground")}>
            {tab === id && <motion.span layoutId="claims-tab" className="absolute inset-0 rounded-xl bg-primary/15 ring-1 ring-primary/25" />}
            <Icon className="relative size-4" /><span className="relative">{label}</span>
          </button>
        ))}
      </div>
      {error && <ErrorBanner message={error} />}

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
          {tab === "create" && <CreateClaim onCreated={(c) => { setSelected(c); refresh(); }} created={selected} advanceBtn={advanceBtn} />}
          {tab === "track" && <TrackClaim selected={selected} setSelected={setSelected} advanceBtn={advanceBtn} />}
          {tab === "view" && (
            <div className="grid gap-3 md:grid-cols-2">
              {claims.map((c) => (
                <button key={c.claim_id} onClick={() => { setSelected(c); setTab("track"); }} className="text-left">
                  <Card className="p-4 transition hover:border-primary/40">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">{c.claim_id}</p>
                      <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{c.incident_type} · {fmtDate(c.incident_date)} · {c.location}</p>
                    <p className="mt-2 line-clamp-2 text-sm">{c.description}</p>
                    <div className="mt-3 flex items-center gap-3">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"><div className="h-full bg-success" style={{ width: `${c.progress}%` }} /></div>
                      <span className="text-xs text-muted-foreground">{c.estimated_amount ? sar(c.estimated_amount) : `${c.progress}%`}</span>
                    </div>
                  </Card>
                </button>
              ))}
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </PageContainer>
  );
}

function CreateClaim({ onCreated, created, advanceBtn }: {
  onCreated: (c: Claim) => void; created: Claim | null; advanceBtn: (c: Claim) => React.ReactNode;
}) {
  const { customerId } = useConsole();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [form, setForm] = useState({ policy_id: "", incident_type: TYPES[0], incident_date: today(), location: "", description: "", estimated_amount: "" });
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Claim | null>(null);
  const stt = useSpeechRecognition({ onFinal: (t) => setForm((f) => ({ ...f, description: `${f.description} ${t}`.trim() })) });

  useEffect(() => {
    api.policies(customerId).then((ps) => {
      const active = ps.filter((p) => p.status === "Active" || p.status === "Expiring");
      setPolicies(active);
      if (active[0]) setForm((f) => ({ ...f, policy_id: active.find((p) => p.policy_type === "Motor - Car")?.policy_id || active[0].policy_id }));
    }).catch(() => {});
  }, [customerId]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const desc = files.length ? `${form.description} (Attachments: ${files.map((f) => f.name).join(", ")})` : form.description;
      const c = await api.createClaim(customerId, { ...form, description: desc, estimated_amount: form.estimated_amount ? +form.estimated_amount : undefined });
      setDone(c);
      onCreated(c);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const shown = done && created?.claim_id === done.claim_id ? created : done;
  if (shown) {
    return (
      <div className="space-y-3">
        <div className="rounded-2xl border border-success/30 bg-success/10 p-4 text-sm text-success">
          Claim registered successfully. Your claim ID is <b>{shown.claim_id}</b>.
        </div>
        <ClaimSummaryCard claim={shown} actions={<>
          {advanceBtn(shown)}
          <Button size="sm" variant="ghost" onClick={() => setDone(null)}>Register another</Button>
        </>} />
      </div>
    );
  }

  return (
    <Card className="p-5">
      <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
        <div>
          <Label>Policy</Label>
          <Select value={form.policy_id} onChange={set("policy_id")}>
            {policies.map((p) => <option key={p.policy_id} value={p.policy_id}>{p.policy_type} · {p.policy_id}</option>)}
          </Select>
        </div>
        <div>
          <Label>Incident type</Label>
          <Select value={form.incident_type} onChange={set("incident_type")}>{TYPES.map((t) => <option key={t}>{t}</option>)}</Select>
        </div>
        <div>
          <Label>Incident date</Label>
          <Input type="date" max={today()} value={form.incident_date} onChange={set("incident_date")} required />
        </div>
        <div>
          <Label>Location</Label>
          <Input placeholder="e.g. King Fahd Rd, Riyadh" value={form.location} onChange={set("location")} required />
        </div>
        <div className="md:col-span-2">
          <Label>What happened?</Label>
          <div className="relative">
            <Textarea placeholder="Describe the incident and the damage — or tap the mic and dictate" value={form.description} onChange={set("description")} required minLength={5} className="pr-14" />
            <button type="button" onClick={stt.toggle} aria-label="Dictate description"
              className={cn("absolute right-2 top-2 grid size-10 place-items-center rounded-xl", stt.listening ? "bg-danger text-white" : "bg-muted text-muted-foreground")}>
              <Mic className="size-4" />
            </button>
          </div>
          {stt.listening && <p className="mt-1 text-xs text-danger">Listening… {stt.transcript}</p>}
          {stt.error && <p className="mt-1 text-xs text-danger">{stt.error}</p>}
        </div>
        <div>
          <Label>Estimated loss (SAR, optional)</Label>
          <Input type="number" min={0} inputMode="numeric" value={form.estimated_amount} onChange={set("estimated_amount")} />
        </div>
        <div>
          <Label>Photos / documents (mock upload)</Label>
          <label className="flex h-11 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-border px-4 text-sm text-muted-foreground hover:bg-muted">
            <Upload className="size-4" />
            <span className="truncate">{files.length ? `${files.length} file(s): ${files.map((f) => f.name).join(", ")}` : "Add photos, Najm report, Istimara…"}</span>
            <input type="file" multiple accept="image/*,.pdf" className="hidden" onChange={(e) => setFiles(Array.from(e.target.files || []))} />
          </label>
        </div>
        {error && <div className="md:col-span-2"><ErrorBanner message={error} /></div>}
        <div className="md:col-span-2">
          <Button type="submit" size="lg" disabled={busy} className="w-full md:w-auto">
            {busy ? <Loader2 className="animate-spin" /> : <FilePlus2 />} Register claim
          </Button>
        </div>
      </form>
    </Card>
  );
}

function TrackClaim({ selected, setSelected, advanceBtn }: {
  selected: Claim | null; setSelected: (c: Claim) => void; advanceBtn: (c: Claim) => React.ReactNode;
}) {
  const [id, setId] = useState(selected?.claim_id || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lookup = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setSelected(await api.claim(id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-4">
      <form onSubmit={lookup} className="flex gap-2">
        <Input placeholder="Enter claim ID, e.g. CLM-2610-8812" value={id} onChange={(e) => setId(e.target.value)} className="uppercase" />
        <Button type="submit" disabled={!id.trim() || busy}>{busy ? <Loader2 className="animate-spin" /> : <Search />} Track</Button>
      </form>
      {error && <ErrorBanner message={error} />}
      {selected && <ClaimSummaryCard claim={selected} actions={advanceBtn(selected)} />}
    </div>
  );
}

export default function ClaimsPage() {
  return <Suspense fallback={null}><ClaimsInner /></Suspense>;
}
