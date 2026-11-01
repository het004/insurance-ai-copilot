"""Deterministic life (term protection) rating engine — Saudi Arabia (illustrative).

Annual premium = sum assured × mortality rate per mille at the mid-term age × smoker factor × plan factor.
VAT: life insurance contracts are EXEMPT (ZATCA insurance guideline, Art. 29(8)) — no VAT is added.
"""
from __future__ import annotations

import re
from typing import Any

MAX_EXPIRY_AGE = 70

PLANS: dict[str, dict[str, Any]] = {
    "life_protect": {
        "plan": "Life Protect", "factor": 1.0,
        "summary": "Pure protection — a lump sum to your family if you pass away during the term.",
        "includes": ["Death benefit: full sum covered", "Level contribution for the whole term",
                     "Cover worldwide, 24/7", "Beneficiaries of your choice"],
        "excludes": ["Suicide in the first year", "Death due to undisclosed pre-existing conditions",
                     "War and hazardous activities not declared"],
    },
    "life_protect_plus": {
        "plan": "Life Protect Plus", "factor": 1.35,
        "summary": "Protection plus living benefits — critical illness and double cover for accidents.",
        "includes": ["Everything in Life Protect", "Critical illness: 50% of sum covered paid on diagnosis (30 illnesses)",
                     "Accidental death: double sum covered", "Total permanent disability: full sum covered"],
        "excludes": ["Critical illness in the first 90 days", "Suicide in the first year", "Self-inflicted injury"],
    },
    "life_premier": {
        "plan": "Life Premier", "factor": 1.75,
        "summary": "Complete family protection — waiver of contributions, income benefit and family cover.",
        "includes": ["Everything in Life Protect Plus", "Waiver of contributions on disability or critical illness",
                     "Family income benefit: 1% of sum covered monthly for 2 years", "Spouse cover: 25% of sum covered",
                     "Terminal illness: early payment of full sum covered"],
        "excludes": ["Critical illness in the first 90 days", "Suicide in the first year"],
    },
}
PLAN_ALIASES = {"protect plus": "life_protect_plus", "plus": "life_protect_plus", "critical illness": "life_protect_plus",
                "premier": "life_premier", "complete": "life_premier", "maximum": "life_premier",
                "basic": "life_protect", "pure": "life_protect", "term": "life_protect", "protect": "life_protect"}
TERMS = [10, 15, 20, 25, 30]


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


def rate_per_mille(age: float) -> float:
    """Illustrative annual mortality-based rate per SAR 1,000 sum assured."""
    return 0.42 * (1.088 ** (age - 25))


def recommend(age: int, smoker: bool, has_family: bool) -> tuple[str, str]:
    if age >= 45 or smoker:
        return "life_protect_plus", "Critical-illness cover matters more from mid-life — Life Protect Plus pays 50% on diagnosis."
    if has_family:
        return "life_premier", "With dependants, Life Premier adds income benefit, spouse cover and waiver of contributions."
    return "life_protect", "Young and healthy — Life Protect gives the most cover for the lowest contribution."


def recommend_cover(age: int) -> int:
    return 2_000_000 if age < 35 else 1_500_000 if age < 45 else 1_000_000


def _price(age: int, smoker: bool, cover: float, term: int, plan: str) -> dict[str, Any]:
    mid = age + term / 2
    base = cover / 1000 * rate_per_mille(mid)
    smoker_load = base * (0.6 if smoker else 0.0)
    rider = (base + smoker_load) * (PLANS[plan]["factor"] - 1)
    policy_fee = 0.0
    net = base + smoker_load + rider + policy_fee
    return {"mortality": round(base), "smoker_loading": round(smoker_load), "riders": round(rider),
            "net_premium": round(net), "gst": 0, "total_premium": round(net)}


def calculate_quote(age: int, sum_assured: float | None = None, term_years: int | None = None, smoker: bool = False,
                    plan: str | None = None, has_family: bool = True, city: str | None = None) -> dict[str, Any]:
    age = int(age)
    if not 18 <= age <= 65:
        raise ValueError("Life cover can be bought online between ages 18 and 65.")
    cover = float(sum_assured) if sum_assured else float(recommend_cover(age))
    if not 100_000 <= cover <= 10_000_000:
        raise ValueError("Sum covered must be between SAR 100,000 and SAR 10,000,000.")
    term = int(term_years or min(20, MAX_EXPIRY_AGE - age))
    term = min(TERMS, key=lambda t: abs(t - term)) if term >= 10 else 10
    if age + term > MAX_EXPIRY_AGE:
        term = max(t for t in TERMS if age + t <= MAX_EXPIRY_AGE) if age + 10 <= MAX_EXPIRY_AGE else 5
    rec_plan, rec_reason = recommend(age, smoker, has_family)
    code = normalize_plan(plan) or rec_plan
    p = _price(age, smoker, cover, term, code)
    score = int(max(5, min(10 + age * 0.8 + (25 if smoker else 0) + cover / 400_000, 95)))
    band = "Low" if score < 40 else "Medium" if score < 65 else "High"
    factors = [f"Age {age} at entry · cover until age {age + term}"]
    factors.append("Smoker: 60% loading" if smoker else "Non-smoker rates")
    if cover > 3_000_000:
        factors.append("High sum assured — financial underwriting applies")
    breakdown = [("Life cover", p["mortality"]), ("Smoker loading", p["smoker_loading"]),
                 ("Plan riders", p["riders"])]
    who = f"Age {age} · {'smoker' if smoker else 'non-smoker'} · {term}-year term"
    return {
        "line": "life",
        "params": {"age": age, "sum_assured": cover, "term_years": term, "smoker": bool(smoker),
                   "has_family": bool(has_family), "city": city or ""},
        "subject": who,
        "sum_insured": cover,
        "sum_insured_label": f"Sum covered SAR {cover:,.0f}",
        "breakdown": [{"label": k, "amount": v} for k, v in breakdown if v],
        "gst_note": "Life insurance is VAT-exempt in Saudi Arabia.",
        "location": city or "", "zone": "",
        "coverage": code, "plan": PLANS[code]["plan"], "plan_summary": PLANS[code]["summary"],
        "coverage_details": {"includes": PLANS[code]["includes"], "excludes": PLANS[code]["excludes"]},
        "premium": {**p, "idv": 0},
        "risk": {"score": score, "band": band, "factors": factors},
        "recommendation": {"coverage": rec_plan, "plan": PLANS[rec_plan]["plan"], "reason": rec_reason,
                           "sum_assured": recommend_cover(age)},
        "alternatives": [{"coverage": k, "plan": v["plan"], "recommended": k == rec_plan,
                          "total_premium": _price(age, smoker, cover, term, k)["total_premium"]} for k, v in PLANS.items()],
        "adjustables": [
            {"key": "sum_assured", "label": "Sum covered", "type": "range", "min": 100_000, "max": 5_000_000,
             "step": 50_000, "value": cover, "unit": "SAR"},
            {"key": "term_years", "label": "Term", "type": "select", "value": term, "unit": "years",
             "options": [{"value": t, "label": f"{t} years"} for t in TERMS if age + t <= MAX_EXPIRY_AGE]},
        ],
        "validity_days": 15,
    }


def underwrite(params: dict[str, Any], plan: str) -> list[str]:
    issues = []
    if params["age"] > 55 or params["sum_assured"] > 3_000_000:
        issues.append("This combination of age and sum covered needs a medical examination — our team will "
                      "arrange it at a partner clinic before the policy is issued.")
    return issues
