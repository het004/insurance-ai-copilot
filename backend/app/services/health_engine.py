"""Deterministic health rating engine — Saudi Arabia (illustrative, CCHI-style tiers).

INDIVIDUAL plans only. Plans differ by provider network, co-payment and annual limit.
Contribution = base for the participant's age band × plan tier × city factor × chronic-condition loading, + 15% VAT
(ZATCA: health insurance is standard-rated).
"""
from __future__ import annotations

import re
from typing import Any

VAT = 0.15

PLANS: dict[str, dict[str, Any]] = {
    "health_essential": {
        "plan": "Health Essential", "factor": 0.78, "limit": 1_000_000,
        "summary": "Essential benefits at an affordable price — inpatient, outpatient, maternity and emergency.",
        "includes": ["Annual limit SAR 1,000,000", "Network: 1,200+ hospitals & clinics (Class C)",
                     "Outpatient co-pay 20% (max SAR 100 per visit)", "Maternity cover",
                     "Emergency treatment anywhere in the Kingdom", "Chronic conditions covered on declaration"],
        "excludes": ["Private room (shared ward)", "Dental beyond emergency", "Optical", "Treatment outside KSA"],
    },
    "health_gold": {
        "plan": "Health Gold", "factor": 1.0, "limit": 1_000_000,
        "summary": "Our most popular plan — private room, wider network and low co-pay.",
        "includes": ["Annual limit SAR 1,000,000", "Network: 2,000+ hospitals & clinics incl. major private hospitals (Class B)",
                     "Private room", "Outpatient co-pay 10%", "Dental up to SAR 2,000 and optical up to SAR 750",
                     "Maternity cover", "Telemedicine 24/7"],
        "excludes": ["Cosmetic treatment", "Treatment outside KSA (except emergencies in GCC)"],
    },
    "health_premier": {
        "plan": "Health Premier", "factor": 1.45, "limit": 5_000_000,
        "summary": "VIP cover — top hospitals, no co-pay and worldwide emergency cover.",
        "includes": ["Annual limit SAR 5,000,000", "Network: all hospitals incl. VIP tier (Class A / VIP)",
                     "No co-pay", "Private suite", "Dental up to SAR 5,000 and optical up to SAR 1,500",
                     "Worldwide emergency cover", "Second medical opinion abroad"],
        "excludes": ["Cosmetic treatment", "Experimental treatments"],
    },
}
PLAN_ALIASES = {"essential": "health_essential", "basic": "health_essential", "class c": "health_essential",
                "economy": "health_essential", "gold": "health_gold", "standard": "health_gold", "class b": "health_gold",
                "premier": "health_premier", "vip": "health_premier", "platinum": "health_premier",
                "class a": "health_premier", "maximum": "health_premier"}

# annual base premium for one adult on Health Gold by age band (SAR, before city/loadings)
AGE_BANDS = [(25, 3_200), (35, 3_900), (45, 5_200), (55, 7_800), (60, 10_400), (65, 13_500), (120, 18_000)]
CITY_FACTOR = {"riyadh": 1.0, "jeddah": 1.0, "makkah": 0.97, "mecca": 0.97, "dammam": 0.98, "khobar": 0.98,
               "al khobar": 0.98, "dhahran": 0.98, "madinah": 0.95, "medina": 0.95}


