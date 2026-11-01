# Amaan (أمان) — Al Rajhi Takaful's AI voice assistant · proof of concept (Saudi Arabia)

**The app is Al Rajhi Takaful's own voice-first assistant for individual customers.** It speaks for the company ("our plans", "we'll settle your claim"), uses Takaful wording (contribution, participant, certificate), greets in Arabic style ("Ahlan wa sahlan!"), keeps replies short because they are read aloud, and sells **individual plans in five portfolios**: Motor, Health, Life, Retirement & Savings and General (home). Prices are in **SAR**.

> This is a proof of concept. Plans, prices, rules, Nafath/Yakeen/Elm checks and payments are **simulated mock data**, not Al Rajhi Takaful's real products or systems.

| Layer | Stack |
|---|---|
| Frontend | Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui · Framer Motion · Lucide · PWA |
| Backend | FastAPI · Python 3.12+ |
| AI | Gemini 2.5 Flash · LangGraph (tool-calling agent + memory) · `langchain-google-genai` / `google-genai` |
| Data | **Customer 360 in Excel** (`data/art_customer_360.xlsx`) · SQLite (`data/art_ksa.db`) |
| RAG | ChromaDB + Google embeddings (`gemini-embedding-001`) with citations |
| Voice | Browser `SpeechRecognition` for listening · **neural voice** (Microsoft neural voices via `edge-tts`, no Azure account) for speaking, with automatic fallback to the browser's own voice |
| Look & feel | Al Rajhi Takaful theme: navy `#22447D` and sky blue `#009ADE` from the logo, Poppins/Tajawal type, light layout with the Individual/Business strip |

## Highlights

- **Amaan (أمان)** — the assistant has its own name ("Ahlan wa sahlan! I'm Amaan…"). Change it with `ASSISTANT_NAME` / `NEXT_PUBLIC_ASSISTANT_NAME`.
- **Retirement Plan journey**, modelled on how private pension plans are sold. One question per message:
  - retirement age (55–65)
  - monthly contribution (from SAR 1,000)
  - payment frequency (monthly / quarterly / half-yearly / yearly)
  - fund (Conservative / Balanced / Growth)
  - beneficiary
  - FATCA / PEP declarations
  - source of funds

  The quote shows the contribution and income periods, the instalment, the projected fund at 3 growth rates, the **projected monthly retirement income**, Takaful protection and a fund comparison.
- **Live "adjust your cover" controls** on every quote card. Each change re-prices in about a second; checkout always uses the latest price.

  | Portfolio | Controls |
  |---|---|
  | Motor | vehicle value insured ±20%, deductible |
  | Health | co-pay, maternity |
  | Life | sum covered, term |
  | Retirement | monthly contribution, retirement age, income years, fund, critical-illness add-on |
  | Savings | monthly contribution, years |
  | General | building and contents values |
- **Enterprise round trips in "What's happening".** Every quote, re-price, purchase, claim and renewal shows simulated calls with timings: **ESKA** (customer context), **Neutrinos** (rating engine), **iFoundry** (product rules, certificate, claims) and the **Payment Engine** (instalments, collection). Rename them with `SYSTEM_CRM` / `SYSTEM_RATING` / `SYSTEM_CORE` / `SYSTEM_PAYMENTS`.
- **Arabic.** Use the EN | عربي switch in the chat header (or simply write in Arabic):
  - Amaan listens in `ar-SA`, understands Arabic answers and digits, and replies in Arabic.
  - Replies are spoken by an Arabic neural voice.
  - Quote cards stay in English.

  Sentences to try:
  - السلام عليكم
  - أبغى خطة تقاعد
  - 0551234567 *(verifies Faisal)*
  - 60 → 3000 → شهري → متوازن → مها زوجتي → لا → الراتب
  - نعم → مدى
  - أبغى تأمين سيارة
  - عندي حادث

## How a conversation goes

Every new-plan conversation follows the same order:

1. **Which portfolio?** Motor, Health, Life, Retirement & Savings or General (home).
2. **Who are you?** One question per message:
   - full name
   - National ID (citizens, starts with 1) or Iqama (residents, starts with 2); sharing it is the consent for the Nafath request
   - **motor only:** the plate (e.g. `7788 BDR`) or Istimara sequence number
3. **Simulated government lookups** stream live in the "What's happening" panel: Nafath → Yakeen (Elm) → National Address (SPL) → Elm vehicle record.
   - The Copilot asks "Is that you?"; on yes, the customer is added to `art_customer_360.xlsx`.
   - A National ID that is already registered links the chat to the existing customer.
   - Existing customers can give their registered mobile instead (`05XXXXXXXX`).
