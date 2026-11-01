"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, BadgeCheck, Car, Clock, FileWarning, HeartHandshake, HeartPulse, House, Landmark,
  MessageSquareText, Mic, PiggyBank, RefreshCcw, ShieldCheck, UserRound, UserRoundCheck,
} from "lucide-react";
import type { Health } from "@/types";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { START_PROMPTS } from "@/features/chat/chat-view";
import { ASSISTANT_NAME, INSURER_NAME, INSURER_SHORT } from "@/lib/brand";
import { cn } from "@/lib/utils";

const chat = (q: string) => `/chat?q=${encodeURIComponent(q)}`;

const PRODUCTS = [
  {
    icon: Car, title: "Motor", sub: "Takaful", from: "TPL from SAR 1,092",
    plans: ["Motor TPL", "Motor Comprehensive", "Motor Comprehensive Plus"],
    points: ["Agency repair for newer cars", "Floods & sandstorms covered", "No Claim Discount up to 30%"],
    q: "I want motor insurance",
  },
  {
    icon: HeartPulse, title: "Health", sub: "Individual", from: "From SAR 2,860 a year",
    plans: ["Health Essential", "Health Gold", "Health Premier"],
    points: ["2,000+ network hospitals", "Chronic conditions covered", "24/7 telemedicine"],
    q: "I want an individual health plan",
  },
  {
    icon: HeartHandshake, title: "Life", sub: "Protection", from: "SAR 1.5M cover from ~SAR 285/month",
    plans: ["Life Protect", "Life Protect Plus", "Life Premier"],
    points: ["Lump sum for your family", "Critical illness & disability", "VAT-exempt contributions"],
    q: "I want a life protection plan",
  },
  {
    icon: PiggyBank, title: "Retirement & Savings", sub: "Shariah-compliant", from: "Retirement Plan from SAR 1,000 a month",
    plans: ["Retirement Plan", "Savings Plan", "Education Plan"],
    points: ["Monthly income for 5–20 years after you retire", "Save for any goal, with Takaful protection", "Save for your child's university"],
    q: "I want a retirement savings plan",
  },
  {
    icon: House, title: "General", sub: "Home & property", from: "From SAR 290 a year",
    plans: ["Home Basic", "Home Plus", "Home Premier"],
    points: ["Fire, flood & sandstorm", "Burglary & contents", "Rent if your home is unliveable"],
    q: "I want home insurance",
  },
];

const SERVICES = [
  { icon: FileWarning, title: "Report a claim", text: "Tell us what happened — registered in a minute", q: "I had an accident" },
  { icon: Clock, title: "Track a claim", text: "See every stage, from survey to settlement", q: "What's the status of my claim?" },
  { icon: RefreshCcw, title: "Renew a plan", text: "Keep your No Claim Discount in one conversation", q: "Renew my policy" },
  { icon: ShieldCheck, title: "My plans", text: "Everything you hold with us, in one place", q: "What policies do I have?" },
];

