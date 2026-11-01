"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { FileWarning, Headset, Home, MessageSquareText, Mic, Moon, RefreshCcw, Sun, UserRound } from "lucide-react";
import { cn } from "@/lib/utils";
import { ASSISTANT_NAME, INSURER_NAME, INSURER_NAME_AR, LOGO_SRC } from "@/lib/brand";

/* Customer-facing app: the chatbot is the only experience. Customer 360, claims back office,
   quotes and the knowledge admin live in the staff console (/console), not linked from here. */
const NAV = [
  { href: "/", label: "Home", icon: Home },
  { href: "/chat", label: `Chat with ${ASSISTANT_NAME}`, icon: MessageSquareText },
];

function isActive(pathname: string, href: string) {
  const path = href.split("?")[0];
  return path === "/" ? pathname === "/" : pathname.startsWith(path);
}

export function useTheme() {
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
  };
  return { dark, toggle };
}

/** Brand lock-up as on alrajhitakaful.com: bilingual name on the left, the logo mark on the right. */
export function Logo({ subtitle, href = "/" }: { subtitle?: string; href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2.5" aria-label={INSURER_NAME}>
      <span className="leading-none text-navy">
        <span className="arabic block text-[17px] font-bold" dir="rtl" lang="ar">{INSURER_NAME_AR}</span>
        <span className="block text-[15px] font-semibold tracking-tight">{INSURER_NAME}</span>
      </span>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={LOGO_SRC} alt="" className="h-9 w-auto md:h-10" />
      {subtitle && <span className="ml-1 hidden rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary sm:inline">{subtitle}</span>}
    </Link>
  );
}

/** Small round avatar used for the assistant in the chat. */
export function BrandAvatar({ className }: { className?: string }) {
  return (
    <span className={cn("grid size-8 shrink-0 place-items-center rounded-full bg-white shadow-card ring-1 ring-border", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={LOGO_SRC} alt="" className="w-[70%]" />
    </span>
  );
}

export function ThemeButton() {
  const { dark, toggle } = useTheme();
  return (
    <button onClick={toggle} aria-label="Toggle theme" className="grid size-10 place-items-center rounded-xl hover:bg-muted">
      {dark ? <Sun className="size-5" /> : <Moon className="size-5" />}
    </button>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden">
      <div className="aurora" aria-hidden />

      {/* Header styled like alrajhitakaful.com: Individual/Business strip + white nav bar */}
      <header className="relative z-20 shrink-0 border-b border-border bg-card-solid/95 backdrop-blur"
        style={{ paddingTop: "env(safe-area-inset-top)" }}>
        <div className="mx-auto hidden h-10 max-w-7xl items-center justify-between border-b border-border px-6 text-sm md:flex">
          <div className="flex h-full items-center gap-6">
            <span className="relative flex h-full items-center font-semibold text-primary after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:rounded-full after:bg-primary">Individual</span>
            <span className="text-muted-foreground" title="This demo covers individual plans">Business</span>
          </div>
          <div className="flex items-center gap-4 text-muted-foreground">
            <Link href="/chat?q=I%20need%20help" className="flex items-center gap-1.5 rounded-lg bg-muted px-2.5 py-1 text-navy hover:text-primary"><Headset className="size-4" /> Help Center</Link>
            <span className="arabic" lang="ar">عربي</span>
          </div>
        </div>
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 md:h-[72px] md:px-6">
          <Logo />
          <nav className="hidden items-center gap-1 lg:flex">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <Link key={href} href={href}
                  className={cn("relative flex h-10 items-center gap-2 rounded-lg px-3 text-[15px] transition-colors",
                    active ? "text-primary" : "text-navy hover:text-primary")}>
                  {active && (
                    <motion.span layoutId="nav-pill" className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-primary"
                      transition={{ type: "spring", stiffness: 400, damping: 32 }} />
                  )}
                  <Icon className="relative size-4" />
                  <span className="relative">{label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-2">
            <Link href="/chat?q=I%20want%20to%20report%20a%20claim"
              className="hidden h-10 items-center gap-2 rounded-lg border border-primary/40 px-4 text-sm font-medium text-primary hover:bg-primary/5 md:flex">
              <FileWarning className="size-4" /> Claims
            </Link>
            <Link href="/chat?q=Renew%20my%20policy"
              className="hidden h-10 items-center gap-2 rounded-lg border border-primary/40 px-4 text-sm font-medium text-primary hover:bg-primary/5 xl:flex">
              <RefreshCcw className="size-4" /> Renew Policy
            </Link>
            <Link href="/chat?voice=1"
              className="hidden h-10 items-center gap-2 rounded-lg bg-brand px-4 text-sm font-medium text-white shadow-md shadow-primary/25 hover:brightness-110 md:flex">
              <Mic className="size-4" /> Talk to us
            </Link>
            <Link href="/chat?q=I%27m%20an%20existing%20customer" aria-label="My account"
              className="grid size-10 place-items-center rounded-lg text-navy hover:bg-muted md:hidden"><UserRound className="size-5" /></Link>
            <ThemeButton />
          </div>
        </div>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        <main className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">{children}</main>

        {/* Mobile bottom navigation with sticky voice button */}
        <nav className="glass mx-3 mb-3 grid h-16 shrink-0 grid-cols-3 items-center rounded-2xl px-1 md:hidden"
          style={{ marginBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}>
          <Link href="/" className={cn("flex h-full flex-col items-center justify-center gap-1 text-[10px]",
            pathname === "/" ? "text-primary" : "text-muted-foreground")}>
            <Home className="size-5" /> Home
          </Link>
          <Link href="/chat?voice=1" aria-label="Talk to us" className="flex justify-center">
            <span className="grid size-15 -translate-y-5 place-items-center rounded-full bg-brand text-white shadow-xl shadow-primary/40 ring-4 ring-background transition-transform active:scale-95">
              <Mic className="size-6" />
            </span>
          </Link>
          <Link href="/chat" className={cn("flex h-full flex-col items-center justify-center gap-1 text-[10px]",
            pathname.startsWith("/chat") ? "text-primary" : "text-muted-foreground")}>
            <MessageSquareText className="size-5" /> Chat
          </Link>
        </nav>
      </div>
    </div>
  );
}
