"""Deterministic GENERAL insurance rating engine — home & property, Saudi Arabia (illustrative).

Premium = building value × building rate + contents value × contents rate
        × plan tier × villa loading × flood-zone loading, + 15% VAT.
"""
from __future__ import annotations

import re
from typing import Any

VAT = 0.15

PLANS: dict[str, dict[str, Any]] = {
    "home_basic": {
        "plan": "Home Basic", "struct_rate": 0.00045, "contents_rate": 0.0, "factor": 1.0,
        "summary": "Protects the building against fire, flood, storm and other perils.",
        "includes": ["Building against fire, lightning, explosion", "Flood, storm, rain and sandstorm damage",
                     "Riot, strike and malicious damage", "Water-tank and pipe bursts", "Impact by vehicles"],
        "excludes": ["Contents and belongings", "Burglary and theft", "Jewellery and valuables"],
    },
    "home_plus": {
        "plan": "Home Plus", "struct_rate": 0.00045, "contents_rate": 0.0016, "factor": 1.12,
        "summary": "Building plus your belongings — furniture, electronics and appliances — including burglary.",
        "includes": ["Everything in Home Basic", "Contents: furniture, electronics, appliances, air-conditioners",
                     "Burglary and theft with forcible entry", "Accidental damage to TVs and appliances",
                     "Alternative accommodation up to 6 months"],
        "excludes": ["Jewellery and valuables above SAR 10,000", "Wear and tear", "Home unoccupied beyond 60 days"],
    },
    "home_premier": {
        "plan": "Home Premier", "struct_rate": 0.00045, "contents_rate": 0.0016, "factor": 1.45,
        "summary": "Complete protection — valuables, personal liability, domestic workers and 12 months' rent.",
        "includes": ["Everything in Home Plus", "Jewellery and valuables up to 20% of contents",
                     "Personal liability up to SAR 500,000", "Alternative accommodation up to 12 months",
                     "Domestic workers' personal accident", "Breakdown of AC units and appliances"],
        "excludes": ["Wear and tear", "Home unoccupied beyond 90 days", "Wilful damage"],
    },
}
PLAN_ALIASES = {"building only": "home_basic", "structure only": "home_basic", "basic": "home_basic",
                "plus": "home_plus", "contents": "home_plus", "premier": "home_premier",
                "complete": "home_premier", "maximum": "home_premier"}
FLOOD_PRONE = {"jeddah", "jazan", "jizan", "makkah", "mecca", "abha", "al baha"}
PROPERTY_TYPES = {"apartment": "Apartment", "independent": "Villa / independent house"}


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


def normalize_property(text: str | None) -> str:
    t = (text or "").lower()
    if re.search(r"independent|villa|house|duplex|palace|townhouse", t) and "apartment" not in t and "flat" not in t:
        return "independent"
    return "apartment"


def _price(ptype: str, building: float, contents: float, city: str, plan: str) -> dict[str, Any]:
    pl = PLANS[plan]
    struct = building * pl["struct_rate"] * (1.15 if ptype == "independent" else 1.0)
    cont = contents * pl["contents_rate"]
    tier = (struct + cont) * (pl["factor"] - 1)
    flood = (struct + cont + tier) * (0.10 if city.lower() in FLOOD_PRONE else 0.0)
    net = max(struct + cont + tier + flood, 250.0)  # minimum premium
    vat = net * VAT
    return {"structure": round(struct), "contents": round(cont), "extensions": round(tier), "flood_loading": round(flood),
            "net_premium": round(net), "gst": round(vat), "total_premium": round(net + vat)}


def recommend(contents: float, building: float) -> tuple[str, str]:
    if contents <= 0:
        return "home_basic", "You're insuring just the building, so Home Basic covers what you need."
    if contents >= 300_000 or building >= 3_000_000:
        return "home_premier", "With valuable contents, Home Premier adds jewellery, liability and longer rent cover."
    return "home_plus", "Home Plus protects both your home and belongings, including burglary."


def calculate_quote(property_type: str, building_value: float, contents_value: float, city: str,
                    plan: str | None = None) -> dict[str, Any]:
    ptype = normalize_property(property_type)
    building = float(building_value or 0)
    contents = float(contents_value or 0)
    if building < 100_000 and contents <= 0:
        raise ValueError("Please share the rebuilding value of the home (at least SAR 100,000) or the contents value.")
    city = (city or "Riyadh").strip().title()
    rec_plan, rec_reason = recommend(contents, building)
    code = normalize_plan(plan) or rec_plan
    p = _price(ptype, building, contents, city, code)
    flood = city.lower() in FLOOD_PRONE
    score = int(max(5, min(20 + (22 if flood else 0) + (10 if ptype == "independent" else 0)
                           + min(contents / 50_000, 15), 95)))
    band = "Low" if score < 40 else "Medium" if score < 65 else "High"
    factors = [PROPERTY_TYPES[ptype] + (" — standalone buildings carry a 15% loading" if ptype == "independent" else "")]
    factors.append(f"{city} has flash-flood exposure — 10% loading" if flood else f"{city} has no flood loading")
    if contents:
        factors.append(f"Contents of SAR {contents:,.0f}" + (" covered against burglary" if code != "home_basic"
                                                             else " are NOT covered on Home Basic"))
    breakdown = [("Building", p["structure"]), ("Contents", p["contents"]), ("Plan extensions", p["extensions"]),
                 ("Flood-zone loading", p["flood_loading"]), ("VAT (15%)", p["gst"])]
    cont_txt = f" + contents SAR {contents:,.0f}" if contents and code != "home_basic" else ""
    return {
        "line": "general",
        "params": {"property_type": ptype, "building_value": building, "contents_value": contents, "city": city},
        "subject": f"{PROPERTY_TYPES[ptype]} · {city}",
        "sum_insured": building + (contents if code != "home_basic" else 0),
        "sum_insured_label": f"Building SAR {building:,.0f}{cont_txt}",
        "breakdown": [{"label": k, "amount": v} for k, v in breakdown if v],
        "gst_note": "Contribution includes 15% VAT.",
        "location": city, "zone": "Flood-prone" if flood else "Standard",
        "coverage": code, "plan": PLANS[code]["plan"], "plan_summary": PLANS[code]["summary"],
        "coverage_details": {"includes": PLANS[code]["includes"], "excludes": PLANS[code]["excludes"]},
        "premium": {**p, "idv": 0},
        "risk": {"score": score, "band": band, "factors": factors},
        "recommendation": {"coverage": rec_plan, "plan": PLANS[rec_plan]["plan"], "reason": rec_reason},
        "alternatives": [{"coverage": k, "plan": v["plan"], "recommended": k == rec_plan,
                          "total_premium": _price(ptype, building, contents, city, k)["total_premium"]}
                         for k, v in PLANS.items()],
        "adjustables": [
            {"key": "building_value", "label": "Building rebuild value", "type": "range", "min": 100_000,
             "max": max(6_000_000, building), "step": 50_000, "value": building, "unit": "SAR"},
            {"key": "contents_value", "label": "Contents value", "type": "range", "min": 0,
             "max": max(1_500_000, contents), "step": 10_000, "value": contents, "unit": "SAR",
             "hint": "Not covered on Home Basic" if code == "home_basic" else None},
        ],
        "validity_days": 15,
    }


def underwrite(params: dict[str, Any], plan: str) -> list[str]:
    issues = []
    if params["building_value"] > 10_000_000:
        issues.append("Properties valued above SAR 10 million need a survey — our team will arrange it before issuing.")
    return issues
