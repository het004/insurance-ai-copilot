export interface Customer {
  id: string;
  name: string;
  phone: string;
  email: string;
  address: string;
  city: string;
  date_of_birth: string;
  segment: string;
  kyc_status: string;
  customer_since: string;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  policy_type: string;
  product_name: string;
  insured_asset: string;
  sum_insured: number;
  premium: number;
  start_date: string;
  end_date: string;
  status: "Active" | "Expiring" | "Lapsed" | "Renewed" | string;
  ncb_percent: number;
  details: Record<string, unknown> | null;
  days_to_expiry: number;
  renewal_due: boolean;
}

export interface TimelineStep {
  status: string;
  completed: boolean;
  note: string | null;
  at: string | null;
}

export interface Claim {
  claim_id: string;
  customer_id: string;
  policy_id: string;
  incident_date: string;
  incident_type: string;
  description: string;
  location: string;
  estimated_amount: number | null;
  status: string;
  remarks: string | null;
  created_at: string;
  updated_at: string;
  timeline: TimelineStep[];
  next_steps: string[];
  progress: number;
  policy?: Pick<Policy, "policy_id" | "policy_type" | "product_name" | "insured_asset">;
}

export interface BreakdownLine { label: string; amount: number }

export interface QuoteResult {
  line?: "health" | "motor" | "life" | "savings" | "general" | "home";
  params?: Record<string, unknown>;
  subject?: string;
  sum_insured?: number;
  sum_insured_label?: string;
  breakdown?: BreakdownLine[];
  gst_note?: string;
  quote_id: string;
  customer_id: string;
  created_at: string;
  vehicle_type: string;
  vehicle_label: string;
  vehicle_age: number;
  location: string;
  zone: string;
  coverage: string;
  plan: string;
  plan_summary: string;
  coverage_details: { includes: string[]; excludes: string[] };
  premium: {
    idv: number;
    own_damage: number;
    ncb_discount: number;
    third_party: number;
    personal_accident: number;
    add_ons: number;
    net_premium: number;
    gst: number;
    total_premium: number;
    monthly?: number;
    instalment?: number;
    frequency?: string;
  };
  projection?: {
    years: number; total_contributions: number; low: number; mid: number; high: number; note: string;
    rates?: { low: number; mid: number; high: number };
    retirement_age?: number; income_years?: number; monthly_income?: { low: number; mid: number; high: number };
  };
  risk: { score: number; band: "Low" | "Medium" | "High"; factors: string[] };
  recommendation: { coverage: string; plan: string; reason: string };
  alternatives: { coverage: string; plan: string; total_premium: number; recommended: boolean; projected_value?: number; fund?: string }[];
  adjustables?: Adjustable[];
  retirement?: RetirementInfo;
  validity_days: number;
}

export interface QuoteRow {
  quote_id: string;
  customer_id: string;
  product: string;
  premium: number;
  coverage: string;
  risk_score: number | null;
  details: Partial<QuoteResult> & Record<string, unknown>;
  created_at: string;
}

export interface RenewalResult {
  status: "quote" | "renewed";
  policy: Policy;
  claims_this_term: number;
  current_premium: number;
  renewal_premium: number;
  change_percent: number;
  ncb_current: number;
  ncb_renewal: number;
  early_renewal_discount_percent: number;
  new_sum_insured: number;
  new_start_date: string;
  new_end_date: string;
  recommendation: string;
  add_on_tip: string;
  next_step: string;
  new_policy_id?: string;
  payment?: { amount: number; mode: string; reference: string };
}

export interface RecommendedAction {
  type: string;
  priority: "high" | "medium" | "low";
  title: string;
  detail: string;
  prompt: string;
}

export interface Customer360 {
  customer: Customer;
  summary: {
    active_policies: number;
    total_annual_premium: number;
    total_sum_insured: number;
    open_claims: number;
    renewals_due: number;
    quotes: number;
  };
  policies: Policy[];
  claims: Claim[];
  quotes: QuoteRow[];
  renewals: Policy[];
  recommended_actions: RecommendedAction[];
  conversations?: RecentInteraction[];
  payments?: PaymentRow[];
  excel?: ExcelStatus;
}