4. **Only what the government data can't tell us.** Age comes from the date of birth, the city from the National Address and the vehicle from Elm, so the Copilot only asks:

   | Portfolio | Questions |
   |---|---|
   | Motor | which plan |
   | Health | any chronic condition |
   | Life | smoker? then confirms the suggested cover and term |
   | Retirement & Savings | goal, then confirms the suggested monthly amount |
   | General | apartment or villa, rebuild value, contents value |
5. **Quote → checkout → payment.** Payment by mada / Apple Pay / STC Pay / card / SADAD (simulated).
   - The Takaful certificate is issued and recorded in the Policies and Payments sheets.
   - A printable certificate is generated.

Other journeys: "What plans do I have?", "I had an accident" (Najm reminder), claim status, renewal (No Claim Discount), and coverage questions answered from the knowledge base with citations.

**Staff console** (`/console`, not linked from the customer app): Customer 360 from Excel, claims back office, a quote workbench for all five portfolios, and knowledge-base admin.

Architecture details: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## 0. Gemini on Vertex AI (your Google Cloud project, Flex PayGo)

By default the backend now calls Gemini through **Vertex AI in your GCP project**, the same way as your sample script, instead of an AI Studio API key:
- same endpoint: `aiplatform.googleapis.com … publishers/google/models/<model>:generateContent`
- same login: `gcloud auth print-access-token`
- same Flex header: `X-Vertex-AI-LLM-Shared-Request-Type: flex`

Settings in **backend/.env**:

```
LLM_PROVIDER=vertex
VERTEX_PROJECT=art-uat-genai-h-claims-0
VERTEX_LOCATION=global
VERTEX_MODEL=gemini-3.5-flash-lite
VERTEX_FLEX=true          # false = standard pay-as-you-go (faster, full price)
VERTEX_AUTH=gcloud        # adc = Application Default Credentials / service account (Cloud Run)
VERTEX_TIMEOUT=120        # after this many seconds the turn is answered by the offline agent
```

One-time setup on the laptop:
1. Install the Google Cloud CLI.
2. Run `gcloud auth login` with an account that has **Vertex AI User** on the project.

The backend refreshes the token itself every ~50 minutes.

To check the connection, run `cd backend` then `python scripts/check_vertex.py`. It sends one prompt and prints the reply and the time it took. Then start the backend as usual. `/api/health` shows `"llm_provider": "vertex"`, and the What's happening panel shows `gemini-3.5-flash-lite · Vertex AI Flex`.

Notes:
- **Flex is best-effort.** Replies can be slower, and requests may be refused when capacity is short. If a turn fails or takes longer than `VERTEX_TIMEOUT`, the offline agent answers that turn, so the demo never stalls.
- **For live demos, consider `VERTEX_FLEX=false`** if replies feel slow.
- **To go back to an AI Studio key:** set `LLM_PROVIDER=gemini_api` and `GEMINI_API_KEY=…`.
- **Knowledge search** tries Vertex embeddings (`VERTEX_EMBEDDING_MODEL`, default `gemini-embedding-001`) and falls back to keyword search if they aren't enabled in the project.

## 1. Quick start

