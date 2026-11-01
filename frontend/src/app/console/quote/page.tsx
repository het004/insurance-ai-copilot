"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bike, Building2, Calculator, Car, HeartHandshake, HeartPulse, House, Loader2, PiggyBank, Sparkles, Zap,
} from "lucide-react";
import type { QuoteResult } from "@/types";
import { consoleApi as api } from "@/services/api";
import { useConsole } from "@/features/console/console-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { ErrorBanner, PageContainer, PageHeader } from "@/components/page-header";
import { QuoteResultCard } from "@/features/quote/quote-result";
import { cn } from "@/lib/utils";

type Line = "health" | "motor" | "life" | "savings" | "general";
const LINES: { id: Line; label: string; icon: React.ElementType }[] = [
  { id: "motor", label: "Motor", icon: Car }, { id: "health", label: "Health", icon: HeartPulse },
  { id: "life", label: "Life", icon: HeartHandshake }, { id: "savings", label: "Savings", icon: PiggyBank },
  { id: "general", label: "General", icon: House },
];
const VEHICLES = [
  { id: "car", label: "Car", icon: Car }, { id: "suv", label: "SUV", icon: Car }, { id: "ev", label: "Electric", icon: Zap },
  { id: "bike", label: "Motorcycle", icon: Bike },
];
const MOTOR_PLANS = [
  { id: "tpl", label: "Motor TPL", hint: "Mandatory liability" },
  { id: "comprehensive", label: "Motor Comprehensive", hint: "Workshop repair" },
  { id: "comprehensive_plus", label: "Motor Comprehensive Plus", hint: "Agency repair" },
];
const PLANS: Record<Exclude<Line, "motor">, { id: string; label: string }[]> = {
  health: [{ id: "", label: "Recommend for me" }, { id: "health_essential", label: "Health Essential" },
    { id: "health_gold", label: "Health Gold" }, { id: "health_premier", label: "Health Premier" }],
  life: [{ id: "", label: "Recommend for me" }, { id: "life_protect", label: "Life Protect" },
    { id: "life_protect_plus", label: "Life Protect Plus" }, { id: "life_premier", label: "Life Premier" }],
  savings: [{ id: "savings_plan", label: "Savings Plan" }, { id: "retirement_plan", label: "Retirement Plan" },
    { id: "education_plan", label: "Education Plan" }],
  general: [{ id: "", label: "Recommend for me" }, { id: "home_basic", label: "Home Basic" },
    { id: "home_plus", label: "Home Plus" }, { id: "home_premier", label: "Home Premier" }],
};
const CITIES = ["Riyadh", "Jeddah", "Makkah", "Madinah", "Dammam", "Al Khobar", "Dhahran", "Taif", "Abha", "Tabuk",
  "Buraidah", "Khamis Mushait", "Hail", "Jazan", "Najran", "Al Ahsa", "Jubail", "Yanbu"];

function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { id: T; label: string; icon?: React.ElementType }[] }) {
  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map(({ id, label, icon: Icon }) => (
        <button type="button" key={id} onClick={() => onChange(id)}
          className={cn("flex h-12 flex-col items-center justify-center gap-0.5 rounded-xl border text-xs transition sm:flex-row sm:gap-1.5 sm:text-sm",
            value === id ? "border-primary bg-primary/12 text-primary" : "border-border hover:bg-muted")}>
          {Icon && <Icon className="size-4" />}{label}
        </button>
      ))}
    </div>
  );
}

