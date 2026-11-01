import type {
  ChatResponse, Claim, ConsoleOverview, Customer360, Health, Identity, KnowledgeAnswer, KnowledgeSource, Policy,
  QuoteResult, QuoteRow, RecentInteraction, RenewalResult, RunEvent,
} from "@/types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Optional: call FastAPI directly (e.g. http://127.0.0.1:8000) instead of via the Next.js /api proxy. */
const BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/$/, "");
const UNREACHABLE = "The Copilot backend is not reachable. Is FastAPI (uvicorn) running on port 8000?";

/** Set once the Next.js /api proxy has failed and FastAPI answered directly on :8000. */
let directBase: string | null = null;

/**
 * fetch() for /api calls. Normally goes through the Next.js proxy (same origin). If the proxy itself
 * can't reach FastAPI (network error, or a non-JSON 5xx from Next), retry once straight against
 * FastAPI on port 8000 of the same host and stick with that for the rest of the session.
 */
async function apiFetch(url: string, init: RequestInit): Promise<Response> {
  if (!BASE && directBase && url.startsWith("/api")) url = directBase + url;
  let res: Response | null = null;
  try {
    res = await fetch(url, init);
  } catch {
    res = null;
  }
  const proxyFailed = !res || (res.status >= 500 && !(res.headers.get("content-type") || "").includes("json"));
  const localHost = typeof window !== "undefined" &&
    /^(localhost|127\.0\.0\.1|\[::1\]|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(window.location.hostname);
  if (!BASE && !directBase && url.startsWith("/api") && proxyFailed && localHost) { // local dev only (not on Cloud Run)
    const d = `${window.location.protocol}//${window.location.hostname}:8000`;
    try {
      const r2 = await fetch(d + url, init);
      directBase = d;
      console.info(`[copilot] Next.js /api proxy failed — talking to FastAPI directly at ${d}`);
      return r2;
    } catch {
      /* fall through */
    }
  }
  if (!res) throw new ApiError(0, UNREACHABLE);
  return res;
}

async function sse(url: string, body: unknown, onEvent: (e: RunEvent) => void): Promise<void> {
  const res = await apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, await failure(res));
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const data = frame.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("");
      if (data) onEvent(JSON.parse(data) as RunEvent);
    }
  }
}

/** Absolute-or-relative URL for links/downloads (follows the direct-to-FastAPI fallback when it's active). */
export function apiHref(path: string): string {
  return (BASE || directBase || "") + path;
}

