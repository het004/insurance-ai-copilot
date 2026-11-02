"""Offline demo agent — used when GEMINI_API_KEY is absent or Gemini errors.

A small slot-filling state machine that calls the SAME tools as Gemini, so every demo journey works (with the
same cards) without network access. Replies are deliberately SHORT — they are read aloud, and the cards carry
the details.

New-plan journey (always in this order):
  portfolio → full name → National ID / Iqama → plate (motor only) → Nafath + Yakeen fetch → "Is that you?"
  → only the questions government data can't answer → quote → checkout → payment.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.agents import arabic
from app.config import settings
from app.services import identity_service, insurance_service, life_engine, products, purchase_service, quote_engine
from app.services import savings_engine
from app.services.progress import emit_event
from app.services.session_store import session_store
from app.services.tool_events import tool_call_event, tool_result_event
from app.tools.insurance_tools import (confirm_registration, create_claim, fetch_kyc_from_government,
                                       generate_general_quote, generate_health_quote, generate_life_quote,
                                       generate_quote, generate_savings_quote, get_customer_profile,
                                       get_policy_details, identify_customer, knowledge_search, lookup_vehicle,
                                       purchase_policy, renew_policy, track_claim)

PERSONAL_INTENTS = {"policies", "profile", "claim", "track", "renew", "buy"}
BUY_RE = re.compile(r"\b(buy|purchase|checkout|check out|pay|go with|take (this|the|that|it)|i'?ll take|proceed with)\b")
NO_RE = re.compile(r"\b(no|not now|later|cancel|don'?t)\b")
YES_RE = re.compile(r"\b(yes|yeah|yep|yup|correct|right|confirm|confirmed|looks good|all good|that'?s me|it'?s me|"
                    r"proceed|go ahead|sure|ok|okay|naam|aywa|tamam|fine|sounds good)\b")

HEALTH_RE = re.compile(r"\b(health|medical|hospital(isation|ization)? cover|health essential|health gold|health premier|"
                       r"(medical|health) (cover|insurance|policy|plan))\b")
LIFE_RE = re.compile(r"\b(life|term (insurance|plan|life|cover)|death benefit|life protect|life premier|protection plan)\b")
SAVINGS_RE = re.compile(r"\b(retire(ment)?|pension|savings?|save money|saving plan|investment|invest|education plan|"
                        r"university fund|child'?s education)\b")
GENERAL_RE = re.compile(r"\b(general|home|house|household|property|flat|apartment|villa|home basic|home plus|home premier)\b")
MOTOR_RE = re.compile(r"\b(motor|vehicle|car|suv|bike|motorcycle|ev|electric car|tpl|third[- ]party|comprehensive|"
                      r"land cruiser|camry)\b")
UNSUPPORTED_RE = re.compile(r"\b(travel insurance|pet insurance|marine|malpractice|sme|business insurance|group (health|"
                            r"medical|insurance)|my (employees|staff|company)|commercial (vehicle|property)|truck|fleet|"
                            r"domestic (helper|worker) insurance)\b")
FAMILY_RE = re.compile(r"\b(family|my (wife|husband|kids|children|parents|mother|father)|for (us|all of us))\b")
KNOW_RE = re.compile(r"\b(what does|what is|what'?s covered|does (it|my|the|this)\b.*\bcover|is .* covered|covered\?|"
                     r"exclu|how do(es)?|explain|difference between|tell me about)\b")
CONTENT_WORDS = re.compile(r"content|belonging|furniture|stuff|valuable|electronic|appliance|jewel|things|inside")
PHONE_RE = re.compile(r"(?:\+?966[\s-]?|\b0)5\d(?:[\s-]?\d){7}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
SAUDI_ID_IN_TEXT = re.compile(r"\b[12]\d{9}\b")  # National ID (1…) or Iqama (2…)
NAME_STOP = {"my", "name", "is", "i", "am", "im", "i'm", "it's", "its", "this", "here", "hi", "hello", "salam", "and",
             "the", "full", "call", "me", "yes", "sure", "ok", "okay", "mr", "mrs", "ms", "dr", "اسمي", "انا", "أنا",
             "معك", "هنا"}
CITIES = sorted(set(quote_engine.CITIES), key=len, reverse=True)

GREETING = "Ahlan wa sahlan!"
PORTFOLIOS = "**Health**, **Motor**, **Life**, **Retirement & Savings** or **General** (home)"
PAY_METHODS = "mada, Apple Pay, STC Pay, card or SADAD"


def _line_in_text(t: str) -> str | None:
    """Which portfolio the customer is talking about."""
    if SAVINGS_RE.search(t):
        return "savings"
    if LIFE_RE.search(t) and not re.search(r"\blife ?style\b", t):
        return "life"
    if HEALTH_RE.search(t):
        return "health"
    if GENERAL_RE.search(t):
        return "general"
    if MOTOR_RE.search(t) or quote_engine.normalize_vehicle(t):
        return "motor"
    return None


def _plan_in_text(t: str, line: str | None = "motor") -> str | None:
    t = re.sub(r"\b(premiums?|contributions?)\b", " ", t)
    if line in ("health", "general", "home", "life", "savings"):
        return products.normalize_plan(line, t)
    hits = []
    for rx, cov in ((r"comprehensive plus|agency repair|\bagency\b|\bplus\b", "comprehensive_plus"),
                    (r"comprehensive(?! plus)", "comprehensive"), (r"\btpl\b|third[\s-]?party", "tpl")):
        if m := re.search(rx, t):
            hits.append((m.start(), cov))
    return min(hits)[1] if hits else None


def _money(t: str) -> list[tuple[float, int, int]]:
    """SAR amounts → [(riyals, start, end)]; '1.5 million', '800k', 'SAR 650,000', '200,000 riyals', '2m'."""
    out, taken = [], []
    for m in re.finditer(r"(?:sar|sr)?\s*(\d+(?:\.\d+)?)\s*(million|mn|m\b|k\b|thousand)", t):
        mult = 1_000_000 if m.group(2) in ("million", "mn", "m") else 1_000
        out.append((float(m.group(1)) * mult, m.start(), m.end()))
        taken.append((m.start(), m.end()))
    for m in re.finditer(r"(?:(?:sar|sr|riyals?)\s*)?(\d{1,3}(?:,\d{3})+|\d{3,})(?:\s*(?:sar|sr|riyals?))?", t):
        raw = m.group(1).replace(",", "")
        if any(a <= m.start() < b for a, b in taken) or re.fullmatch(r"0?5\d{8}|[12]\d{9}|\d{9}", raw):
            continue  # skip mobiles, IDs, sequence numbers
        out.append((float(raw), m.start(), m.end()))
    return sorted(out, key=lambda x: x[1])


def _years(t: str) -> int | None:
    m = re.search(r"(?:for|term(?: of)?|over)\s*(\d{1,2})\s*(?:years?|yrs?)|(\d{1,2})[- ]years?", t)
    return int(m.group(1) or m.group(2)) if m else None


def _parse_name(m: str) -> str | None:
    text = SAUDI_ID_IN_TEXT.sub(" ", m)
    text = re.split(r"[,.;]| and | my (?:id|iqama|national)", text, flags=re.I)[0]
    if mt := re.search(r"(?:name is|i'?m|i am|this is|it'?s|call me)\s+(.+)", text, re.I):
        text = mt.group(1)
    words = [w for w in re.findall(r"[A-Za-z؀-ۿ'-]+", text) if w.lower() not in NAME_STOP]
    if not words or len(words) > 6 or len("".join(words)) < 3:
        return None
    return " ".join(w if re.search(r"[؀-ۿ]", w) else w[0].upper() + w[1:] for w in words)


@dataclass
class Session:
    intent: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    pending: str | None = None  # request to resume once the customer is identified
    offer: str | None = None    # what the last reply offered (e.g. "buy" after a quote) so "yes" maps to it
    lang: str = "en"            # "ar" → replies are localised to Arabic


@dataclass
class TurnResult:
    reply: str
    calls: list[tuple[str, dict, str]] = field(default_factory=list)


def _has(t: str, *words: str) -> bool:
    return any(re.search(rf"\b{w}\b", t) for w in words)


def _parse_date(t: str) -> str | None:
    today = date.today()
    if "day before yesterday" in t:
        return (today - timedelta(days=2)).isoformat()
    if "yesterday" in t or "last night" in t:
        return (today - timedelta(days=1)).isoformat()
    if _has(t, "today", "just now", "this morning", "an hour ago", "this evening", "now"):
        return today.isoformat()
    m = re.search(r"(\d+)\s+days?\s+ago", t)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"\b(20\d\d-\d\d-\d\d)\b", t)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        y = int(m.group(3) or today.year)
        y = y + 2000 if y < 100 else y
        try:
            return date(y, int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def _parse_city(t: str) -> str | None:
    for c in CITIES:
        if re.search(rf"\b{re.escape(c)}\b", t):
            return c.title()
    return None


def _first(name: str | None) -> str:
    return (name or "").split()[0] if name else ""


class OfflineAgent:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self._n = 0

    def reset(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    def _call(self, res: TurnResult, tool, args: dict, cfg: dict) -> dict:
        """Invoke a tool exactly as LangGraph's ToolNode would, streaming events to the progress panel."""
        self._n += 1
        call_id = f"off-{self._n}"
        emit_event(tool_call_event(call_id, tool.name, args))
        msg = tool.invoke({"name": tool.name, "args": args, "id": call_id, "type": "tool_call"}, config=cfg)
        out = msg.content if hasattr(msg, "content") else msg
        emit_event(tool_result_event(call_id, tool.name, out))
        res.calls.append((tool.name, args, out))
        return json.loads(out)

    @staticmethod
    def _sid(cfg: dict) -> str:
        return cfg["configurable"]["thread_id"]

    # ------------------------------------------------------------------ main
    def chat(self, message: str, session_id: str, lang: str | None = None) -> TurnResult:
        s = self.sessions.setdefault(session_id, Session())
        if lang in ("ar", "en"):
            s.lang = lang
        elif arabic.is_arabic(message):
            s.lang = "ar"
        res = self._chat(arabic.digits(message), arabic.normalize(message), s, session_id)
        if s.lang == "ar":
            res.reply = arabic.localize(res.reply)
        return res

    def _chat(self, message: str, t: str, s: Session, session_id: str) -> TurnResult:
        cfg = {"configurable": {"thread_id": session_id}}
        res = TurnResult(reply="")

        if _has(t, "cancel", "stop", "never mind", "nevermind", "start over"):
            self.sessions[session_id] = Session(lang=s.lang)
            res.reply = "No problem, cleared. What would you like to do next?"
            return res

        intent = self._detect(t, s)
        if intent is None and s.intent in {"who", "identify"}:
            s.intent = None  # they asked something else; keep `pending` for later
        if intent != s.intent and intent is not None:
            s.intent, s.slots = intent, {}
        verified = bool(session_store.get(session_id).customer_id)
        if intent not in (None, "buy"):
            s.offer = None
        if s.intent == "buy" and not verified:  # buying always starts with the product journey (it verifies)
            ex = session_store.get(session_id).extra
            if not ex.get("last_quote_id"):
                s.intent, s.slots = "quote", {}
        if s.intent in PERSONAL_INTENTS and not verified:
            s.pending, s.intent, s.slots = message, "who", {}
            res.reply = (f"Sure. Are you already with {settings.INSURER_SHORT}? Share your registered mobile number, "
                         "or your National ID / Iqama.")
            return res
        handler = getattr(self, f"_h_{s.intent}", None) if s.intent else None
        if handler is None:
            return self._h_knowledge(t, message, s, res, cfg)
        return handler(t, message, s, res, cfg)

    def _resume(self, s: Session, res: TurnResult, session_id: str, prefix: str) -> TurnResult:
        """After identification, continue with what the customer originally asked."""
        pending, s.pending = s.pending, None
        if not pending:
            res.reply = prefix + " How can I help today?"
            return res
        nxt = self.chat(pending, session_id)
        res.calls.extend(nxt.calls)
        res.reply = prefix + " " + nxt.reply
        return res

    def _detect(self, t: str, s: Session) -> str | None:
        claimish = re.search(r"\b(accident|crash|theft|stolen|admitted|burglary|renew|track|status|claim)\b", t)
        # mid-journey answers stay in the journey (names, IDs, plates, "yes", amounts…)
        if s.intent == "quote" and s.slots.get("line") and not claimish:
            return "quote"
        if s.intent == "quote" and s.slots.get("asked") == "line" and (_line_in_text(t) or UNSUPPORTED_RE.search(t)
                                                                     or FAMILY_RE.search(t)):
            return "quote"
        if s.intent == "kyc_confirm":
            return s.intent
        if re.search(r"\b(i'?m|i am|am) new\b|new (customer|here|user)|first time|register me|sign me up|sign up|"
                     r"not (a|an existing) customer|don'?t have (a|any) (policy|plan)", t):
            return "onboard"
        if SAUDI_ID_IN_TEXT.search(t) and s.intent in {None, "who", "identify", "onboard"}:
            return "onboard"
        if re.search(r"existing customer|already (a|have|with)|i'?m registered|i am registered|"
                     r"my (registered )?(mobile|phone)", t) \
                or re.search(r"\bcust-\d+\b", t) or EMAIL_RE.search(t) \
                or (PHONE_RE.search(t) and s.intent in {None, "who", "identify"}) \
                or (re.search(r"\bpol-[a-z]+-\d+\b", t) and s.intent in {"who", "identify"}):
            return "identify"
        if s.intent in {"who", "identify"} and re.search(r"^(yes|yeah|yep|i am|i'?m)\b", t):
            return "identify"
        if KNOW_RE.search(t) and not re.search(r"\b(quote|price|cost|how much|buy|purchase|get me)\b", t):
            return None  # a coverage question → knowledge search
        if BUY_RE.search(t) or (s.offer == "buy" and YES_RE.search(t) and not NO_RE.search(t)):
            return "buy"
        if re.search(r"\bclm-\d{4}-\d{4}\b", t) or (_has(t, "status", "track", "progress", "update") and "claim" in t):
            return "track"
        if _has(t, "accident", "crash", "crashed", "collision", "collided", "stolen", "theft", "admitted", "hospitalised",
                "hospitalized", "burglary", "break-in") or re.search(r"\b(file|raise|make|register|report|new|lodge) (a )?claim\b", t):
            return "claim"
        if _has(t, "renew", "renewal", "expiring", "expire"):
            return "renew"
        if re.search(r"\b(my|what) (polic(y|ies)|plans)\b|(policies|plans) do i have|policy details", t):
            return "policies"
        if re.search(r"\b(my profile|my details|customer 360|my account|overview|summary of my)\b", t):
            return "profile"
        if re.search(r"\b(quote|quotation|price|cost|how much|insure|insurance for|need|want|looking for|interested in|"
                     r"get|buy|plan for|cover for)\b", t) and (_line_in_text(t) or UNSUPPORTED_RE.search(t)) \
                or re.search(r"\b(health|motor|car|life|retirement|savings|home) (insurance|takaful|plan|policy|cover)\b", t) \
                or re.fullmatch(r"(health|motor|life|retirement|savings|retirement (and|&) savings|general|home|car)\.?", t):
            return "quote"
        if s.intent in {"claim", "renew", "buy"}:
            return s.intent  # continue slot filling
        if re.search(r"^(hi|hello|hey|salam|salaam|assalam|as-?salamu|marhaba|ahlan|good (morning|afternoon|evening))\b", t):
            return "greet"
        return None

    # ------------------------------------------------------------------ greeting / identity
    def _h_greet(self, t, m, s, res, cfg):
        name = session_store.get(self._sid(cfg)).customer_name
        if name:
            s.intent = None
            res.reply = f"Ahlan, {_first(name)}! How can I help you today?"
            return res
        s.intent, s.slots = "quote", {"asked": "line"}
        res.reply = (f"{GREETING} I'm {settings.ASSISTANT_NAME}, your {settings.INSURER_SHORT} assistant. "
                     f"Which plan are you looking for — {PORTFOLIOS}?")
        return res

    def _h_who(self, t, m, s, res, cfg):
        res.reply = "Please share your registered mobile number, or your National ID / Iqama."
        return res

    def _h_identify(self, t, m, s, res, cfg):
        sid = self._sid(cfg)
        ident = None
        for rx in (re.compile(r"\bcust-\d+\b", re.I), re.compile(r"\bpol-[a-z]+-\d+\b", re.I), EMAIL_RE, PHONE_RE):
            if mt := rx.search(m):
                ident = mt.group(0)
                break
        if not ident:
            res.reply = "Sure — what's your registered mobile number?"
            return res
        out = self._call(res, identify_customer, {"identifier": ident}, cfg)
        if not out["ok"]:
            res.reply = f"Sorry, I couldn't check that: {out['error']}"
            return res
        d = out["data"]
        if not d["found"]:
            res.reply = "I couldn't find that number. Try another, or share your National ID / Iqama to register."
            return res
        s.intent, s.slots = None, {}
        return self._resume(s, res, sid, f"Ahlan, {_first(d['customer']['name'])}! You're verified.")

    def _h_onboard(self, t, m, s, res, cfg):
        """"I'm new" → start the product journey; an ID typed on its own → verify straight away."""
        sid = self._sid(cfg)
        sid_m = SAUDI_ID_IN_TEXT.search(m)
        if not sid_m:
            s.intent, s.slots = "quote", {"asked": "line"}
            res.reply = f"{GREETING} Happy to have you. Which plan are you looking for — {PORTFOLIOS}?"
            return res
        nid = sid_m.group(0)
        args = {"id_type": "NATIONAL_ID" if nid.startswith("1") else "IQAMA", "id_number": nid, "consent": True}
        if veh := identity_service.normalize_plate(SAUDI_ID_IN_TEXT.sub(" ", m)):
            args["vehicle_number"] = veh
        out = self._call(res, fetch_kyc_from_government, args, cfg)
        if not out["ok"]:
            res.reply = f"{out['error']} Could you share it again?"
            return res
        d = out["data"]
        if d.get("already_registered"):
            s.intent, s.slots = None, {}
            return self._resume(s, res, sid, f"Ahlan, {_first(d['customer']['name'])}! You're already with us.")
        s.intent, s.slots = "kyc_confirm", {}
        res.reply = self._kyc_question(d["draft"])
        return res

    @staticmethod
    def _kyc_question(dr: dict) -> str:
        veh = f", and your {dr['vehicle']['make_model']} {dr['vehicle'].get('model_year', '')}".rstrip() \
            if dr.get("vehicle") else ""
        born = str(dr.get("date_of_birth", ""))[:4]
        lead = "Nafath approved." if dr.get("name_match") is not False else \
            "Nafath approved, but the name on this ID is different."
        return f"{lead} Yakeen shows **{dr['name']}**, born {born}, {dr.get('city', '')}{veh}. Is that you?"

    def _confirm_kyc(self, t, m, s, res, cfg) -> tuple[bool, str | None]:
        """Handle the answer to "Is that you?". Returns (registered, reply-if-not-done)."""
        fixes: dict[str, str] = {}
        if em := EMAIL_RE.search(m):
            fixes["email"] = em.group(0)
        if ph := PHONE_RE.search(m):
            fixes["phone"] = ph.group(0)
        for field_name in ("name", "address"):
            if mt := re.search(rf"\b{field_name}\s+(?:is|should be|to)\s+(.+)$", m, re.I):
                fixes[field_name] = mt.group(1).strip().rstrip(".")
        wants_yes = bool(YES_RE.search(t)) and not re.search(r"\b(no|not|wrong|incorrect|change)\b", t)
        if fixes and not wants_yes:
            self._call(res, confirm_registration, {"confirm": False, **fixes}, cfg)
            return False, f"Updated your {', '.join(sorted(fixes))}. Is everything correct now?"
        if not wants_yes:
            return False, "No problem — what should I correct? For example, \"address is …\"."
        out = self._call(res, confirm_registration, {"confirm": True, **fixes}, cfg)
        if not out["ok"]:
            return False, f"I couldn't complete the registration: {out['error']}"
        return True, None

    def _h_kyc_confirm(self, t, m, s, res, cfg):
        ok, reply = self._confirm_kyc(t, m, s, res, cfg)
        if not ok:
            res.reply = reply
            return res
        s.intent, s.slots = None, {}
        name = session_store.get(self._sid(cfg)).customer_name
        return self._resume(s, res, self._sid(cfg), f"Shukran, {_first(name)} — you're registered.")

    # ------------------------------------------------------------------ the new-plan journey
    def _h_quote(self, t, m, s, res, cfg):
        sl = s.slots
        sid = self._sid(cfg)
        ident = session_store.get(sid)
        extra = ident.extra

        # 1. which portfolio?
        if UNSUPPORTED_RE.search(t) and not sl.get("line"):
            sl.update(asked="line")
            res.reply = f"This chat covers individual plans only — {PORTFOLIOS}. Which would you like?"
            return res
        line = _line_in_text(t) if not sl.get("line") or sl.get("asked") in ("line", None) else None
        if line and line != sl.get("line"):
            keep = {k: sl[k] for k in ("pre",) if k in sl}
            sl.clear()
            sl.update(line=line, **keep)
            if FAMILY_RE.search(t) and line in ("health", "life"):
                sl["pre"] = "Our online plans are for individuals, so this covers you. "
            if p := _plan_in_text(t, line):
                sl["plan"] = p
            if not ident.customer_id:
                sl["seed"] = t  # details in the opening message ("insure my villa…") are used after identity
        if not sl.get("line"):
            if FAMILY_RE.search(t):
                res.reply = f"This chat covers individual plans only. Which would you like — {PORTFOLIOS}?"
            else:
                res.reply = f"Which plan are you looking for — {PORTFOLIOS}?"
            sl["asked"] = "line"
            return res
        line = sl["line"]

        # 2. identity (product first, then name → ID → plate)
        if not ident.customer_id:
            done = self._identity_steps(t, m, s, res, cfg)
            if not done:
                return res
            ident = session_store.get(sid)
            extra = ident.extra
            if line != "motor" or extra.get("vehicle"):
                t = ""  # this message answered the identity questions, not the product ones
        if line == "motor" and not extra.get("vehicle"):
            plate = identity_service.normalize_plate(m)
            if not plate:
                sl["asked"] = "plate"
                res.reply = self._say(sl, "What's your plate number, e.g. 7788 BDR? (Or the Istimara sequence number.)")
                return res
            out = self._call(res, lookup_vehicle, {"vehicle_number": plate}, cfg)
            if not out["ok"]:
                res.reply = f"{out['error']} Could you check the plate?"
                return res
            v = out["data"]["vehicle"]
            sl["pre"] = f"Found your {v['make_model']} {v.get('model_year', '')}. ".replace(" .", ".")
            t = ""  # the plate answer isn't an answer to the next question

        # 3. product questions
        if (seed := sl.pop("seed", None)) and ident.customer_id and seed != t:
            t = f"{seed} {t}".strip()
        return {"motor": self._q_motor, "health": self._q_health, "life": self._q_life, "savings": self._q_savings,
                "general": self._q_general, "home": self._q_general}[line](t, m, s, res, cfg)

    @staticmethod
    def _say(sl: dict, text: str) -> str:
        return sl.pop("pre", "") + text

    def _identity_steps(self, t, m, s, res, cfg) -> bool:
        """Collect name → ID → plate (motor) and verify. Returns True once the chat is verified."""
        sl = s.slots
        sid = self._sid(cfg)
        asked = sl.get("asked")

        if asked == "kyc":
            ok, reply = self._confirm_kyc(t, m, s, res, cfg)
            if not ok:
                res.reply = reply
                return False
            sl["pre"] = f"Shukran, {_first(session_store.get(sid).customer_name)} — you're registered. "
            sl.pop("asked", None)
            return True

        # an existing customer may just give their mobile number
        if PHONE_RE.search(m) and not SAUDI_ID_IN_TEXT.search(m):
            out = self._call(res, identify_customer, {"identifier": PHONE_RE.search(m).group(0)}, cfg)
            if out["ok"] and out["data"]["found"]:
                sl["pre"] = f"Ahlan, {_first(out['data']['customer']['name'])}! "
                sl.pop("asked", None)
                if sl["line"] == "motor":
                    sl["asked"] = "plate"
                    res.reply = self._say(sl, "What's the plate number of the car to insure?")
                    return False
                return True
            res.reply = "I couldn't find that number. What's your National ID or Iqama number?"
            sl["asked"] = "id"
            return False

        if id_m := SAUDI_ID_IN_TEXT.search(m):
            sl["id"] = id_m.group(0)
        if sl["line"] == "motor" and (plate := identity_service.normalize_plate(SAUDI_ID_IN_TEXT.sub(" ", m))):
            sl["plate"] = plate
        if "name" not in sl:
            if asked == "name" or re.search(r"\b(my name is|name'?s)\b", t):
                if n := _parse_name(m):
                    sl["name"] = n

        if "name" not in sl:
            sl["asked"] = "name"
            lead = {"motor": "Let's insure your car.", "health": "Let's find your health plan.",
                    "life": "Let's protect your family's future.", "savings": "Let's plan your savings.",
                    "general": "Let's protect your home."}[sl["line"]]
            res.reply = self._say(sl, f"{lead} May I have your full name?")
            return False
        if "id" not in sl:
            sl["asked"] = "id"
            res.reply = (f"Thanks, {_first(sl['name'])}. Your National ID or Iqama number? You'll get a Nafath "
                         "request to approve.")
            return False
        if sl["line"] == "motor" and "plate" not in sl:
            sl["asked"] = "plate"
            res.reply = "And the car's plate number, e.g. 7788 BDR?"
            return False

        args = {"id_type": "NATIONAL_ID" if sl["id"].startswith("1") else "IQAMA", "id_number": sl["id"],
                "consent": True, "full_name": sl["name"]}
        if sl.get("plate"):
            args["vehicle_number"] = sl["plate"]
        out = self._call(res, fetch_kyc_from_government, args, cfg)
        if not out["ok"]:
            sl.pop("id", None)
            sl["asked"] = "id"
            res.reply = f"{out['error']} Could you share it again?"
            return False
        d = out["data"]
        if d.get("already_registered"):
            sl["pre"] = f"Ahlan, {_first(d['customer']['name'])} — you're already with us. "
            if sl.get("plate") and d.get("vehicle"):
                v = d["vehicle"]
                sl["pre"] += f"Found your {v['make_model']} {v.get('model_year', '')}. ".replace(" .", ".")
            sl.pop("asked", None)
            return True
        sl["asked"] = "kyc"
        res.reply = self._kyc_question(d["draft"])
        return False

    # ---------------- quote follow-up
    def _after_quote(self, out, s, res, cfg) -> TurnResult:
        s.intent, s.slots = None, {}
        if not out["ok"]:
            res.reply = f"Sorry, I couldn't prepare that quote: {out['error']}"
            return res
        q = out["data"]
        price = q["premium"]["total_premium"]
        if q.get("coverage") == "retirement_plan":
            pj = q["projection"]
            res.reply = (f"Your **Retirement Plan**: SAR {q['premium']['monthly']:,} a month until {pj['retirement_age']}, "
                         f"then about **SAR {pj['monthly_income']['mid']:,} a month for {pj['income_years']} years** "
                         "(projected, not guaranteed). Shall we go ahead?")
            s.offer = "buy"
            return res
        if q["line"] == "savings":
            pj = q["projection"]
            res.reply = (f"Your **{q['plan']}**: SAR {q['premium']['monthly']:,} a month for {pj['years']} years — "
                         f"around **SAR {pj['mid']:,}** at 5% a year (not guaranteed). Shall we go ahead?")
        else:
            vat = "VAT-exempt" if q["line"] == "life" else "incl. VAT"
            res.reply = (f"Your **{q['plan']}** quote is **SAR {price:,}** a year ({vat}). "
                         f"Other plans are on the card. Shall we go ahead?")
        s.offer = "buy"
        return res

    # ---------------- motor
    def _q_motor(self, t, m, s, res, cfg):
        sl = s.slots
        extra = session_store.get(self._sid(cfg)).extra
        v = extra.get("vehicle") or {}
        if "plan" not in sl:
            if re.search(r"\b(recommend\w*|suggest\w*|not sure|you decide|best|whatever|any|yes|ok|okay|sure|go with)\b", t) \
                    and not _plan_in_text(t, "motor"):
                sl["plan"] = quote_engine.recommend_coverage(v.get("vehicle_age", 0), v.get("vehicle_type", "car"))[0]
            elif c := _plan_in_text(t, "motor"):
                sl["plan"] = c
        if "plan" not in sl:
            sl["asked"] = "plan"
            rec = quote_engine.COVERAGES[quote_engine.recommend_coverage(v.get("vehicle_age", 0),
                                                                         v.get("vehicle_type", "car"))[0]]["plan"]
            res.reply = self._say(sl, f"Which plan — TPL, Comprehensive or Comprehensive Plus? I'd suggest **{rec}**.")
            return res
        out = self._call(res, generate_quote, {"coverage": sl["plan"]}, cfg)
        return self._after_quote(out, s, res, cfg)

    # ---------------- health (individual)
    def _q_health(self, t, m, s, res, cfg):
        sl = s.slots
        asked = sl.get("asked")
        extra = session_store.get(self._sid(cfg)).extra
        if "age" not in sl and extra.get("age") is None:
            if asked == "age" and (mt := re.search(r"\b(\d{2})\b", t)):
                sl["age"] = int(mt.group(1))
            else:
                sl["asked"] = "age"
                res.reply = self._say(sl, "How old are you?")
                return res
        if "ped" not in sl:
            if re.search(r"diabet|sugar|\bbp\b|blood pressure|hypertension|thyroid|asthma|heart|cholesterol|kidney|cancer|"
                         r"chronic", t) and not re.search(r"\b(no|none|not)\b", t):
                sl["ped"] = True
            elif asked == "ped" and re.search(r"\b(no|none|nothing|healthy|not really|nope|la)\b", t):
                sl["ped"] = False
            elif asked == "ped" and YES_RE.search(t):
                sl["ped"] = True
        if "plan" not in sl and (pl := _plan_in_text(t, "health")):
            sl["plan"] = pl
        if "ped" not in sl:
            sl["asked"] = "ped"
            res.reply = self._say(sl, "Do you have any chronic condition, like diabetes, hypertension or asthma?")
            return res
        args = {"pre_existing_conditions": sl["ped"]}
        if sl.get("plan"):
            args["plan"] = sl["plan"]
        if sl.get("age"):
            args["age"] = sl["age"]
        out = self._call(res, generate_health_quote, args, cfg)
        return self._after_quote(out, s, res, cfg)

    # ---------------- life
    def _q_life(self, t, m, s, res, cfg):
        sl = s.slots
        asked = sl.get("asked")
        age = session_store.get(self._sid(cfg)).extra.get("age") or sl.get("age")
        if age is None:
            if asked == "age" and (mt := re.search(r"\b(\d{2})\b", t)):
                sl["age"] = age = int(mt.group(1))
            else:
                sl["asked"] = "age"
                res.reply = self._say(sl, "How old are you?")
                return res
        if "smoker" not in sl:
            if re.search(r"non[- ]?smoker|don'?t smoke|do not smoke|never smoke", t):
                sl["smoker"] = False
            elif re.search(r"\bsmoker\b|\bi smoke\b|cigarette|shisha|vape|tobacco", t) and not re.search(r"\bno\b", t):
                sl["smoker"] = True
            elif asked == "smoker" and re.search(r"\b(no|nope|never|la)\b", t):
                sl["smoker"] = False
            elif asked == "smoker" and YES_RE.search(t):
                sl["smoker"] = True
        if "plan" not in sl and (pl := _plan_in_text(t, "life")):
            sl["plan"] = pl
        if "smoker" not in sl:
            sl["asked"] = "smoker"
            res.reply = self._say(sl, "Do you smoke or use tobacco, including shisha?")
            return res
        if asked == "cover":
            if amounts := [v for v, _, _ in _money(t) if v >= 50_000]:
                sl["cover"] = amounts[0]
            if y := _years(t):
                sl["term"] = y
            if not (YES_RE.search(t) or sl.get("cover") or sl.get("term")):
                res.reply = "How much cover would you like, and for how many years?"
                return res
            sl["agreed"] = True
        if not sl.get("agreed"):
            sl["asked"] = "cover"
            rec = life_engine.recommend_cover(age)
            term = min(20, 70 - age)
            res.reply = self._say(sl, f"I'd suggest **SAR {rec:,}** sum covered for **{term} years**. Shall I use that?")
            return res
        args = {"smoker": sl["smoker"]}
        for k, a in (("cover", "sum_assured"), ("term", "term_years"), ("plan", "plan"), ("age", "age")):
            if sl.get(k):
                args[a] = sl[k]
        out = self._call(res, generate_life_quote, args, cfg)
        return self._after_quote(out, s, res, cfg)

    # ---------------- retirement & savings
    def _q_savings(self, t, m, s, res, cfg):
        sl = s.slots
        asked = sl.get("asked")
        age = session_store.get(self._sid(cfg)).extra.get("age") or sl.get("age")
        if age is None:
            if asked == "age" and (mt := re.search(r"\b(\d{2})\b", t)):
                sl["age"] = age = int(mt.group(1))
            else:
                sl["asked"] = "age"
                res.reply = self._say(sl, "How old are you?")
                return res
        if (pl := _plan_in_text(t, "savings")) and ("plan" not in sl or asked in ("goal", "monthly")):
            if pl != sl.get("plan") and asked == "monthly":
                sl.pop("agreed", None)
            sl["plan"] = pl
        if "plan" not in sl:
            sl["asked"] = "goal"
            res.reply = self._say(sl, "What are you saving for — **retirement**, a **child's education**, or a "
                                      "**general goal**?")
            return res
        if sl["plan"] == "retirement_plan":
            return self._q_retirement(t, m, s, res, cfg, age)
        if asked in ("goal", "monthly"):
            if amounts := [v for v, _, _ in _money(t) if 300 <= v <= 50_000]:
                sl["monthly"] = amounts[0]
            elif asked == "goal" and (mt := re.search(r"\b(\d{3,5})\b", t)) and 300 <= int(mt.group(1)) <= 50_000:
                sl["monthly"] = float(mt.group(1))
            if y := _years(t):
                sl["term"] = y
            if asked == "monthly" and (YES_RE.search(t) or sl.get("monthly")):
                sl["agreed"] = True
        if not sl.get("agreed") and not sl.get("monthly"):
            sl["asked"] = "monthly"
            rec = savings_engine.recommend_monthly(age)
            yrs = savings_engine.default_term(sl["plan"], age)
            res.reply = self._say(sl, f"How much each month? I'd suggest **SAR {rec:,}** for {yrs} years.")
            return res
        args = {"plan": sl["plan"]}
        for k, a in (("monthly", "monthly_contribution"), ("term", "term_years"), ("age", "age")):
            if sl.get(k):
                args[a] = sl[k]
        out = self._call(res, generate_savings_quote, args, cfg)
        return self._after_quote(out, s, res, cfg)

    # ---------------- retirement plan (the flagship journey)
    def _q_retirement(self, t, m, s, res, cfg, age: int):
        sl = s.slots
        asked = sl.get("asked")
        if asked == "goal":
            asked = None  # the answer to "what are you saving for" may also carry an age or an amount
        # retirement age
        if "ra" not in sl:
            mt = re.search(r"\b(?:retire|retirement|at|by|age)\D{0,12}(5[5-9]|6[0-5])\b", t) or                 (re.search(r"\b(5[5-9]|6[0-5])\b", t) if asked == "ra" else None)
            if mt:
                sl["ra"] = int(mt.group(1))
            elif asked == "ra" and re.search(r"\b(sixty|60)\b|default|suggest|normal|usual", t):
                sl["ra"] = 60
        # monthly contribution
        if "monthly" not in sl:
            if amounts := [v for v, _, _ in _money(t) if 1_000 <= v <= 80_000]:
                sl["monthly"] = amounts[0]
            elif asked == "monthly" and (mt := re.search(r"\b(\d{4,5})\b", t)) and 1_000 <= int(mt.group(1)) <= 80_000:
                sl["monthly"] = float(mt.group(1))
            elif asked == "monthly" and (YES_RE.search(t) or re.search(r"suggest|recommend", t)):
                sl["monthly"] = float(savings_engine.recommend_monthly(age, "retirement_plan"))
            elif asked == "monthly" and _money(t):
                res.reply = "The Retirement Plan starts from SAR 1,000 a month. How much would you like to contribute?"
                return res
        if "freq" not in sl and (fq := savings_engine.normalize_frequency(t)) and (asked == "freq" or fq != "monthly"):
            sl["freq"] = fq
        elif "freq" not in sl and asked == "freq" and YES_RE.search(t):
            sl["freq"] = "monthly"
        if "fund" not in sl:
            if fd := savings_engine.normalize_fund(t):
                sl["fund"] = fd
            elif asked == "fund" and re.search(r"\b(yes|ok|okay|sure|suggest\w*|recommend\w*|fine|go with)\b", t):
                sl["fund"] = savings_engine.recommend_fund(age, sl.get("ra", 60))
        if "benef" not in sl and asked == "benef" and len(m.strip()) >= 3 and not NO_RE.fullmatch(t):
            sl["benef"] = m.strip().rstrip(".")
        if "decl" not in sl and asked == "decl":
            us = bool(re.search(r"\b(us|usa|american|green card|united states)\b", t)) and not re.search(r"\bnot\b", t)
            pep = bool(re.search(r"\b(pep|politic\w*|minister|official|government position)\b", t))                 and not re.search(r"\bnot\b|\bno\b", t)
            if re.search(r"^\s*(no|nope|neither|none|la)\b|\bnot\b|\bneither\b", t) and not (us or pep):
                sl["decl"] = {"us_person": False, "pep": False}
            elif us or pep:
                sl["decl"] = {"us_person": us, "pep": pep}
            elif YES_RE.search(t):
                res.reply = "Which applies — US person, politically exposed person, or both?"
                return res
        if "sof" not in sl and asked == "sof" and len(t) >= 3:
            sl["sof"] = next((w for w in ("salary", "business", "investments", "inheritance", "savings", "rental")
                              if w[:5] in t), m.strip().rstrip("."))

        ra = sl.get("ra")
        if not ra:
            sl["asked"] = "ra"
            res.reply = self._say(sl, "At what age would you like to retire — **55**, **60** or **65**?")
            return res
        if "monthly" not in sl:
            sl["asked"] = "monthly"
            rec = savings_engine.recommend_monthly(age, "retirement_plan")
            res.reply = self._say(sl, f"How much would you like to contribute each month? The minimum is SAR 1,000 — "
                                      f"I'd suggest **SAR {rec:,}**.")
            return res
        if "freq" not in sl:
            sl["asked"] = "freq"
            res.reply = "Would you like to pay **monthly**, **quarterly**, **half-yearly** or **yearly**?"
            return res
        if "fund" not in sl:
            sl["asked"] = "fund"
            rec = savings_engine.recommend_fund(age, ra)
            res.reply = (f"Which fund suits you — **Conservative**, **Balanced** or **Growth**? With {ra - age} years "
                         f"to go, I'd suggest **{rec.title()}**.")
            return res
        if "benef" not in sl:
            sl["asked"] = "benef"
            res.reply = "Who should receive the Takaful protection if anything happens to you? Their name and relationship, please."
            return res
        if "decl" not in sl:
            sl["asked"] = "decl"
            res.reply = ("Two quick declarations: are you a US citizen or US tax resident, or a politically exposed "
                         "person?")
            return res
        if "sof" not in sl:
            sl["asked"] = "sof"
            res.reply = "Last one — is the money from your **salary**, **business**, **investments** or something else?"
            return res
        args = {"plan": "retirement_plan", "retirement_age": ra, "monthly_contribution": sl["monthly"],
                "frequency": sl["freq"], "fund": sl["fund"], "beneficiary": sl["benef"],
                "us_person": sl["decl"]["us_person"], "pep": sl["decl"]["pep"], "source_of_funds": sl["sof"]}
        if sl.get("age"):
            args["age"] = sl["age"]
        out = self._call(res, generate_savings_quote, args, cfg)
        return self._after_quote(out, s, res, cfg)

    # ---------------- general (home & property)
    def _q_general(self, t, m, s, res, cfg):
        sl = s.slots
        asked = sl.get("asked")
        if "property_type" not in sl and re.search(r"apartment|flat|villa|independent|townhouse|duplex|house|palace", t):
            sl["property_type"] = "independent" if re.search(r"villa|independent|townhouse|duplex|palace|house", t) \
                and not re.search(r"apartment|flat", t) else "apartment"
        amounts = _money(t)
        if not amounts and asked in ("building", "contents") and (mt := re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", t)):
            v = float(mt.group(1))
            amounts = [(v * 1_000 if v < 10_000 else v, 0, len(t))]  # bare small number → thousands of SAR
        for v, start, end in amounts:
            before = re.split(r"\b(?:with|and|plus)\b|[,.;]", t[max(0, start - 30): start])[-1]
            after = re.split(r"\b(?:with|and|plus)\b|[,.;]", t[end: end + 30])[0]
            is_contents = bool(CONTENT_WORDS.search(before) or CONTENT_WORDS.search(after)) or (
                asked == "contents" and len(amounts) == 1)
            if is_contents and "contents" not in sl:
                sl["contents"] = v
            elif "building" not in sl:
                sl["building"] = v
            elif "contents" not in sl:
                sl["contents"] = v
        if "contents" not in sl and (asked == "contents" or re.search(r"structure only|just the (structure|building)|no contents", t)) \
                and re.search(r"\b(no|none|nothing|zero|0|structure only|just the)\b", t):
            sl["contents"] = 0
        if "city" not in sl and (c := _parse_city(t)):
            sl["city"] = c
        if "plan" not in sl and (pl := _plan_in_text(t, "general")):
            sl["plan"] = pl

        if "property_type" not in sl:
            sl["asked"] = "ptype"
            res.reply = self._say(sl, "Is it an **apartment** or a **villa**?")
            return res
        if "building" not in sl:
            sl["asked"] = "building"
            res.reply = self._say(sl, "Roughly what would it cost to rebuild? For example SAR 1.5 million for a villa.")
            return res
        if "contents" not in sl:
            sl["asked"] = "contents"
            res.reply = self._say(sl, "And your belongings — furniture, electronics? Say \"none\" for building only.")
            return res
        args = {"property_type": sl["property_type"], "building_value": sl["building"], "contents_value": sl["contents"]}
        if sl.get("city"):
            args["city"] = sl["city"]
        if sl.get("plan"):
            args["plan"] = sl["plan"]
        out = self._call(res, generate_general_quote, args, cfg)
        return self._after_quote(out, s, res, cfg)

    # ------------------------------------------------------------------ purchase
    def _h_buy(self, t, m, s, res, cfg):
        sid = self._sid(cfg)
        extra = session_store.get(sid).extra
        sl = s.slots
        s.offer = None
        if mt := re.search(r"\bqt-\d{4}-\d{4}\b", t):
            sl["quote_id"] = mt.group(0).upper()
        if re.search(r"plate|registration|istimara|sequence", t) and (plate := identity_service.normalize_plate(m)):
            sl["registration_number"] = plate
        req_line = _line_in_text(t)
        cur_line = sl.get("line") or extra.get("last_quote_line")
        if method := (purchase_service.normalize_method(m) or purchase_service.normalize_method(t)):
            sl["method"] = method[0]

        if sl.get("reviewed") and NO_RE.search(t) and not _plan_in_text(t, cur_line):
            s.intent, s.slots = None, {}
            res.reply = "No problem — your quote stays saved for 15 days."
            return res
        # no quote yet, or a different product than the last quote → start that product's journey
        if not sl.get("quote_id") and (not extra.get("last_quote_id") or (req_line and req_line != cur_line
                                                                            and not sl.get("reviewed"))):
            s.intent, s.slots = "quote", {}
            return self._h_quote(t, m, s, res, cfg)
        sl["line"] = cur_line
        plan = _plan_in_text(t, cur_line)
        changed = bool(plan) and plan != sl.get("coverage")
        if plan:
            sl["coverage"] = plan
        base = {k: sl[k] for k in ("quote_id", "coverage", "registration_number") if sl.get(k)}

        # ---- pay
        if sl.get("reviewed") and not changed and (method or YES_RE.search(t) or BUY_RE.search(t)):
            if not sl.get("method"):
                res.reply = f"How would you like to pay the SAR {sl['total']:,} — {PAY_METHODS}?"
                return res
            out = self._call(res, purchase_policy, {**base, "confirm": True, "payment_method": sl["method"]}, cfg)
            s.intent, s.slots = None, {}
            if not out["ok"]:
                res.reply = f"The payment couldn't be completed: {out['error']}"
                return res
            d = out["data"]
            res.reply = (f"Mabrook! Your {d['plan']} is active — certificate **{d['policy_id']}**. "
                         "It's in your profile with the schedule below.")
            return res

        # ---- review (first time, or after switching plan)
        out = self._call(res, purchase_policy, {**base, "confirm": False}, cfg)
        if not out["ok"]:
            s.intent, s.slots = None, {}
            res.reply = f"I couldn't start the checkout: {out['error']}"
            return res
        d = out["data"]
        sl.update(quote_id=d["quote_id"], coverage=d["coverage"], total=d["total_premium"])
        if not d["underwriting"]["accepted"]:
            sl["reviewed"] = False
            issues = " ".join(d["underwriting"]["issues"])
            fixable_by_plan = not re.search(r"KYC|Iqama|medical|survey|examination|declaration|source-of-funds", issues)
            res.reply = issues + (" Which plan would you like instead?" if fixable_by_plan else
                                  " Your quote stays saved for 15 days.")
            if not fixable_by_plan:
                s.intent, s.slots = None, {}
            return res
        sl["reviewed"] = True
        ask = (f"Shall I take **SAR {d['total_premium']:,}** by {sl['method']}?" if sl.get("method")
               else f"How would you like to pay — {PAY_METHODS}?")
        res.reply = f"**{d['plan']}**, starting today, **SAR {d['total_premium']:,}** a year. {ask}"
        return res

    # ------------------------------------------------------------------ servicing
    def _h_policies(self, t, m, s, res, cfg):
        s.intent = None
        out = self._call(res, get_policy_details, {}, cfg)
        ps = out.get("data") or []
        active = [p for p in ps if p["status"] in ("Active", "Expiring")]
        due = [p for p in active if p["renewal_due"]]
        res.reply = f"You have {len(active)} active plans — they're on the card."
        if due:
            res.reply += f" Your {due[0]['insured_asset'].split(' · ')[0]} is due for renewal in {due[0]['days_to_expiry']} days — renew it?"
        return res

    def _h_profile(self, t, m, s, res, cfg):
        s.intent = None
        out = self._call(res, get_customer_profile, {}, cfg)
        d = out["data"]
        sm = d["summary"]
        res.reply = (f"{_first(d['customer']['name'])}, you have {sm['active_policies']} active plans and "
                     f"{sm['open_claims']} open claim(s). Suggestion: {d['recommended_actions'][0]['title']}.")
        return res

    def _h_claim(self, t, m, s, res, cfg):
        sl = s.slots
        first = not sl
        asked = sl.get("asked")
        if (d := _parse_date(t)) and "incident_date" not in sl:
            sl["incident_date"] = d
        if "location" not in sl and (loc := _parse_city(t)):
            sl["location"] = loc
        if asked == "location" and "location" not in sl:
            sl["location"] = m.strip().rstrip(".")
        if asked == "description" and "description" not in sl:
            sl["description"] = m.strip()
        if first and len(t.split()) >= 8:  # detailed first message doubles as the description
            sl["description"] = m.strip()
        if re.search(r"\b(hospital|admitted|surgery)\b", t):
            sl["incident_type"] = "Health - Hospitalisation"
        if re.search(r"\bnajm|taqdeer\b", t):
            sl["najm"] = True
        cid = session_store.get(self._sid(cfg)).customer_id
        motors = [] if sl.get("incident_type", "").startswith(("Health", "Home")) or not cid else [
            p for p in insurance_service.list_policies(cid)
            if p["policy_type"].startswith("Motor") and p["status"] in ("Active", "Expiring")]
        if "policy_id" not in sl and len(motors) > 1:
            for p in motors:
                words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}|\d{4}", p["insured_asset"])][:3]
                if any(re.search(rf"\b{re.escape(w)}\b", t) for w in words) or p["policy_id"].lower() in t:
                    sl["policy_id"] = p["policy_id"]
                    break

        prefix = "Sorry to hear that — I hope everyone is safe. " if first else ""
        if "incident_date" not in sl:
            sl["asked"] = "date"
            res.reply = prefix + "When did it happen?"
            return res
        if "location" not in sl:
            sl["asked"] = "location"
            res.reply = prefix + "Where did it happen?"
            return res
        if "description" not in sl:
            sl["asked"] = "description"
            res.reply = prefix + "Briefly, what happened?"
            return res
        if "policy_id" not in sl and len(motors) > 1:
            sl["asked"] = "vehicle"
            opts = " or ".join(f"the **{p['insured_asset'].split(' · ')[0]}**" for p in motors)
            res.reply = f"Which car — {opts}?"
            return res
        args = {"description": sl["description"], "incident_date": sl["incident_date"], "location": sl["location"]}
        for k in ("policy_id", "incident_type"):
            if sl.get(k):
                args[k] = sl[k]
        out = self._call(res, create_claim, args, cfg)
        had_najm = sl.get("najm")
        s.intent, s.slots = None, {}
        if not out["ok"]:
            res.reply = f"I couldn't register the claim: {out['error']}"
            return res
        c = out["data"]
        res.reply = f"Done — your claim ID is **{c['claim_id']}**. Next steps are on the card."
        if c.get("incident_type", "").startswith("Accident") and not had_najm:
            res.reply += " Please get the Najm report."
        return res

    def _h_track(self, t, m, s, res, cfg):
        s.intent = None
        mid = re.search(r"\bclm-\d{4}-\d{4}\b", t)
        out = self._call(res, track_claim, {"claim_id": mid.group(0).upper()} if mid else {}, cfg)
        if not out["ok"]:
            res.reply = f"I couldn't find that claim: {out['error']}"
            return res
        d = out["data"]
        c = ([x for x in d if x["status"] != "Closed"] or d)[0] if isinstance(d, list) else d
        res.reply = f"Claim **{c['claim_id']}** is at **{c['status']}** — {c['progress']}% done."
        return res

    def _h_renew(self, t, m, s, res, cfg):
        sl = s.slots
        mid = re.search(r"\bpol-[a-z]+-\d+\b", t)
        if "policy_id" not in sl:
            if mid:
                sl["policy_id"] = mid.group(0).upper()
            else:
                ps = self._call(res, get_policy_details, {}, cfg)["data"]
                cands = [p for p in ps if p["status"] in ("Active", "Expiring")
                         and p["policy_type"] not in ("Life", "Retirement & Savings")]
                if _has(t, "car", "motor"):
                    cands = [p for p in cands if p["policy_type"].startswith("Motor")] or cands
                elif _has(t, "health"):
                    cands = [p for p in cands if p["policy_type"] == "Health"] or cands
                if not cands:
                    s.intent = None
                    res.reply = "I couldn't find a plan due for renewal."
                    return res
                sl["policy_id"] = sorted(cands, key=lambda p: p["days_to_expiry"])[0]["policy_id"]
        if sl.get("quoted") and YES_RE.search(t) and not NO_RE.search(t):
            out = self._call(res, renew_policy, {"policy_id": sl["policy_id"], "confirm": True}, cfg)
            s.intent, s.slots = None, {}
            if not out["ok"]:
                res.reply = f"Renewal failed: {out['error']}"
                return res
            res.reply = f"Mabrook — renewed! Your new certificate is **{out['data']['new_policy_id']}**."
            return res
        if sl.get("quoted") and NO_RE.search(t):
            s.intent, s.slots = None, {}
            res.reply = "No problem — just ask when you're ready."
            return res
        out = self._call(res, renew_policy, {"policy_id": sl["policy_id"], "confirm": False}, cfg)
        if not out["ok"]:
            s.intent, s.slots = None, {}
            res.reply = f"I can't renew that plan: {out['error']}"
            return res
        d = out["data"]
        sl["quoted"] = True
        ncd = (f" Your No Claim Discount goes to {d['ncb_renewal']}%." if d["policy"]["policy_type"].startswith("Motor")
               and d["ncb_renewal"] != d["ncb_current"] else "")
        res.reply = (f"Your {d['policy']['insured_asset'].split(' · ')[0]} renews at **SAR {d['renewal_premium']:,}**."
                     f"{ncd} Shall I renew it?")
        return res

    def _h_knowledge(self, t, m, s, res, cfg):
        s.intent = None
        out = self._call(res, knowledge_search, {"query": m}, cfg)
        hits = out.get("data") or []
        if not hits:
            res.reply = f"I can help with quotes, claims and renewals. Which plan interests you — {PORTFOLIOS}?"
            return res
        q = set(re.findall(r"[a-z]{4,}", t)) - {"does", "what", "insurance", "policy", "cover", "covered", "takaful"}
        h = hits[0]
        sents = re.split(r"(?<=[.!?])\s+", re.sub(r"[*#|]", "", h["content"]).replace("\n", " "))
        scored = sorted(((len(q & set(re.findall(r"[a-z]{4,}", x.lower()))), -i, x) for i, x in enumerate(sents)),
                        reverse=True)
        best = scored[0][2].strip("- ").strip() if scored and scored[0][0] else ""
        res.reply = f"{best} [{h['ref']}]" if best else "I couldn't find a clear answer in our documents."
        return res


offline_agent = OfflineAgent()