def normalize_plan(text: str | None) -> str | None:
    if not text:
        return None
    t = text.strip().lower().replace("-", " ")
    if t.replace(" ", "_") in PLANS:
        return t.replace(" ", "_")
    for name, code in sorted(((v["plan"].lower(), k) for k, v in PLANS.items()), key=lambda x: -len(x[0])):
        if name in t:
            return code
    for k, v in sorted(PLAN_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{k}\b", t):
            return v
    return None


def _base(age: int) -> int:
    return next(p for limit, p in AGE_BANDS if age <= limit)


def city_factor(city: str) -> float:
    return CITY_FACTOR.get(city.lower(), 0.92)


def recommend(age: int, chronic: bool) -> tuple[str, str]:
    if age >= 50 or chronic:
        return "health_gold", "Health Gold's wider network and 10% co-pay keep regular visits affordable."
    if age < 30:
        return "health_essential", "Young and healthy — Health Essential covers what matters at the lowest price."
    return "health_gold", "Health Gold balances price, network and benefits well at your age."


COPAY_FACTOR = {0: 1.15, 10: 1.0, 20: 0.88}       # outpatient co-pay → contribution factor
DEFAULT_COPAY = {"health_essential": 20, "health_gold": 10, "health_premier": 0}
MATERNITY_LOAD = 0.08


def _price(age: int, city: str, plan: str, chronic: bool, copay: int | None = None,
           maternity: bool = True) -> dict[str, Any]:
    cp = DEFAULT_COPAY[plan] if copay is None else copay
    base = _base(age) * PLANS[plan]["factor"] * COPAY_FACTOR.get(cp, 1.0) / COPAY_FACTOR[DEFAULT_COPAY[plan]] \
        * (1 if maternity else 1 - MATERNITY_LOAD)
    city_adj = base * (city_factor(city) - 1)
    chronic_load = (base + city_adj) * (0.15 if chronic else 0.0)
    net = base + city_adj + chronic_load
    vat = net * VAT
    return {"base_contribution": round(base), "zone_adjustment": round(city_adj), "ped_loading": round(chronic_load),
            "net_premium": round(net), "gst": round(vat), "total_premium": round(net + vat)}


def calculate_quote(age: int, city: str, plan: str | None = None, pre_existing: bool = False,
                    copay: int | None = None, maternity: bool = True) -> dict[str, Any]:
    """Individual health plan (one participant)."""
    age = int(age)
    if not 18 <= age <= 75:
        raise ValueError("Individual health plans are available online from age 18 to 75.")
    city = (city or "Riyadh").strip().title()
    rec_plan, rec_reason = recommend(age, pre_existing)
    code = normalize_plan(plan) or rec_plan
    cp = DEFAULT_COPAY[code] if copay is None else min(COPAY_FACTOR, key=lambda c: abs(c - int(copay)))
    p = _price(age, city, code, pre_existing, cp, maternity)
    score = int(max(5, min(15 + age * 0.7 + (14 if pre_existing else 0), 95)))
    band = "Low" if score < 40 else "Medium" if score < 65 else "High"
    factors = [f"Age {age} — contributions step up by age band"]
    if pre_existing:
        factors.append("Declared chronic condition: 15% loading, covered from day one")
    factors.append(f"{city} hospital-cost factor {city_factor(city):.2f}")
    limit = PLANS[code]["limit"]
    breakdown = [("Base contribution", p["base_contribution"]), ("City adjustment", p["zone_adjustment"]),
                 ("Chronic-condition loading", p["ped_loading"]), ("VAT (15%)", p["gst"])]
    return {
        "line": "health",
        "params": {"age": age, "city": city, "pre_existing": bool(pre_existing), "copay": cp, "maternity": bool(maternity)},
        "subject": f"Individual · age {age} · {city}",
        "sum_insured": limit,
        "sum_insured_label": f"Annual limit SAR {limit:,}",
        "breakdown": [{"label": k, "amount": v} for k, v in breakdown if v],
        "gst_note": "Contribution includes 15% VAT.",
        "location": city, "zone": city,
        "coverage": code, "plan": PLANS[code]["plan"], "plan_summary": PLANS[code]["summary"],
        "coverage_details": {"includes": PLANS[code]["includes"], "excludes": PLANS[code]["excludes"]},
        "premium": {**p, "idv": 0},
        "risk": {"score": score, "band": band, "factors": factors},
        "recommendation": {"coverage": rec_plan, "plan": PLANS[rec_plan]["plan"], "reason": rec_reason},
        "alternatives": [{"coverage": k, "plan": v["plan"], "recommended": k == rec_plan,
                          "total_premium": _price(age, city, k, pre_existing, None, maternity)["total_premium"]}
                         for k, v in PLANS.items()],
        "adjustables": [
            {"key": "copay", "label": "Outpatient co-pay", "type": "select", "value": cp,
             "options": [{"value": c, "label": f"{c}%" + (" (no co-pay)" if c == 0 else "")} for c in COPAY_FACTOR]},
            {"key": "maternity", "label": "Maternity cover", "type": "toggle", "value": bool(maternity),
             "hint": "Adds about 8%"},
        ],
        "validity_days": 15,
    }


def underwrite(params: dict[str, Any], plan: str) -> list[str]:
    issues = []
    if int(params.get("age") or params.get("eldest_age") or 0) > 65:
        issues.append("Participants over 65 need a medical declaration review before we can issue online — "
                      "our team will call you within one working day.")
    return issues