/** Turn a failed /api response into a message that says *where* it failed. */
async function failure(res: Response): Promise<string> {
  let text = "";
  try { text = await res.text(); } catch { /* ignore */ }
  try {
    const b = JSON.parse(text);
    if (typeof b.detail === "string") return b.detail;
    if (b.detail) return JSON.stringify(b.detail);
  } catch { /* not JSON */ }
  if (res.status >= 500) {
    // Next's proxy answers 500 with a plain body when FastAPI can't be reached; FastAPI's own crash also says so.
    return `Backend error (HTTP ${res.status}) — check the uvicorn terminal for a traceback. ${text.slice(0, 120)}`.trim();
  }
  return `Request failed (HTTP ${res.status}) ${text.slice(0, 120)}`.trim();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const res = await apiFetch(path, {
    ...init,
    headers: isForm ? init?.headers : { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new ApiError(res.status, await failure(res));
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const q = (customerId: string) => `customer_id=${encodeURIComponent(customerId)}`;

/* ------------------------------------------------------------------ customer-facing (chat only)
   The browser never says who the customer is: the backend decides, per chat session,
   after identification (existing customer) or KYC onboarding (new customer). */
export const api = {
  health: () => request<Health>(BASE + "/api/health"),

  /** Server speech-to-text (Google Cloud Chirp). Throws if unavailable — caller falls back to the browser. */
  stt: async (audio: Blob, lang: string): Promise<{ text: string; engine?: string | null }> => {
    const fd = new FormData();
    fd.append("audio", audio, "speech.webm");
    const res = await apiFetch(BASE + `/api/stt?lang=${lang}`, { method: "POST", body: fd, cache: "no-store" });
    if (!res.ok) throw new ApiError(res.status, "stt unavailable");
    return res.json();
  },

  /** Neural voice (MP3). Throws if the backend can't reach the speech service — caller falls back to the browser. */
  tts: async (text: string, lang?: string): Promise<Blob> => {
    const res = await apiFetch(BASE + "/api/tts", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang }), cache: "no-store",
    });
    if (!res.ok || !(res.headers.get("content-type") || "").includes("audio")) throw new ApiError(res.status, "tts unavailable");
    return res.blob();
  },

  chat: (message: string, session_id?: string) => request<ChatResponse>(BASE + "/api/chat", json({ message, session_id })),

  /** POST /api/chat/stream — Server-Sent Events with live agent progress, then the final reply. */
  chatStream: (message: string, session_id: string | undefined, onEvent: (e: RunEvent) => void, lang?: string) =>
    sse(BASE + "/api/chat/stream", { message, session_id, lang }, onEvent),

  /** Re-price a quote after a slider / toggle change — streams the engine round trip like a chat turn. */
  repriceStream: (quoteId: string, changes: Record<string, unknown>, session_id: string | undefined,
    onEvent: (e: RunEvent) => void) =>
    sse(BASE + `/api/quotes/${quoteId}/reprice/stream`, { changes, session_id }, onEvent),

  identity: (session_id: string) => request<Identity>(BASE + `/api/chat/${session_id}/identity`),
  resetChat: (session_id: string) => request<{ ok: boolean }>(BASE + `/api/chat/${session_id}`, { method: "DELETE" }),
};

/* ------------------------------------------------------------------ staff console (customer chosen explicitly) */
export const consoleApi = {
  overview: () => request<ConsoleOverview>(BASE + "/api/console/overview"),
  workbookUrl: BASE + "/api/console/customer-360.xlsx",
  syncWorkbook: () => request<{ synced: boolean; warning?: string }>(BASE + "/api/console/excel/sync", { method: "POST" }),
  recent: (customerId: string) => request<RecentInteraction[]>(BASE + `/api/interactions/recent?${q(customerId)}`),

  customer360: (customerId: string) => request<Customer360>(BASE + `/api/customers/${customerId}/360`),
  policies: (customerId: string) => request<Policy[]>(BASE + `/api/policies?${q(customerId)}`),
  renewalQuote: (policyId: string) => request<RenewalResult>(BASE + `/api/policies/${policyId}/renewal-quote`),
  renew: (customerId: string, policyId: string, confirm: boolean) =>
    request<RenewalResult>(BASE + `/api/policies/${policyId}/renew`, json({ confirm, customer_id: customerId })),

  createQuote: (customerId: string, body: { vehicle_type: string; vehicle_age: number; coverage: string; location: string; ncb_percent?: number }) =>
    request<QuoteResult>(BASE + "/api/quotes", json({ ...body, customer_id: customerId })),
  createLineQuote: (customerId: string, line: "motor" | "health" | "life" | "savings" | "general", params: Record<string, unknown>, plan?: string) =>
    request<QuoteResult>(BASE + `/api/quotes/${line}`, json({ customer_id: customerId, params, plan })),
  quotes: (customerId: string) => request<QuoteRow[]>(BASE + `/api/quotes?${q(customerId)}`),

  createClaim: (customerId: string, body: {
    policy_id?: string; incident_date?: string; incident_type?: string; description: string;
    location?: string; estimated_amount?: number;
  }) => request<Claim>(BASE + "/api/claims", json({ ...body, customer_id: customerId })),
  claims: (customerId: string) => request<Claim[]>(BASE + `/api/claims?${q(customerId)}`),
  claim: (id: string) => request<Claim>(BASE + `/api/claims/${encodeURIComponent(id.trim().toUpperCase())}`),
  advanceClaim: (id: string) => request<Claim>(BASE + `/api/claims/${id}/advance`, { method: "POST" }),

  ask: (question: string) => request<KnowledgeAnswer>(BASE + "/api/knowledge/ask", json({ question })),
  sources: () => request<{ retrieval_mode: string; sources: KnowledgeSource[] }>(BASE + "/api/knowledge/sources"),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ source: string; chunks: number }>(BASE + "/api/knowledge/upload", { method: "POST", body: fd });
  },
};
