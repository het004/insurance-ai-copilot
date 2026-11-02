"""Customer identification and new-customer onboarding — Saudi Arabia.

Existing customer:  mobile (+966 5x…) / email / customer ID / policy number → Customer 360 (Excel) → verified.
New customer:       National ID (citizens, starts with 1) or Iqama (residents, starts with 2) + consent
                    → SIMULATED: Nafath authentication → Yakeen (Elm) identity data → National Address (SPL)
                    → optional vehicle registration (Elm) → shown to the customer → confirmed → Customer 360.

⚠ No real government API is called. MOCK_REGISTRY and a deterministic generator stand in for Nafath, Yakeen,
the National Address service and vehicle registration data so the demo shows the real-world flow end to end.
ID numbers are never stored in clear — only a masked reference and a one-way hash.
"""
from __future__ import annotations

import hashlib
import random
import re
import time
from datetime import date, datetime, timedelta
from typing import Any

from app.database import db
from app.services.excel_store import excel_store
from app.services.progress import progress
from app.services.systems import CRM
from app.services.session_store import session_store


class IdentityError(Exception):
    pass


ID_TYPES = {"NATIONAL_ID": "National ID", "IQAMA": "Iqama"}
NID_RE = re.compile(r"^1\d{9}$")
IQAMA_RE = re.compile(r"^2\d{9}$")
PLATE_LETTERS = set("ABJDRSXTEGKLZNHUV")  # Latin letters used on Saudi plates
NOT_PLATES = {"AND", "THE", "ARE", "SAR", "HAS", "GET", "USE", "BUT", "DUE", "NET", "TAX", "VAT", "SUV", "ELM"}

# ------------------------------------------------------------------ simulated government data
MOCK_REGISTRY: dict[str, dict[str, Any]] = {
    "NATIONAL_ID:1012345678": {
        "name": "Abdullah Mohammed Al-Qahtani", "date_of_birth": "1990-05-12", "gender": "Male", "nationality": "Saudi",
        "address": "Building 7219, Al Takhassusi St, Al Olaya District, Riyadh 12333", "city": "Riyadh",
        "phone": "+966 55 012 3456", "email": "",
    },
    "IQAMA:2234567890": {
        "name": "Anil Joseph Mathew", "date_of_birth": "1986-11-03", "gender": "Male", "nationality": "Indian",
        "address": "Building 3105, Prince Sultan St, Al Rawdah District, Jeddah 23435", "city": "Jeddah",
        "phone": "+966 56 778 1290", "email": "",
    },
}
MOCK_VEHICLES: dict[str, dict[str, Any]] = {
    "7788 BDR": {"make_model": "Toyota Camry GLE", "model_year": 2022, "colour": "White", "body": "Sedan",
                 "registration_expiry": (date.today() + timedelta(days=210)).isoformat()},
    "4521 RTA": {"make_model": "Toyota Land Cruiser GXR", "model_year": 2023, "colour": "Pearl White", "body": "SUV",
                 "registration_expiry": (date.today() + timedelta(days=400)).isoformat()},
}
SUV_WORDS = re.compile(r"land cruiser|patrol|tahoe|sportage|hilux|prado|fortuner|yukon|pajero|rav4|tucson|santa fe|"
                       r"x5|q7|gx|lx|suv|4x4|pickup", re.I)
EV_WORDS = re.compile(r"tesla|lucid|ioniq|\bev\b|electric|byd", re.I)
BIKE_WORDS = re.compile(r"motorcycle|harley|yamaha|kawasaki|ducati|bike", re.I)


def vehicle_type_of(v: dict[str, Any]) -> str:
    text = f"{v.get('make_model', '')} {v.get('body', '')}"
    return "bike" if BIKE_WORDS.search(text) else "ev" if EV_WORDS.search(text) else "suv" if SUV_WORDS.search(text) else "car"


def age_from_dob(dob: str | None) -> int | None:
    try:
        d = date.fromisoformat(str(dob)[:10])
    except (TypeError, ValueError):
        return None
    t = date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def remember_profile(session_id: str, person: dict[str, Any]) -> None:
    """Facts the quote journeys can reuse so the customer isn't asked twice (age from DOB, city from address)."""
    extra = session_store.get(session_id).extra
    if (a := age_from_dob(person.get("date_of_birth"))) is not None:
        extra["age"] = a
    if person.get("city"):
        extra["city"] = person["city"]