**Prerequisites:** Python 3.12+, Node.js 20+, Chrome / Edge / Safari for voice.

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # includes edge-tts for the neural voice
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install                          # Windows PowerShell: npm.cmd install
cp .env.example .env.local
npm run dev                          # http://localhost:3000
```

> **No Gemini key, or no credit?** The app runs on the **offline demo agent**: same tools, same cards, same journeys.

> **Upgrading from the earlier ART build?** Delete `backend/data/` before starting, so the new individual-plan demo data (including a Retirement Plan) is seeded.

---

## 1b. Deploy to Google Cloud

Cloud Run in me-central2 (Dammam), one command from Cloud Shell: `bash deploy/gcp/deploy.sh`. Full steps, costs and troubleshooting: **[deploy/gcp/DEPLOY_GCP.md](deploy/gcp/DEPLOY_GCP.md)**.

---

## 2. Portfolios (individual plans only)

| Portfolio | Plans | VAT | Online underwriting |
|---|---|---|---|
| **Motor** (private car, SUV, EV, motorcycle) | Motor TPL · Motor Comprehensive · Motor Comprehensive Plus | 15% | agency repair only for vehicles ≤ 5 years |
| **Health** (one person, 18–75) | Health Essential · Health Gold · Health Premier | 15% | age > 65 → medical declaration review |
| **Life** (protection) | Life Protect · Life Protect Plus · Life Premier | exempt | age > 55 or cover > SAR 3M → medical exam |
| **Retirement & Savings** | Retirement Plan (18–55 at entry, retire 55–65, from SAR 1,000/month, income 5–20 years) · Savings Plan · Education Plan (from SAR 300/month) | exempt | > SAR 10,000 a month → source-of-funds check; PEP → enhanced due diligence; US person → W-9 (FATCA) |
| **General** (home & property) | Home Basic · Home Plus · Home Premier | 15% | building > SAR 10M → survey |

Notes:
- **Retirement & Savings quotes** show illustrative fund values at 3% / 5% / 7% a year after fees, labelled "not guaranteed".
- **Not offered here:** family, group, business and commercial-vehicle cover. The Copilot explains that this chat covers individual plans.
- **Other underwriting:** an expired Iqama is refused, with a pointer to Absher.

## 3. Voice — natural English & Saudi Arabic (speaking and listening)

Voice uses the same Google Cloud project and `gcloud` login as Vertex AI.

**Speaking (`/api/tts`).** Tried in this order:
1. **Google Cloud Text-to-Speech, Chirp 3 HD voices.** The most human-sounding voices:
   - English: `en-US-Chirp3-HD-Aoede`
   - Arabic: `ar-XA-Chirp3-HD-Aoede`
   - Other personas: female Kore, Leda, Zephyr…; male Charon, Puck, Orus…
2. **Microsoft neural voices** through edge-tts.
3. **The browser's own voice.**

Arabic replies are spoken by the Arabic voice automatically.

**Listening (`/api/stt`).**
- When server recognition is on, the mic records a short clip and stops by itself after about 1.2 s of silence.
- The clip is transcribed by **Google Cloud Speech-to-Text**: Chirp 3 in the EU region first, then the "short" model in the global region. Both cover English (`en-US`) and Saudi Arabic (`ar-SA`).
- If neither works, the app falls back to the browser's recogniser. Chrome and Edge also support `ar-SA`.

**One-time setup** in project `art-uat-genai-h-claims-0`:
1. Enable **Cloud Text-to-Speech API** and **Cloud Speech-to-Text API** (APIs & Services → Library).
2. Your account needs permission to use them, for example Editor, or the Cloud Speech / Text-to-Speech user roles.

`GET /api/voice` shows which engines are active. If an API isn't enabled, the app logs it once and quietly uses the next option.

**Settings** (`backend/.env`): `TTS_PROVIDER`, `TTS_GOOGLE_VOICE_EN`, `TTS_GOOGLE_VOICE_AR`, `TTS_GOOGLE_RATE`, `STT_PROVIDER` (`google` | `browser`), `STT_MODELS`.

**Microphone:** it needs `https://` or `localhost`. On phones use `ngrok http 3000`.

## 4. Environment variables

**backend/.env**

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | Google AI Studio key. Empty → offline demo agent |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Chat / tool-calling model |
| `INSURER_NAME` / `INSURER_SHORT` | `Al Rajhi Takaful` | Name used by the AI, documents and certificates |
| `TTS_PROVIDER` | `edge` | `edge` = neural voice; `off` = browser voice only |
| `TTS_VOICE_EN` / `TTS_VOICE_AR` | `en-US-AvaMultilingualNeural` / `ar-SA-ZariyahNeural` | Neural voices (e.g. `en-US-AndrewMultilingualNeural`, `ar-SA-HamedNeural`) |
| `TTS_RATE` | `+4%` | Speaking speed |
| `TTS_PROXY` | *(HTTPS_PROXY)* | Proxy for the voice service on corporate networks |
| `DATA_DIR` | `./data` | SQLite, Excel, Chroma store, uploads |
| `STATE_BUCKET` | *(empty)* | Cloud Run: Cloud Storage bucket that keeps the demo data between restarts (set by deploy.sh) |
| `CUSTOMER_360_XLSX` | `DATA_DIR/art_customer_360.xlsx` | Customer 360 workbook |