export interface Citation {
  ref: number;
  source: string;
  title: string;
  section: string;
  content: string;
  score: number;
  cited?: boolean | null;
}

export interface ToolUse {
  name: string;
  args: Record<string, unknown>;
  ok: boolean;
}

export type ChatCard =
  | { type: "quote"; data: QuoteResult }
  | { type: "profile"; data: Customer360 }
  | { type: "policies"; data: Policy[] | Policy }
  | { type: "claim"; data: Claim | Claim[] }
  | { type: "renewal"; data: RenewalResult }
  | { type: "identity"; data: IdentityResult }
  | { type: "kyc"; data: KycResult }
  | { type: "registered"; data: RegisteredResult }
  | { type: "purchase"; data: PurchaseResult }
  | { type: "vehicle"; data: { vehicle: VehicleInfo } };

export interface VehicleInfo {
  registration_number: string; make_model: string; model_year?: number; colour?: string; body?: string;
  registration_expiry?: string; vehicle_type?: string; vehicle_age?: number;
}

export interface ChatResponse {
  reply: string;
  session_id: string;
  tools_used: ToolUse[];
  cards: ChatCard[];
  citations: Citation[];
  mode: "gemini" | "offline" | "engine";
  notice?: string | null;
  identity?: Identity;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  tools?: ToolUse[];
  cards?: ChatCard[];
  citations?: Citation[];
  mode?: "gemini" | "offline" | "engine";
  notice?: string | null;
  error?: boolean;
  viaVoice?: boolean;
  runId?: string;
}

export interface KnowledgeAnswer {
  answer: string;
  sources: Citation[];
  mode: "gemini" | "offline" | "engine";
  retrieval: "vector" | "keyword";
}

export interface KnowledgeSource {
  source: string;
  title: string;
  chunks: number;
  uploaded: boolean;
}

export interface RecentInteraction {
  session_id: string;
  prompt: string;
  reply: string | null;
  tools: string[] | null;
  created_at: string;
}

export interface Health {
  status: string;
  agent_mode: "gemini" | "offline" | "engine";
  retrieval_mode: "vector" | "keyword";
  stt_server?: boolean;
  tts_providers?: string[];
  model: string | null;
  knowledge_chunks: number;
}

export type VoiceState = "idle" | "listening" | "processing" | "speaking";

/* ---------- Live agent progress ("What's happening" panel) ---------- */
export type RunEvent =
  | { type: "run_started"; run_id: string; session_id: string; mode: "gemini" | "offline" | "engine"; model: string; identity: Identity; ts: number; message?: string }
  | { type: "tool_progress"; tool_call_id: string; id: string; label: string; status: "running" | "done" | "error"; detail?: string | null; ts: number }
  | { type: "step"; id: string; kind: "think"; label: string; status: "running" | "done"; detail?: string | null; ts: number }
  | { type: "tool_call"; id: string; name: string; label: string; args: Record<string, unknown>; ts: number }
  | { type: "tool_result"; id: string; name: string; ok: boolean; summary: string; ts: number }
  | { type: "notice"; message: string; detail?: string; ts: number }
  | ({ type: "final"; run_id: string; duration_ms: number; ts: number; replaces_quote?: string } & ChatResponse)
  | { type: "error"; message: string };

export interface RunStep {
  id: string;
  kind: "think" | "tool" | "notice" | "sub";
  parentId?: string;
  label: string;
  name?: string;
  detail?: string | null;
  args?: Record<string, unknown>;
  status: "running" | "done" | "error";
  startedAt: number;
  endedAt?: number;
}

export interface AgentRun {
  id: string;
  prompt: string;
  status: "running" | "done" | "error";
  mode?: "gemini" | "offline" | "engine";
  model?: string;
  steps: RunStep[];
  startedAt: number;
  endedAt?: number;
  messageId?: string;
}

/* ---------- Identity, KYC onboarding, staff console ---------- */
export interface Identity {
  status: "guest" | "kyc_pending" | "verified";
  customer_id: string | null;
  customer_name: string | null;
  verified_via: string | null;
  verified_at: string | null;
  is_new_customer: boolean;
}