_SAUDI_FIRST = ["Mohammed", "Abdullah", "Fahad", "Khalid", "Saud", "Nora", "Reem", "Lama", "Turki", "Hessa", "Omar", "Sultan"]
_SAUDI_FATHER = ["Abdulaziz", "Saleh", "Nasser", "Ibrahim", "Hamad", "Ali"]
_SAUDI_FAMILY = ["Al-Otaibi", "Al-Ghamdi", "Al-Zahrani", "Al-Shehri", "Al-Dosari", "Al-Mutairi", "Al-Harbi",
                 "Al-Shammari", "Al-Anazi", "Al-Subaie"]
_EXPATS = [("Ahmed Hassan Mahmoud", "Egyptian"), ("Muhammad Usman Tariq", "Pakistani"), ("Ramesh Kumar Pillai", "Indian"),
           ("Jose Miguel Santos", "Filipino"), ("Omar Khaled Haddad", "Jordanian"), ("Karim Nabil Mansour", "Lebanese")]
_PLACES = [("Al Malqa", "Riyadh", "13521"), ("Al Nakheel", "Riyadh", "12382"), ("Al Rawdah", "Jeddah", "23435"),
           ("Al Shati", "Jeddah", "23412"), ("Al Faisaliyah", "Dammam", "32272"), ("Al Aziziyah", "Makkah", "24243"),
           ("Al Khalidiyah", "Madinah", "42317"), ("Al Hamra", "Al Khobar", "34617")]
_STREETS = ["King Abdulaziz Rd", "Prince Mohammed bin Salman Rd", "Olaya St", "Tahlia St", "King Fahd Rd", "Al Imam Saud St"]
_FEMALE = {"Nora", "Reem", "Lama", "Hessa"}


def _synthetic(key: str) -> dict[str, Any]:
    rnd = random.Random(hashlib.sha256(key.encode()).hexdigest())
    if key.startswith("NATIONAL_ID"):
        first = rnd.choice(_SAUDI_FIRST)
        name, nat = f"{first} {rnd.choice(_SAUDI_FATHER)} {rnd.choice(_SAUDI_FAMILY)}", "Saudi"
        gender = "Female" if first in _FEMALE else "Male"
    else:
        name, nat = rnd.choice(_EXPATS)
        gender = "Male"
    district, city, postal = rnd.choice(_PLACES)
    y = rnd.randint(1965, 2001)
    return {
        "name": name, "date_of_birth": f"{y}-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}", "gender": gender,
        "nationality": nat,
        "address": f"Building {rnd.randint(1000, 9999)}, {rnd.choice(_STREETS)}, {district} District, {city} {postal}",
        "city": city, "phone": f"+966 5{rnd.randint(0, 9)} {rnd.randint(100, 999)} {rnd.randint(1000, 9999)}", "email": "",
    }


def _sleep(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))  # simulated latency so the progress panel shows real steps


def normalize_id(id_type: str | None, id_number: str) -> tuple[str, str]:
    n = re.sub(r"\D", "", id_number or "")
    t = (id_type or "").strip().upper().replace(" ", "_").replace("-", "_")
    if t in {"NATIONAL_ID", "NID", "NATIONALID", "CITIZEN_ID", "HAWIYA", "SAUDI_ID"}:
        t = "NATIONAL_ID"
    elif t in {"IQAMA", "RESIDENT_ID", "RESIDENCE_PERMIT", "RESIDENCY"}:
        t = "IQAMA"
    else:
        t = "NATIONAL_ID" if n.startswith("1") else "IQAMA" if n.startswith("2") else t
    if len(n) != 10:
        raise IdentityError("Saudi National ID and Iqama numbers have 10 digits — please check the number.")
    if t == "NATIONAL_ID" and not NID_RE.match(n):
        raise IdentityError("A Saudi National ID starts with 1. If you're a resident, please share your Iqama number (starts with 2).")
    if t == "IQAMA" and not IQAMA_RE.match(n):
        raise IdentityError("An Iqama number starts with 2. Saudi citizens should share their National ID (starts with 1).")
    if t not in ID_TYPES:
        raise IdentityError("Please share your National ID or Iqama number.")
    return t, n