**frontend/.env.local**

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8000` | Where `/api/*` is proxied |
| `NEXT_PUBLIC_API_BASE` | *(empty)* | Force the browser to call FastAPI directly. Not normally needed: the app switches to calling port 8000 directly if the proxy fails |
| `NEXT_PUBLIC_INSURER_NAME` / `NEXT_PUBLIC_INSURER_SHORT` | `Al Rajhi Takaful` | Brand in the UI |
| `NEXT_PUBLIC_INSURER_NAME_AR` | `تكافل الراجحي` | Arabic name in the logo lock-up |
| `NEXT_PUBLIC_LOGO_SRC` | `/brand/logo-mark.png` | Logo mark (replace the file in `frontend/public/brand/` to update it) |
| `NEXT_PUBLIC_SPEECH_LANG` | `en-US` | `ar-SA` for Arabic listening and speaking |

---

## 5. Demo script

| # | Say / do | What you see |
|---|---|---|
| 1 | Open http://localhost:3000 | Al Rajhi Takaful-style home with five portfolio cards |
| 2 | Open the chat → "hi" | "Ahlan wa sahlan! … Which plan are you looking for?" |
| 3 | "Motor" → "Abdullah Al-Qahtani" → "1012345678" → "7788 BDR" | Nafath → Yakeen → National Address → Elm stream live → "Yakeen shows Abdullah Mohammed Al-Qahtani … Toyota Camry GLE 2022. Is that you?" |
| 4 | "Yes" → "your suggestion" | Registered in Excel → straight to the plan → motor quote |
| 5 | "Yes" → "mada" | "Mabrook!" + certificate POL-MTR-… |
| 6 | New chat → "Retirement & Savings" → "Anil Mathew" → "2234567890" → "yes" → "2000 a month" | Retirement Plan to age 60 with 3/5/7% projection bars → buy with STC Pay |
| 7 | New chat → "Life insurance" → "0551234567" | "Ahlan, Faisal!" → smoker? → suggested SAR 1.5M for 20 years → quote |
| 8 | "I had an accident" → when / where / what | Asks which car (Land Cruiser / Elantra) → claim ID + Najm reminder |
| 9 | "Renew my policy" → "yes" | Elantra renewal, No Claim Discount 25% → 30% |
| 10 | "Health insurance for my family" | Explains plans are individual → continues for the customer |
| 11 | "Is sandstorm damage covered?" | Short cited answer |

**Demo data** (government data is simulated):

| Who | Identify with | Notes |
|---|---|---|
| Faisal Abdullah Al-Otaibi · CUST-1001 · Riyadh | `0551234567` | 2 cars, Health Gold, Life Protect Plus, Retirement Plan |
| Sara Khalid Al-Harbi · CUST-1002 · Jeddah | `0509876543` | Motor + Health |
| Imran Ahmed Siddiqui · CUST-1003 · Dammam | `0562223344` | Iqama expired → purchases refused |
| New: Abdullah Mohammed Al-Qahtani | National ID `1012345678` | Saudi, Riyadh |
| New: Anil Joseph Mathew | Iqama `2234567890` | Resident, Jeddah |
| Vehicles | `7788 BDR` (Camry 2022), `4521 RTA` (Land Cruiser 2023) | any other plate gets a generated vehicle |

Any other valid National ID / Iqama produces a synthetic person who takes the name the customer gave.

---

## 6. Project layout

```
backend/app/
  agents/      graph.py (LangGraph) · prompts.py (Amaan persona, flow, brevity) · offline_agent.py · arabic.py (Arabic in/out)
  tools/       insurance_tools.py — 16 tools incl. lookup_vehicle and generate_savings_quote
  services/    products · quote_engine (motor) · health_engine (individual) · life_engine · savings_engine ·
               home_engine (general) · identity_service (Nafath/Yakeen/SPL/Elm, simulated) · purchase_service ·
               tts_service (neural voice) · systems (ESKA/Neutrinos/iFoundry/Payment Engine steps) ·
               reprice_service (live slider re-pricing, SSE) · excel_store · insurance_service …
  rag/documents/  incl. retirement_savings_guide.md
backend/tests/test_demo_flows.py   18 end-to-end flows (offline), incl. retirement, re-pricing and Arabic
frontend/public/brand/logo-mark.png  Al Rajhi Takaful logo mark
frontend/src/  app/ · features/ · hooks/use-speech-synthesis.ts (neural voice + fallback) · lib/brand.ts
```

## 7. Useful API calls

```bash
curl localhost:8000/api/health
curl -X POST localhost:8000/api/quotes/savings -H 'content-type: application/json' \
     -d '{"customer_id":"CUST-1001","plan":"retirement_plan","params":{"age":35,"monthly_contribution":1500}}'
curl -X POST localhost:8000/api/quotes/health -H 'content-type: application/json' \
     -d '{"customer_id":"CUST-1001","params":{"age":40,"city":"Riyadh"}}'
curl -X POST localhost:8000/api/tts -H 'content-type: application/json' -d '{"text":"Ahlan wa sahlan!"}' -o hello.mp3
```

Tests: `cd backend && pip install pytest && python -m pytest -q`

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `uvicorn` not recognised (Windows) | `python -m uvicorn app.main:app --port 8000` |
| `npm.ps1 cannot be loaded` | Use `npm.cmd …` |
| *Backend not reachable* while uvicorn runs | Restart uvicorn after updating; the app falls back to calling port 8000 directly |
| Voice still sounds robotic | The neural voice couldn't be reached (see uvicorn log "Neural TTS unavailable"). Allow `speech.platform.bing.com`, set `TTS_PROXY`, or use Microsoft Edge for its built-in natural voices |
| `402 Payment Required` from Gemini | No credit on the Gemini project — the offline agent answers meanwhile |
| Old ART / family-health data showing | Delete `backend/data/` and restart |
| Excel changes not saving | Close `art_customer_360.xlsx`; use *Sync* in the console |

Rotate the Gemini key after the demo and never commit `backend/.env`.
