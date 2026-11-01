"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ConsoleOverview } from "@/types";
import { consoleApi } from "@/services/api";

interface ConsoleCtx {
  customerId: string;
  setCustomerId: (id: string) => void;
  overview: ConsoleOverview | null;
  error: string | null;
  refresh: () => Promise<void>;
}

const Ctx = createContext<ConsoleCtx | null>(null);
const KEY = "console.customer";

export function ConsoleProvider({ children }: { children: React.ReactNode }) {
  const [customerId, setId] = useState("CUST-1001");
  const [overview, setOverview] = useState<ConsoleOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setOverview(await consoleApi.overview());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved) setId(saved);
    } catch {}
    refresh();
    const t = setInterval(refresh, 15_000); // pick up new registrations + Excel edits
    return () => clearInterval(t);
  }, [refresh]);

  const setCustomerId = (id: string) => {
    setId(id);
    try {
      localStorage.setItem(KEY, id);
    } catch {}
  };

  return <Ctx.Provider value={{ customerId, setCustomerId, overview, error, refresh }}>{children}</Ctx.Provider>;
}

export function useConsole() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useConsole must be used inside ConsoleProvider");
  return c;
}