def mask_id(t: str, n: str) -> str:
    return f"{n[0]}XXXXXX{n[-3:]}"


def id_hash(t: str, n: str) -> str:
    return hashlib.sha256(f"{t}:{n}:insurance-copilot".encode()).hexdigest()[:24]


def normalize_plate(text: str | None) -> str | None:
    """Saudi plate in Latin form '1234 ABJ' (digits + 3 letters) or an Istimara sequence number (9 digits)."""
    if not text:
        return None
    t = text.upper()
    if m := re.search(r"(?:SEQUENCE|SERIAL|SEQ)\D{0,15}(\d{9})\b", t):
        return f"SEQ {m.group(1)}"
    for m in re.finditer(r"\b(\d{1,4})\s?([A-Z]{3})\b", t):
        letters = m.group(2)
        if letters not in NOT_PLATES and set(letters) <= PLATE_LETTERS:
            return f"{m.group(1)} {letters}"
    return None


def _mask_phone(p: str) -> str:
    d = re.sub(r"\D", "", p)
    return f"+966 {d[-9:-7]}X XXX X{d[-3:]}" if len(d) >= 9 else p


def _customer_card(c: dict[str, Any], via: str) -> dict[str, Any]:
    with db() as conn:
        pol = conn.execute("SELECT COUNT(*) FROM policies WHERE customer_id=? AND status IN ('Active','Expiring')",
                           (c["customer_id"],)).fetchone()[0]
        clm = conn.execute("SELECT COUNT(*) FROM claims WHERE customer_id=? AND status!='Closed'",
                           (c["customer_id"],)).fetchone()[0]
    return {"customer_id": c["customer_id"], "name": c["name"], "phone_masked": _mask_phone(c["phone"]),
            "city": c["city"], "segment": c["segment"], "customer_since": c["customer_since"],
            "active_policies": pol, "open_claims": clm, "verified_via": via}


# ------------------------------------------------------------------ existing customers
def identify(session_id: str, identifier: str, tool_call_id: str | None = None) -> dict[str, Any]:
    ident = (identifier or "").strip()
    if not ident:
        raise IdentityError("Please share your registered mobile number, email, customer ID or policy number.")
    progress(tool_call_id, "search", f"{CRM} · searching Customer 360")
    _sleep(0.2, 0.4)
    via, cust = "registered mobile", None
    m = re.search(r"\bPOL-[A-Z]+-\d+\b", ident.upper())
    if m:
        with db() as conn:
            row = conn.execute("SELECT customer_id FROM policies WHERE policy_id=?", (m.group(0),)).fetchone()
        cust, via = (excel_store.get(row[0]) if row else None), "policy number"
    else:
        cust = excel_store.find(ident)
        via = "customer ID" if ident.upper().startswith("CUST-") else "registered email" if "@" in ident else via
    if not cust:
        progress(tool_call_id, "search", f"{CRM} · searching Customer 360", "error", "No matching customer")
        return {"found": False, "identifier": ident,
                "message": "No registered customer matches that. They may be a new customer — offer onboarding."}
    progress(tool_call_id, "search", f"{CRM} · searching Customer 360", "done", f"Matched {cust['customer_id']}")
    progress(tool_call_id, "otp", "Sending one-time password to registered mobile", "done", "OTP verified (simulated)")
    session_store.bind(session_id, cust["customer_id"], cust["name"], via)
    remember_profile(session_id, cust)
    return {"found": True, "customer": _customer_card(cust, via)}


