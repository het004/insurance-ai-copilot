import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const sar = (n: number | null | undefined) =>
  n == null ? "—" : `SAR ${Math.round(n).toLocaleString("en-US")}`;

/** Compact SAR: SAR 1.5M / SAR 285,000 */
export const sarShort = (n: number | null | undefined) => {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e6) return `SAR ${(n / 1e6).toFixed(2).replace(/\.?0+$/, "")}M`;
  return sar(n);
};

export const fmtDate = (s?: string | null) =>
  s ? new Date(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";

export const fmtDateTime = (s?: string | null) =>
  s ? new Date(s).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "—";

export const humanize = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const SPEECH_LANG = process.env.NEXT_PUBLIC_SPEECH_LANG || "en-US";