export default function QuotePage() {
  const { customerId } = useConsole();
  const [line, setLine] = useState<Line>("motor");
  const [city, setCity] = useState("Riyadh");
  // health
  const [healthAge, setHealthAge] = useState(38);
  const [chronic, setChronic] = useState(false);
  // motor
  const [vehicle, setVehicle] = useState("car");
  const [age, setAge] = useState(0);
  const [coverage, setCoverage] = useState("comprehensive_plus");
  const [ncd, setNcd] = useState(0);
  // life
  const [lifeAge, setLifeAge] = useState(35);
  const [smoker, setSmoker] = useState(false);
  const [sumAssured, setSumAssured] = useState(1_500_000);
  const [term, setTerm] = useState(20);
  // savings
  const [monthly, setMonthly] = useState(1000);
  const [savingsYears, setSavingsYears] = useState(20);
  // general
  const [ptype, setPtype] = useState<"apartment" | "villa">("villa");
  const [building, setBuilding] = useState(1_500_000);
  const [contents, setContents] = useState(200_000);
  const [plan, setPlan] = useState("");

  const [quote, setQuote] = useState<QuoteResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const p = plan || undefined;
      setQuote(
        line === "motor"
          ? await api.createQuote(customerId, { vehicle_type: vehicle, vehicle_age: age, coverage, location: city, ncb_percent: ncd })
          : line === "health"
            ? await api.createLineQuote(customerId, "health", { age: healthAge, city, pre_existing: chronic }, p)
            : line === "life"
              ? await api.createLineQuote(customerId, "life", { age: lifeAge, smoker, sum_assured: sumAssured, term_years: term }, p)
              : line === "savings"
                ? await api.createLineQuote(customerId, "savings", { age: lifeAge, monthly_contribution: monthly, term_years: savingsYears }, p || "savings_plan")
                : await api.createLineQuote(customerId, "general", { property_type: ptype, building_value: building, contents_value: contents, city }, p),
      );
      if (window.innerWidth < 1024) setTimeout(() => document.getElementById("quote-result")?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const num = (setter: (n: number) => void) => (e: React.ChangeEvent<HTMLInputElement>) => setter(+e.target.value);

  return (
    <PageContainer className="space-y-5">
      <PageHeader title="Get a quote" subtitle="Rating workbench for our individual Motor, Health, Life, Retirement & Savings and General plans — quotes are saved to the selected customer"
        icon={<Calculator className="size-5" />} />

      <div className="grid gap-5 lg:grid-cols-[400px_1fr]">
        <Card className="h-fit p-5">
          <form onSubmit={submit} className="space-y-5">
            <div>
              <Label>Category</Label>
              <Segmented value={line} onChange={(v) => { setLine(v); setQuote(null); setPlan(""); }} options={LINES} />
            </div>

            {line === "health" && (
              <>
                <div>
                  <Label htmlFor="healthAge">Age (individual plan): <b className="text-foreground">{healthAge} years</b></Label>
                  <input id="healthAge" type="range" min={18} max={75} value={healthAge} onChange={num(setHealthAge)} className="h-11 w-full accent-[var(--primary)]" />
                </div>
                <label className="flex h-11 items-center gap-3 rounded-xl border border-border px-4 text-sm">
                  <input type="checkbox" checked={chronic} onChange={(e) => setChronic(e.target.checked)} className="size-4 accent-[var(--primary)]" />
                  Chronic condition declared (diabetes, hypertension…)
                </label>
              </>
            )}

            {line === "motor" && (
              <>
                <div>
                  <Label>Vehicle type</Label>
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-3">
                    {VEHICLES.map(({ id, label, icon: Icon }) => (
                      <button type="button" key={id} onClick={() => setVehicle(id)}
                        className={cn("flex h-16 flex-col items-center justify-center gap-1 rounded-xl border text-xs transition",
                          vehicle === id ? "border-primary bg-primary/12 text-primary" : "border-border hover:bg-muted")}>
                        <Icon className="size-5" />{label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label htmlFor="age">Vehicle age: <b className="text-foreground">{age === 0 ? "Brand new" : `${age} year${age > 1 ? "s" : ""}`}</b></Label>
                  <input id="age" type="range" min={0} max={15} value={age} onChange={num(setAge)} className="h-11 w-full accent-[var(--primary)]" />
                </div>
                <div>
                  <Label>Plan</Label>
                  <div className="grid gap-2">
                    {MOTOR_PLANS.map((c) => (
                      <button type="button" key={c.id} onClick={() => setCoverage(c.id)}
                        className={cn("flex h-12 items-center justify-between rounded-xl border px-4 text-sm transition",
                          coverage === c.id ? "border-primary bg-primary/12" : "border-border hover:bg-muted")}>
                        <span className="font-medium">{c.label}</span>
                        <span className="text-xs text-muted-foreground">{c.hint}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div><Label>No Claim Discount</Label>
                  <Select value={ncd} onChange={(e) => setNcd(+e.target.value)}>{[0, 15, 20, 25, 30].map((n) => <option key={n} value={n}>{n}%</option>)}</Select></div>
              </>
            )}

            {line === "life" && (
              <>
                <div>
                  <Label htmlFor="lifeAge">Age: <b className="text-foreground">{lifeAge}</b></Label>
                  <input id="lifeAge" type="range" min={18} max={65} value={lifeAge} onChange={num(setLifeAge)} className="h-11 w-full accent-[var(--primary)]" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Sum covered (SAR)</Label><Input type="number" min={100000} step={50000} value={sumAssured} onChange={num(setSumAssured)} /></div>
                  <div><Label>Term</Label>
                    <Select value={term} onChange={(e) => setTerm(+e.target.value)}>{[10, 15, 20, 25, 30].map((n) => <option key={n} value={n}>{n} years</option>)}</Select></div>
                </div>
                <label className="flex h-11 items-center gap-3 rounded-xl border border-border px-4 text-sm">
                  <input type="checkbox" checked={smoker} onChange={(e) => setSmoker(e.target.checked)} className="size-4 accent-[var(--primary)]" />
                  Smoker (incl. shisha)
                </label>
              </>
            )}

            {line === "savings" && (
              <>
                <div>
                  <Label htmlFor="savAge">Age: <b className="text-foreground">{lifeAge}</b></Label>
                  <input id="savAge" type="range" min={18} max={60} value={lifeAge} onChange={num(setLifeAge)} className="h-11 w-full accent-[var(--primary)]" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Monthly (SAR)</Label><Input type="number" min={300} step={100} value={monthly} onChange={num(setMonthly)} /></div>
                  <div><Label>Years</Label>
                    <Select value={savingsYears} onChange={(e) => setSavingsYears(+e.target.value)}>{[5, 10, 15, 20, 25, 30].map((n) => <option key={n} value={n}>{n} years</option>)}</Select></div>
                </div>
              </>
            )}

            {line === "general" && (
              <>
                <div><Label>Property type</Label>
                  <Segmented value={ptype} onChange={setPtype} options={[{ id: "apartment", label: "Apartment", icon: Building2 }, { id: "villa", label: "Villa", icon: House }]} /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Rebuild value (SAR)</Label><Input type="number" min={100000} step={50000} value={building} onChange={num(setBuilding)} /></div>
                  <div><Label>Contents (SAR)</Label><Input type="number" min={0} step={10000} value={contents} onChange={num(setContents)} /></div>
                </div>
              </>
            )}

            <div className="grid grid-cols-2 gap-3">
              {line !== "life" && line !== "savings" && (
                <div className={cn(line === "motor" && "col-span-2")}>
                  <Label htmlFor="city">City</Label>
                  <Select id="city" value={city} onChange={(e) => setCity(e.target.value)}>{CITIES.map((c) => <option key={c}>{c}</option>)}</Select>
                </div>
              )}
              {line !== "motor" && (
                <div className={cn((line === "life" || line === "savings") && "col-span-2")}>
                  <Label>Plan</Label>
                  <Select value={plan} onChange={(e) => setPlan(e.target.value)}>
                    {PLANS[line].map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                  </Select>
                </div>
              )}
            </div>

            <Button type="submit" size="lg" className="w-full" disabled={loading}>
              {loading ? <Loader2 className="animate-spin" /> : <Sparkles />} Generate quote
            </Button>
          </form>
        </Card>

        <div id="quote-result" className="min-w-0 space-y-3">
          {error && <ErrorBanner message={error} />}
          <AnimatePresence mode="wait">
            {quote ? (
              <motion.div key={quote.quote_id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <QuoteResultCard quote={quote} />
              </motion.div>
            ) : (
              <Card className="grid min-h-80 place-items-center p-8 text-center">
                <div>
                  <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary/12 text-primary"><Calculator className="size-6" /></span>
                  <p className="mt-4 font-medium">Your quotation will appear here</p>
                  <p className="mt-1 text-sm text-muted-foreground">Choose a category, fill in the details, then generate.</p>
                </div>
              </Card>
            )}
          </AnimatePresence>
        </div>
      </div>
    </PageContainer>
  );
}