def _vehicle(vehicle_number: str | None, step) -> dict[str, Any] | None:
    """Simulated vehicle registration lookup (Elm)."""
    plate = normalize_plate(vehicle_number) if vehicle_number else None
    if not plate:
        return None
    step("vehicle", f"Fetching vehicle registration from Elm ({plate})", "Vehicle registration via Elm — simulated",
         0.4, 0.7, "Istimara record found")
    rnd = random.Random(plate)
    v = {"registration_number": plate, **(MOCK_VEHICLES.get(plate) or {
        "make_model": rnd.choice(["Toyota Land Cruiser GXR", "Hyundai Elantra Smart", "Nissan Patrol LE", "Kia Sportage",
                                  "Toyota Camry GLE", "Hyundai Sonata", "Lucid Air Pure", "Chevrolet Tahoe"]),
        "model_year": rnd.randint(2016, 2025), "colour": rnd.choice(["White", "Silver", "Black", "Grey"]),
        "body": "Private", "registration_expiry": (date.today() + timedelta(days=rnd.randint(30, 700))).isoformat()})}
    v["vehicle_type"] = vehicle_type_of(v)
    v["vehicle_age"] = max(0, date.today().year - int(v["model_year"])) if v.get("model_year") else 0
    return v


def lookup_vehicle(session_id: str, vehicle_number: str, tool_call_id: str | None = None) -> dict[str, Any]:
    """Elm vehicle lookup (simulated) for a customer who is already verified."""
    if not normalize_plate(vehicle_number):
        raise IdentityError("That doesn't look like a Saudi plate (e.g. 7788 BDR) or a 9-digit sequence number.")

    def step(k: str, step_label: str, source: str, lo: float, hi: float, detail_ok: str) -> None:
        progress(tool_call_id, k, step_label)
        _sleep(lo, hi)
        progress(tool_call_id, k, step_label, "done", detail_ok)

    v = _vehicle(vehicle_number, step)
    session_store.get(session_id).extra["vehicle"] = v
    return {"vehicle": v}


# ------------------------------------------------------------------ new customers
def fetch_kyc(session_id: str, id_type: str | None, id_number: str, consent: bool,
              vehicle_number: str | None = None, tool_call_id: str | None = None,
              full_name: str | None = None) -> dict[str, Any]:
    if not consent:
        raise IdentityError("Customer consent is required before fetching identity data from government sources.")
    t, n = normalize_id(id_type, id_number)
    label = ID_TYPES[t]
    key = f"{t}:{n}"
    h = id_hash(t, n)
    lookups: list[dict[str, Any]] = []

    def step(k: str, step_label: str, source: str, lo: float, hi: float, detail_ok: str) -> None:
        progress(tool_call_id, k, step_label)
        t0 = time.time()
        _sleep(lo, hi)
        progress(tool_call_id, k, step_label, "done", detail_ok)
        lookups.append({"key": k, "label": step_label, "source": source, "status": "done", "detail": detail_ok,
                        "ms": int((time.time() - t0) * 1000)})

    step("consent", "Recording customer consent", "Consent manager", 0.1, 0.2, "Consent captured for identity check")
    step("validate", f"Validating {label} number", "Local validation", 0.1, 0.2, f"{label} {mask_id(t, n)} is well-formed")

    existing = excel_store.find_by_id_hash(h)
    if existing:
        progress(tool_call_id, "dedupe", f"{CRM} · checking for an existing profile", "done", f"Already registered as {existing['customer_id']}")
        sess = session_store.bind(session_id, existing["customer_id"], existing["name"], f"{label} match (already registered)")
        vehicle = _vehicle(vehicle_number, step)
        if vehicle:
            sess.extra["vehicle"] = vehicle
        remember_profile(session_id, existing)
        return {"already_registered": True, "customer": _customer_card(existing, f"{label} match"), "vehicle": vehicle}

    nafath_no = random.randint(10, 99)
    step("nafath", "Sending Nafath authentication request", "Nafath (National Single Sign-On) — simulated",
         0.9, 1.4, f"Approved in the Nafath app · number {nafath_no}")
    step("yakeen", "Fetching identity data from Yakeen (Elm)", "Yakeen identity verification (Elm) — simulated",
         0.5, 0.9, "Name, date of birth, nationality, ID validity")
    step("address", "Fetching National Address", "National Address (Saudi Post / SPL) — simulated",
         0.3, 0.6, "Registered short address verified")

    step("dedupe", f"{CRM} · checking for an existing profile", "CRM", 0.15, 0.3, "No existing profile — new customer")
    person = dict(MOCK_REGISTRY.get(key) or _synthetic(key))
    given = re.sub(r"\s+", " ", (full_name or "")).strip().title()
    name_match = None
    if given:
        if re.search(r"[\u0600-\u06FF]", given):  # Arabic-script name vs Latin record — can't compare reliably
            name_match = None
        elif key in MOCK_REGISTRY:  # real (mock) record: compare first names
            name_match = given.split()[0].lower() == person["name"].split()[0].lower()
        if key not in MOCK_REGISTRY:  # synthetic record takes the name the customer gave
            person["name"], name_match = given, True
    vehicle = _vehicle(vehicle_number, step)
    draft = {
        **person,
        "id_type": label, "id_reference": mask_id(t, n), "id_hash": h,
        "id_expiry": (date.today() + timedelta(days=random.Random(key).randint(200, 1500))).isoformat(),
        "kyc_source": "Nafath + Yakeen (Elm) + National Address (SPL) — simulated",
        "vehicle": vehicle,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "lookups": lookups,
        "name_match": name_match,
    }
    session_store.get(session_id).kyc_draft = draft
    public = {k: v for k, v in draft.items() if k != "id_hash"}
    return {"draft": public, "simulated": True,
            "next_step": "Show these details to the customer and ask them to confirm or correct them. "
                         "Then call confirm_registration."}