export interface CustomerCard {
  customer_id: string;
  name: string;
  phone_masked: string;
  city: string;
  segment: string;
  customer_since: string;
  active_policies: number;
  open_claims: number;
  verified_via: string;
}

export interface KycLookup { key: string; label: string; source: string; status: string; detail: string; ms: number }

export interface KycDraft {
  name: string;
  date_of_birth: string;
  gender?: string;
  address: string;
  city: string;
  phone: string;
  email: string;
  id_type: "National ID" | "Iqama" | string;
  nationality?: string;
  id_expiry?: string;
  id_reference: string;
  kyc_source: string;
  vehicle: null | { registration_number: string; make_model: string; model_year?: number; colour?: string; body?: string; registration_expiry?: string };
  fetched_at: string;
  lookups: KycLookup[];
  customer_corrections?: string[];
}

export interface IdentityResult { found: boolean; customer?: CustomerCard; identifier?: string; message?: string }
export interface KycResult { draft?: KycDraft; already_registered?: boolean; customer?: CustomerCard; simulated?: boolean }
export interface RegisteredResult {
  registered: boolean;
  customer?: CustomerCard;
  draft?: KycDraft;
  vehicle?: KycDraft["vehicle"];
  excel?: { synced: boolean; warning?: string | null; file: string };
  message?: string;
}

export interface ConsoleCustomer extends Customer {
  customer_id: string;
  id_type: string;
  id_reference: string;
  kyc_source: string;
  onboarded_via: string;
  registered_at: string;
}

export interface ExcelStatus {
  path: string;
  exists: boolean;
  pending_sync: boolean;
  last_error: string | null;
  last_synced_at: string | null;
  customers: number;
}

export interface ConsoleOverview {
  customers: ConsoleCustomer[];
  active_sessions: (Identity & { session_id: string })[];
  excel: ExcelStatus;
}

/* ---------- Policy purchase (checkout) ---------- */
export interface PurchaseResult {
  status: "review" | "issued";
  retirement?: RetirementInfo | null;
  projection?: QuoteResult["projection"] | null;
  line: "health" | "motor" | "life" | "savings" | "general" | "home";
  line_label: string;
  subject: string;
  sum_insured: number;
  sum_insured_label: string;
  breakdown: BreakdownLine[];
  gst_note?: string;
  notes: string[];
  quote_id: string;
  plan: string;
  coverage: string;
  plan_summary: string;
  vehicle_type: string;
  vehicle_label: string;
  vehicle_age: number;
  location: string;
  insured_asset: string;
  registration_number: string | null;
  premium: QuoteResult["premium"];
  total_premium: number;
  idv: number;
  includes: string[];
  start_date: string;
  end_date: string;
  alternatives: QuoteResult["alternatives"];
  recommendation: QuoteResult["recommendation"];
  customer: { customer_id: string; name: string };
  payment_methods: string[];
  underwriting: { accepted: boolean; issues: string[] };
  policy_id?: string;
  proposal_no?: string;
  payment?: { payment_id: string; amount: number; method: string; status: string; bank_reference: string; gateway: string; paid_at: string };
  document_url?: string;
  excel?: { synced: boolean; warning?: string | null; file: string };
}

export interface PaymentRow {
  payment_id: string;
  customer_id: string;
  policy_id: string;
  quote_id: string;
  amount: number;
  method: string;
  status: string;
  reference: string;
  gateway: string;
  created_at: string;
}

export interface Adjustable {
  key: string;
  label: string;
  type: "range" | "select" | "toggle";
  value: number | string | boolean;
  min?: number; max?: number; step?: number; unit?: string; hint?: string | null;
  options?: { value: number | string; label: string }[];
}

export interface RetirementInfo {
  contribution_period: string; income_period: string; fund: string; fund_risk: string; frequency: string;
  instalment: string; protection: number; ci_rider: boolean; beneficiary?: string | null;
  declarations?: { us_person?: boolean; pep?: boolean; source_of_funds?: string } | null;
}
