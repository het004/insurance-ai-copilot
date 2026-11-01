"""Deterministic motor rating engine — Saudi Arabia (illustrative).

Contribution = own damage (vehicle market value × OD rate × city zone × age factor, less No Claim Discount)
        + third-party liability (TPL) + plan add-ons, + 15% VAT (ZATCA standard rate for general insurance).
The LLM never invents prices: generate_quote() calls this.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

VAT = 0.15

# new-vehicle market value (SAR), TPL premium (SAR), own-damage rate
VEHICLES: dict[str, dict[str, Any]] = {
    "car":        {"label": "Private Car",        "new_value": 95_000,  "tp": 950,   "od_rate": 0.026},
    "suv":        {"label": "SUV",                "new_value": 180_000, "tp": 1_250, "od_rate": 0.024},
    "ev":         {"label": "Electric Car",       "new_value": 190_000, "tp": 900,   "od_rate": 0.027},
    "bike":       {"label": "Motorcycle",         "new_value": 30_000,  "tp": 480,   "od_rate": 0.040},
}

VEHICLE_ALIASES = {
    "car": "car", "sedan": "car", "saloon": "car", "hatchback": "car", "private car": "car",
    "suv": "suv", "4x4": "suv", "jeep": "suv", "land cruiser": "suv", "patrol": "suv", "pickup": "suv", "pick-up": "suv",
    "ev": "ev", "electric": "ev", "electric car": "ev", "tesla": "ev", "lucid": "ev",
    "bike": "bike", "motorcycle": "bike", "motorbike": "bike", "scooter": "bike",
}

COVERAGES: dict[str, dict[str, Any]] = {
    "tpl": {
        "plan": "Motor TPL",
        "summary": "Mandatory third-party liability cover — required for Istimara renewal and road use in the Kingdom.",
        "includes": ["Third-party bodily injury and death (diya) up to SAR 10 million",
                     "Third-party property damage", "Linked to Najm accident reporting"],
        "excludes": ["Damage to your own vehicle", "Theft of your vehicle", "Flood and natural perils to your vehicle"],
    },
    "comprehensive": {
        "plan": "Motor Comprehensive",
        "summary": "Your own vehicle plus third-party liability, repaired at our approved workshops.",
        "includes": ["Own damage: collision, overturning, fire, theft", "Floods, storms and sandstorms",
                     "All third-party liabilities", "24/7 roadside assistance and towing",
                     "Repairs at approved workshops"],
        "excludes": ["Agency (dealer) repair", "Depreciation on parts at claim", "Driving outside the GCC"],
    },
    "comprehensive_plus": {
        "plan": "Motor Comprehensive Plus",
        "summary": "Maximum protection — agency repair, no depreciation on parts, replacement car and GCC cover.",
        "includes": ["Everything in Motor Comprehensive", "Agency (dealer) repair for vehicles up to 5 years",
                     "No depreciation deducted on replaced parts", "Replacement car up to 10 days",
                     "GCC & Bahrain causeway cover", "Personal accident for driver and passengers"],
        "excludes": ["Unlicensed or under-age driver", "Wear and tear, mechanical breakdown", "Racing and off-road events"],
    },
}

COVERAGE_ALIASES = {
    "tpl": "tpl", "third party": "tpl", "third-party": "tpl", "third_party": "tpl", "liability": "tpl",
    "mandatory": "tpl", "basic": "tpl", "cheapest": "tpl", "minimum": "tpl",
    "comprehensive plus": "comprehensive_plus", "comprehensive_plus": "comprehensive_plus", "agency": "comprehensive_plus",
    "plus": "comprehensive_plus", "maximum": "comprehensive_plus", "zero dep": "comprehensive_plus",
    "full cover": "comprehensive_plus",
    "comprehensive": "comprehensive", "standard": "comprehensive", "workshop": "comprehensive", "full": "comprehensive",
}

ZONE_A = {"riyadh", "jeddah", "makkah", "mecca", "dammam", "khobar", "al khobar", "dhahran"}
CITIES = ["riyadh", "jeddah", "makkah", "mecca", "madinah", "medina", "dammam", "khobar", "al khobar", "dhahran",
          "taif", "abha", "tabuk", "buraidah", "khamis mushait", "hail", "jazan", "jizan", "najran", "al ahsa",
          "hofuf", "jubail", "yanbu", "qatif", "al kharj", "sakaka", "arar", "al baha", "unaizah", "neom"]

NCD_SLABS = [0, 15, 20, 25, 30]  # No Claim Discount for 0, 1, 2, 3, 4+ claim-free years


def normalize_vehicle(v: str | None) -> str | None:
    if not v:
        return None
    v = v.strip().lower()
    if v in VEHICLES:
        return v
    for k, val in sorted(VEHICLE_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(k)}\b", v):
            return val
    return None


def normalize_coverage(c: str | None) -> str | None:
    if not c:
        return None
    t = c.strip().lower().replace("-", " ").replace("_", " ")
    if t.replace(" ", "_") in COVERAGES:
        return t.replace(" ", "_")
    for name, code in sorted(((v["plan"].lower(), k) for k, v in COVERAGES.items()), key=lambda x: -len(x[0])):
        if name in t:
            return code
    for k, val in sorted(COVERAGE_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(k.replace('_', ' '))}\b", t):
            return val
    return None


def market_value_factor(age: float) -> float:
    """Vehicle market value as a share of new value (approx. 15% a year, floor 25%)."""
    return max(0.25, 0.95 * (0.85 ** age)) if age > 0 else 1.0


def risk_score(vtype: str, age: float, city: str, coverage: str) -> tuple[int, str, list[str]]:
    score, factors = 25, []
    if city.lower() in ZONE_A:
        score += 14
        factors.append(f"{city.title()} is a high-traffic city (Zone A)")
    else:
        factors.append(f"{city.title()} is a Zone B city — lower claim frequency")
    age_pts = min(int(age * 3), 24)
    score += age_pts
    if age_pts >= 12:
        factors.append(f"Vehicle age of {age:g} years raises breakdown and parts risk")
    type_pts = {"suv": 8, "bike": 18, "commercial": 16, "ev": 9, "car": 5}[vtype]
    score += type_pts
    if vtype in {"bike", "commercial"}:
        factors.append(f"{VEHICLES[vtype]['label']} segment has higher accident frequency")
    if vtype == "ev":
        factors.append("EV battery and parts are costly — agency repair recommended")
    if coverage == "tpl":
        score += 6
        factors.append("TPL only leaves your own vehicle uninsured")
    score = max(5, min(score, 95))
    band = "Low" if score < 40 else "Medium" if score < 65 else "High"
    return score, band, factors


def recommend_coverage(age: float, vtype: str) -> tuple[str, str]:
    if age <= 3:
        return "comprehensive_plus", ("Your vehicle is under 3 years old — agency repair and no depreciation keep "
                                      "it in showroom condition after a claim.")
    if age <= 10:
        return "comprehensive", "Motor Comprehensive balances price and protection for a vehicle of this age."
    return "comprehensive", "Older vehicles still face theft, flood and sandstorm risk — comprehensive is the sensible floor."


DEDUCTIBLES = {500: 0.0, 1000: 0.05, 2000: 0.10, 3000: 0.15}  # excess per claim → own-damage discount


def market_value(vtype: str, age: float) -> float:
    return round(VEHICLES[vtype]["new_value"] * market_value_factor(age), -2)


def _price(vtype: str, age: float, coverage: str, city: str, ncd: int, insured_value: float | None = None,
           deductible: int = 500) -> dict[str, Any]:
    v = VEHICLES[vtype]
    value = round(insured_value or market_value(vtype, age), -2)
    zone_factor = 1.0 if city.lower() in ZONE_A else 0.92
    age_factor = 1.0 + (0.08 if age > 5 else 0) + (0.07 if age > 10 else 0)
    tp = float(v["tp"])
    od = addons = ncd_amt = 0.0
    if coverage != "tpl":
        od = value * v["od_rate"] * zone_factor * age_factor * (1 - DEDUCTIBLES.get(int(deductible), 0.0))
        ncd_amt = od * ncd / 100
        od -= ncd_amt
        if coverage == "comprehensive_plus":
            addons = od * 0.35 + 150  # agency repair, nil depreciation, replacement car, GCC, PA
    net = od + tp + addons
    vat = net * VAT
    return {
        "idv": value if coverage != "tpl" else 0,  # insured (market) value
        "own_damage": round(od), "ncb_discount": round(ncd_amt), "third_party": round(tp),
        "personal_accident": 0, "add_ons": round(addons),
        "net_premium": round(net), "gst": round(vat), "total_premium": round(net + vat),
    }


def calculate_quote(vehicle_type: str, vehicle_age: float, coverage: str, location: str,
                    ncb_percent: int = 0, insured_value: float | None = None, deductible: int = 500) -> dict[str, Any]:
    vtype = normalize_vehicle(vehicle_type)
    if not vtype:
        raise ValueError(f"Unsupported vehicle type '{vehicle_type}'. We insure private cars, SUVs, electric cars and motorcycles for individuals.")
    cov = normalize_coverage(coverage) or "comprehensive"
    age = max(0.0, float(vehicle_age))
    city = (location or "Riyadh").strip().title()
    ncd = min(NCD_SLABS, key=lambda s: abs(s - int(ncb_percent or 0)))
    mv = market_value(vtype, age)
    lo, hi = round(mv * 0.8, -3), round(mv * 1.2, -3)
    iv = min(max(float(insured_value), lo), hi) if insured_value else mv
    ded = min(DEDUCTIBLES, key=lambda d: abs(d - int(deductible or 500)))

    b = _price(vtype, age, cov, city, ncd, iv, ded)
    score, band, factors = risk_score(vtype, age, city, cov)
    rec_cov, rec_reason = recommend_coverage(age, vtype)
    zone = "A" if city.lower() in ZONE_A else "B"
    age_txt = "Brand new" if age == 0 else f"{age:g} yrs old"
    return {
        # ---- generic fields shared by every line of business
        "line": "motor",
        "params": {"vehicle_type": vtype, "vehicle_age": age, "location": city, "ncb_percent": ncd,
                   "insured_value": iv, "deductible": ded},
        "subject": f"{VEHICLES[vtype]['label']} · {age_txt} · {city}",
        "sum_insured": b["idv"],
        "sum_insured_label": "Insured market value" if b["idv"] else "Third-party liability only",
        "breakdown": [{"label": k, "amount": v} for k, v in [
            ("Own damage", b["own_damage"]), ("No Claim Discount", -b["ncb_discount"]),
            ("Third-party liability", b["third_party"]), ("Plan benefits (agency repair, GCC…)", b["add_ons"]),
            (f"Deductible SAR {ded:,} per claim", 0),
            ("VAT (15%)", b["gst"])] if v],
        "gst_note": "Contribution includes 15% VAT.",
        # ---- motor-specific
        "vehicle_type": vtype, "vehicle_label": VEHICLES[vtype]["label"], "vehicle_age": age,
        "location": city, "zone": zone,
        "coverage": cov, "plan": COVERAGES[cov]["plan"], "plan_summary": COVERAGES[cov]["summary"],
        "coverage_details": {"includes": COVERAGES[cov]["includes"], "excludes": COVERAGES[cov]["excludes"]},
        "premium": b,
        "risk": {"score": score, "band": band, "factors": factors},
        "recommendation": {"coverage": rec_cov, "plan": COVERAGES[rec_cov]["plan"], "reason": rec_reason},
        "alternatives": [{"coverage": k, "plan": COVERAGES[k]["plan"], "recommended": k == rec_cov,
                          "total_premium": _price(vtype, age, k, city, ncd, iv, ded)["total_premium"]} for k in COVERAGES],
        "adjustables": [] if cov == "tpl" else [
            {"key": "insured_value", "label": "Vehicle value insured", "type": "range", "min": lo, "max": hi,
             "step": 1000, "value": iv, "unit": "SAR", "hint": f"Market value SAR {mv:,.0f} (±20%)"},
            {"key": "deductible", "label": "Deductible per claim", "type": "select", "value": ded, "unit": "SAR",
             "options": [{"value": d, "label": f"SAR {d:,}" + (f" · −{int(r * 100)}%" if r else "")} for d, r in DEDUCTIBLES.items()]},
        ],
        "validity_days": 15,
    }


def parse_age(text: str) -> float | None:
    t = text.lower()
    if re.search(r"\b(brand[- ]new|new (car|vehicle|bike|suv|motorcycle)|just bought|zero km|not yet registered)\b", t) \
            or t.strip() in {"new", "brand new"}:
        return 0.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr)\b", t)
    if m:
        return float(m.group(1))
    m = re.search(r"\b(20[0-3]\d|19[89]\d)\b", t)
    if m:
        return float(max(0, date.today().year - int(m.group(1))))
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "a year": 1, "six months": 0.5}
    for w, n in words.items():
        if re.search(rf"\b{w}\b\s*(years?|old)?", t) and ("year" in t or "old" in t or "month" in t):
            return float(n)
    if re.fullmatch(r"\s*\d+(\.\d+)?\s*", t):
        return float(t)
    return None