EDITABLE = {"name", "address", "phone", "email", "city", "date_of_birth"}


def confirm_registration(session_id: str, confirm: bool, corrections: dict[str, Any] | None = None,
                         tool_call_id: str | None = None) -> dict[str, Any]:
    s = session_store.get(session_id)
    if s.customer_id and not s.kyc_draft:
        raise IdentityError(f"This chat is already verified as {s.customer_id}.")
    draft = s.kyc_draft
    if not draft:
        raise IdentityError("There are no fetched identity details to confirm yet. Fetch them first.")
    fixes = {k: str(v).strip() for k, v in (corrections or {}).items() if k in EDITABLE and v}
    if fixes:
        draft.update(fixes)
        draft.setdefault("customer_corrections", []).extend(sorted(fixes))
    if not confirm:
        return {"registered": False, "draft": {k: v for k, v in draft.items() if k != "id_hash"},
                "message": "Updated the details. Ask the customer to confirm again." if fixes
                else "Not registered. Ask the customer what needs correcting."}

    progress(tool_call_id, "create", f"{CRM} · creating customer profile")
    cid = excel_store.next_id()
    today = date.today().isoformat()
    record = {
        "customer_id": cid, "name": draft["name"], "phone": draft.get("phone", ""), "email": draft.get("email", ""),
        "address": draft.get("address", ""), "city": draft.get("city", ""), "date_of_birth": draft.get("date_of_birth", ""),
        "nationality": draft.get("nationality", ""),
        "segment": "Retail", "kyc_status": "Verified", "customer_since": today,
        "id_type": draft["id_type"], "id_reference": draft["id_reference"], "id_hash": draft["id_hash"],
        "kyc_source": draft["kyc_source"], "onboarded_via": "AI Copilot chat",
        "registered_at": datetime.now().isoformat(timespec="seconds"),
    }
    progress(tool_call_id, "create", f"{CRM} · creating customer profile", "done", cid)
    progress(tool_call_id, "excel", "Writing to Customer 360 (art_customer_360.xlsx)")
    result = excel_store.add_customer(record)
    if result["synced"]:
        progress(tool_call_id, "excel", "Writing to Customer 360 (art_customer_360.xlsx)", "done", "Row added to Customers sheet")
    else:
        progress(tool_call_id, "excel", "Writing to Customer 360 (art_customer_360.xlsx)", "error", result.get("warning"))
    vehicle = draft.get("vehicle")
    session_store.bind(session_id, cid, draft["name"], f"new registration ({draft['id_type']} + Nafath)", new=True)
    remember_profile(session_id, record)
    if vehicle:
        session_store.get(session_id).extra["vehicle"] = vehicle
    card = _customer_card(record, f"new registration ({draft['id_type']} + Nafath)")
    return {"registered": True, "customer": card, "vehicle": vehicle,
            "excel": {"synced": result["synced"], "warning": result.get("warning"), "file": "art_customer_360.xlsx"}}
