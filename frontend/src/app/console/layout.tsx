"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { BookOpenText, Calculator, ExternalLink, FileSpreadsheet, FileWarning, UserRound } from "lucide-react";
import { Logo, ThemeButton } from "@/components/app-shell";
import { ConsoleProvider, useConsole } from "@/features/console/console-context";
import { consoleApi } from "@/services/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/console", label: "Customer 360", icon: UserRound },
  { href: "/console/claims", label: "Claims", icon: FileWarning },
  { href: "/console/quote", label: "Quotes", icon: Calculator },
  { href: "/console/knowledge", label: "Knowledge", icon: BookOpenText },
];

function CustomerPicker() {
  const { customerId, setCustomerId, overview } = useConsole();
  const custs = overview?.customers ?? [];
  return (
    <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} aria-label="Customer"
      className="h-10 max-w-[200px] rounded-xl border border-border bg-card-solid/60 px-3 text-sm">
      {custs.length === 0 && <option value={customerId}>{customerId}</option>}
      {custs.map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name} · {c.customer_id}</option>)}
    </select>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { overview } = useConsole();
  return (
    <div className="relative flex h-dvh flex-col overflow-hidden">
      <div className="aurora" aria-hidden />
      <header className="glass relative z-20 mx-3 mt-3 flex shrink-0 flex-wrap items-center justify-between gap-3 rounded-2xl px-3 py-2.5 md:mx-4 md:mt-4 md:px-4">
        <div className="flex items-center gap-3">
          <Logo subtitle="Staff console · internal" href="/console" />
          <span className="hidden rounded-full bg-warning/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-warning sm:inline">Staff only</span>
        </div>
        <nav className="order-3 flex w-full items-center gap-0.5 overflow-x-auto md:order-none md:w-auto">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/console" ? pathname === "/console" : pathname.startsWith(href);
            return (
              <Link key={href} href={href}
                className={cn("relative flex h-10 shrink-0 items-center gap-2 rounded-xl px-3 text-sm",
                  active ? "text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
                {active && <motion.span layoutId="console-pill" className="absolute inset-0 rounded-xl bg-primary/12 ring-1 ring-primary/25" />}
                <Icon className={cn("relative size-4", active && "text-primary")} />
                <span className="relative">{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-1.5">
          <CustomerPicker />
          <a href={consoleApi.workbookUrl} title="Download art_customer_360.xlsx"
            className={cn("relative grid size-10 place-items-center rounded-xl hover:bg-muted",
              overview?.excel.pending_sync && "text-warning")}>
            <FileSpreadsheet className="size-5" />
            {overview?.excel.pending_sync && <span className="absolute right-2 top-2 size-2 rounded-full bg-warning" />}
          </a>
          <Link href="/" target="_blank" title="Open the customer app" className="hidden size-10 place-items-center rounded-xl hover:bg-muted sm:grid">
            <ExternalLink className="size-5" />
          </Link>
          <ThemeButton />
        </div>
      </header>
      <main className="scrollbar-thin relative z-10 min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <ConsoleProvider>
      <Shell>{children}</Shell>
    </ConsoleProvider>
  );
}