export default function HomePage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [active, setActive] = useState(3); // Retirement & Savings in focus
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);
  const p = PRODUCTS[active];

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-10 md:px-6">
      {/* Hero */}
      <section className="pt-8 text-center md:pt-12">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card-solid px-3 py-1 text-xs text-muted-foreground shadow-card">
            <span className={`size-1.5 rounded-full ${health ? "bg-success" : "bg-warning"}`} />
            {health ? (health.agent_mode === "gemini" ? `${ASSISTANT_NAME} is online` : `${ASSISTANT_NAME} · offline demo mode`) : "Connecting…"}
          </span>
          <h1 className="mx-auto mt-5 max-w-4xl text-3xl font-bold leading-tight md:text-5xl">
            Takaful solutions tailored to your needs — <span className="text-gradient">just talk to us</span>
          </h1>
          <p className="mx-auto mt-3 max-w-2xl text-base text-muted-foreground">
            Get a quote, buy, claim and renew individual plans in one conversation, by voice or text.
          </p>
          <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="w-full sm:w-auto">
              <Link href="/chat?voice=1"><Mic /> Talk to {INSURER_SHORT}</Link>
            </Button>
            <Button asChild size="lg" variant="secondary" className="w-full sm:w-auto">
              <Link href="/chat"><MessageSquareText /> Chat with us</Link>
            </Button>
          </div>
        </motion.div>
      </section>

      {/* Retirement in focus */}
      <section className="mt-10 overflow-hidden rounded-3xl border border-border bg-card-solid shadow-card">
        <div className="grid md:grid-cols-[1.3fr_1fr]">
          <div className="p-6 md:p-8">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              <PiggyBank className="size-3.5" /> Retirement Plan · new
            </span>
            <h2 className="mt-3 text-2xl font-bold md:text-3xl">Your retirement, planned in one conversation</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Tell {ASSISTANT_NAME} when you&apos;d like to retire and what you can save. Contribute until then — into
              Shariah-compliant funds — and receive a monthly income for up to 20 years after, with Takaful protection
              for your family all along.
            </p>
            <ul className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
              {["Retire between 55 and 65", "From SAR 1,000 a month · monthly to yearly", "Conservative, Balanced or Growth fund",
                "Protection from SAR 50,000 + critical-illness add-on"].map((x) => (
                <li key={x} className="flex gap-2"><BadgeCheck className="mt-0.5 size-4 shrink-0 text-success" />{x}</li>
              ))}
            </ul>
            <Link href={chat("I want to plan my retirement")}
              className="mt-5 inline-flex h-11 items-center gap-2 rounded-lg bg-brand px-5 text-sm font-medium text-white shadow-md shadow-primary/25 hover:brightness-110">
              Plan my retirement <ArrowRight className="size-4" />
            </Link>
          </div>
          <div className="brand-wave relative flex flex-col justify-center gap-3 p-6 text-white md:p-8">
            <p className="text-xs uppercase tracking-wider opacity-80">Illustration · age 35, SAR 2,000/month</p>
            {[["Contribute", "25 years", "to age 60"], ["Projected fund", "≈ SAR 894,000", "Balanced fund, 5% a year after fees"],
              ["Retirement income", "≈ SAR 6,175 a month", "for 15 years"]].map(([k, v, d]) => (
              <div key={k} className="rounded-xl bg-white/12 p-3 backdrop-blur">
                <p className="text-[11px] opacity-80">{k}</p>
                <p className="text-xl font-bold">{v}</p>
                <p className="text-[11px] opacity-80">{d}</p>
              </div>
            ))}
            <p className="text-[10px] opacity-75">Projections are illustrative and not guaranteed.</p>
          </div>
        </div>
      </section>

      {/* Product cards — like the site's carousel */}
      <section className="mt-10">
        <div className="mb-4 flex justify-center">
          <div className="inline-flex gap-1 rounded-full border border-border bg-card-solid p-1 shadow-card">
            <span className="flex items-center gap-1.5 rounded-full bg-brand px-4 py-1.5 text-sm font-medium text-white"><UserRound className="size-4" /> Individual</span>
            <span className="flex items-center gap-1.5 px-4 py-1.5 text-sm text-muted-foreground" title="Not part of this demo">Business</span>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {PRODUCTS.map(({ icon: Icon, title, sub }, i) => (
            <motion.button key={title} onClick={() => setActive(i)} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 + i * 0.05 }}
              className={cn("group overflow-hidden rounded-2xl border bg-card-solid text-left shadow-card transition hover:-translate-y-0.5",
                active === i ? "border-primary ring-2 ring-primary/20" : "border-border")}>
              <div className="p-4 pb-3">
                <Icon className="size-6 text-primary" />
                <p className="mt-2 font-semibold text-navy">{title}</p>
                <p className="text-xs text-muted-foreground">{sub}</p>
              </div>
              <div className="brand-wave relative mx-3 mb-3 grid h-24 place-items-center overflow-hidden rounded-xl">
                <Icon className="size-12 text-white/95 drop-shadow transition group-hover:scale-110" strokeWidth={1.4} />
              </div>
            </motion.button>
          ))}
        </div>

        {/* Detail of the selected portfolio — like "Find out Motor Insurance and get your policy" */}
        <motion.div key={active} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="mt-4 grid gap-6 rounded-2xl border border-border bg-card-solid p-6 shadow-card md:grid-cols-[1.4fr_1fr] md:p-8">
          <div>
            <h2 className="text-2xl font-bold md:text-3xl">Find out {p.title} and get your plan</h2>
            <p className="mt-2 text-sm text-muted-foreground">Choose from three plans designed to match your needs. {p.from}.</p>
            <ul className="mt-4 grid gap-2 sm:grid-cols-3">
              {p.plans.map((pl, i) => (
                <li key={pl} className="rounded-xl border border-border bg-muted/50 p-3">
                  <p className="text-sm font-semibold text-navy">{pl}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{p.points[i]}</p>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex flex-col justify-center rounded-2xl bg-muted/60 p-5">
            <p className="text-lg font-semibold text-navy">Get your plan now</p>
            <p className="mt-1 text-sm text-muted-foreground">Share your National ID or Iqama and approve Nafath — we fill in the rest.</p>
            <Link href={chat(p.q)}
              className="mt-4 inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-brand text-sm font-medium text-white shadow-md shadow-primary/25 hover:brightness-110">
              Get a quote <ArrowRight className="size-4" />
            </Link>
          </div>
        </motion.div>
      </section>

      {/* Services */}
      <section className="mt-10">
        <h2 className="mb-4 text-xl font-bold">Our services</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {SERVICES.map(({ icon: Icon, title, text, q }) => (
            <Link key={title} href={chat(q)} className="group">
              <div className="h-full rounded-2xl border border-border bg-card-solid p-4 shadow-card transition group-hover:-translate-y-0.5 group-hover:border-primary/40">
                <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="size-5" /></span>
                <p className="mt-3 font-semibold text-navy">{title}</p>
                <p className="text-sm text-muted-foreground">{text}</p>
              </div>
            </Link>
          ))}
        </div>
        <Link href={chat(START_PROMPTS.existing)}
          className="mt-3 flex items-center gap-4 rounded-2xl border border-primary/25 bg-primary/5 p-4 transition hover:border-primary/50">
          <UserRoundCheck className="size-6 text-primary" />
          <span className="flex-1">
            <span className="block font-semibold text-navy">Already with {INSURER_SHORT}?</span>
            <span className="block text-sm text-muted-foreground">Verify with your registered mobile to manage your plans and claims.</span>
          </span>
          <ArrowRight className="size-4 text-primary" />
        </Link>
      </section>

      <footer className="mt-12 flex flex-col items-center gap-1 border-t border-border pt-6 text-center text-[11px] text-muted-foreground">
        <p className="flex items-center gap-1.5"><Landmark className="size-3" /> {INSURER_NAME} · Kingdom of Saudi Arabia</p>
        <p className="flex items-center gap-1.5"><BadgeCheck className="size-3" /> Proof of concept — plans, prices, Nafath/Yakeen checks and payments are simulated. Contributions in SAR; Health, Motor and General include 15% VAT, Life and Retirement & Savings are VAT-exempt.</p>
      </footer>
    </div>
  );
}
