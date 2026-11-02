"""Retirement & Savings — individual Takaful savings plans with protection (illustrative, Saudi Arabia).

Retirement Plan (the flagship) follows how private pension plans are sold in the Kingdom:
  • two periods — a CONTRIBUTION period (now → chosen retirement age) and an INCOME period (5–20 years of
    retirement income paid monthly)
  • regular contributions monthly / quarterly / semi-annual / annual (minimum SAR 1,000 a month equivalent)
  • a choice of Shariah-compliant funds by risk level (Conservative, Balanced, Growth)
  • Takaful protection from SAR 50,000 for chosen beneficiaries, optional critical-illness add-on
  • KYC declarations before issue: FATCA / CRS tax residency, politically exposed person (PEP), source of funds
Savings Plan and Education Plan use a simpler monthly-contribution-for-N-years model.

All projections are ILLUSTRATIVE — fund growth is not guaranteed. VAT-exempt (savings with life protection).
"""
from __future__ import annotations

import re
from typing import Any

MIN_MONTHLY = 300
MIN_MONTHLY_RETIREMENT = 1_000
MAX_MONTHLY = 80_000
PAYOUT_RATE = 0.03  # Murabaha rate assumed while retirement income is paid out

FUNDS: dict[str, dict[str, Any]] = {
    "conservative": {"name": "Conservative Fund (Sukuk & Murabaha)", "growth": 0.035, "fee": 0.006, "risk": "Low"},
    "balanced": {"name": "Balanced Fund (Sukuk + Shariah equities)", "growth": 0.05, "fee": 0.010, "risk": "Medium"},
    "growth": {"name": "Growth Fund (Shariah equities)", "growth": 0.065, "fee": 0.014, "risk": "High"},
}
FREQUENCIES = {"monthly": 12, "quarterly": 4, "semi_annual": 2, "annual": 1}
FREQ_LABEL = {"monthly": "month", "quarterly": "quarter", "semi_annual": "half-year", "annual": "year"}
INCOME_YEARS = [5, 10, 15, 20]
CI_RIDER_RATE = 0.0009  # critical illness add-on, per SAR of protection a year (illustrative)

PLANS: dict[str, dict[str, Any]] = {
    "retirement_plan": {
        "plan": "Retirement Plan", "admin_fee": 0.01, "default_term": None, "min_term": 5,
        "summary": "Build a pension pot until you retire, then receive a monthly retirement income — with Takaful "
                   "protection for your family along the way.",
        "includes": ["Contribution period until your chosen retirement age", "Monthly retirement income for 5–20 years",
                     "Choice of Shariah-compliant funds — switch any time", "Takaful protection from SAR 50,000",
                     "Top-ups and partial withdrawals", "Optional critical-illness add-on"],
        "excludes": ["Guaranteed returns — fund value can go down", "Withdrawals before age 55 carry a charge",
                     "Cancellation charges in the first 3 years"],
    },
    "savings_plan": {
        "plan": "Savings Plan", "admin_fee": 0.015, "default_term": 10, "min_term": 5,
        "summary": "Save monthly towards any goal — a home, marriage or Hajj — with Takaful protection built in.",
        "includes": ["Monthly contribution into a Shariah-compliant balanced fund", "Takaful protection for your family",
                     "Partial withdrawals after 3 years", "Pause contributions for up to 6 months", "Top up any time"],
        "excludes": ["Guaranteed returns — fund value can go down", "Surrender charges in the first 3 years"],
    },
    "education_plan": {
        "plan": "Education Plan", "admin_fee": 0.015, "default_term": 15, "min_term": 5,
        "summary": "Save for your child's university — if anything happens to you, we keep paying the contributions.",
        "includes": ["Fund paid out when your child starts university", "Takaful pays remaining contributions if you die",
                     "Takaful protection for your family", "Choose a payout over 4 years of study"],
        "excludes": ["Guaranteed returns — fund value can go down", "Surrender charges in the first 3 years"],
    },
}
PLAN_ALIASES = {"retire": "retirement_plan", "retirement": "retirement_plan", "pension": "retirement_plan",
                "education": "education_plan", "child": "education_plan", "children": "education_plan",
                "kids": "education_plan", "university": "education_plan", "school": "education_plan",
                "saving": "savings_plan", "savings": "savings_plan", "save": "savings_plan", "goal": "savings_plan"}


def normalize_plan(text: str | None) -> str | None:
    if not text:
        return None
    t = text.strip().lower().replace("-", " ")
    if t.replace(" ", "_") in PLANS:
        return t.replace(" ", "_")
    if re.search(r"\bretire|\bpension", t):
        return "retirement_plan"
    if re.search(r"\beducation|\buniversity|\bchild|\bkids?\b|\bschool", t):
        return "education_plan"
    for name, code in sorted(((v["plan"].lower(), k) for k, v in PLANS.items()), key=lambda x: -len(x[0])):
        if name in t:
            return code
    for k, v in sorted(PLAN_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{k}", t):
            return v
    return None


def normalize_fund(text: str | None) -> str | None:
    t = (text or "").lower()
    if re.search(r"conservative|low risk|safe|sukuk|murabaha|cautious", t):
        return "conservative"
    if re.search(r"growth|high risk|aggressive|equit|stocks?", t):
        return "growth"
    if re.search(r"balanced|medium|moderate|middle", t):
        return "balanced"
    return None


def normalize_frequency(text: str | None) -> str | None:
    t = (text or "").lower()
    if re.search(r"semi|half|6 months|twice a year", t):
        return "semi_annual"
    if re.search(r"quarter|3 months", t):
        return "quarterly"
    if re.search(r"annual|yearly|once a year|every year", t):
        return "annual"
    if re.search(r"monthly|every month|each month|month", t):
        return "monthly"
    return None


def recommend_monthly(age: int, plan: str = "savings_plan") -> int:
    if plan == "retirement_plan":
        return 1_500 if age < 35 else 2_500 if age < 45 else 4_000
    return 500 if age < 30 else 1_000 if age < 45 else 1_500


def recommend_fund(age: int, retire_age: int) -> str:
    years = retire_age - age
    return "growth" if years >= 25 else "balanced" if years >= 10 else "conservative"


def default_term(plan: str, age: int) -> int:
    if plan == "retirement_plan":
        return max(5, 60 - age)
    return PLANS[plan]["default_term"]


def _fv(monthly: float, years: float, rate: float, fee: float) -> int:
    r = (rate - fee) / 12
    n = int(round(years * 12))
    return round(monthly * n if abs(r) < 1e-9 else monthly * ((1 + r) ** n - 1) / r * (1 + r))


def _income(pot: float, years: int) -> int:
    """Level monthly retirement income that runs the pot down over `years` at the payout rate."""
    r, n = PAYOUT_RATE / 12, years * 12
    return round(pot * r / (1 - (1 + r) ** -n))


def _scenarios(growth: float) -> dict[str, float]:
    return {"low": max(0.0, growth - 0.02), "mid": growth, "high": growth + 0.02}


# ---------------------------------------------------------------- retirement plan
def _retirement_quote(age: int, monthly: float | None, retire_age: int | None, income_years: int | None,
                      fund: str | None, frequency: str | None, ci_rider: bool, extra: dict[str, Any],
                      city: str | None) -> dict[str, Any]:
    if not 18 <= age <= 55:
        raise ValueError("The Retirement Plan can be started online between ages 18 and 55.")
    ra = int(retire_age or 60)
    ra = max(55, min(ra, 65))
    if ra - age < 5:
        ra = min(65, age + 5)
    if ra - age < 5:
        raise ValueError("The contribution period must be at least 5 years — the latest retirement age is 65.")
    years = ra - age
    iy = min(INCOME_YEARS, key=lambda y: abs(y - int(income_years or 15)))
    fd = fund if fund in FUNDS else recommend_fund(age, ra)
    fq = frequency if frequency in FREQUENCIES else "monthly"
    m = float(monthly or recommend_monthly(age, "retirement_plan"))
    if not MIN_MONTHLY_RETIREMENT <= m <= MAX_MONTHLY:
        raise ValueError(f"Retirement Plan contributions must be between SAR {MIN_MONTHLY_RETIREMENT:,} and "
                         f"SAR {MAX_MONTHLY:,} a month.")
    f = FUNDS[fd]
    annual = round(m * 12)
    per_instalment = round(annual / FREQUENCIES[fq])
    total = annual * years
    protection = max(50_000, round(min(total, 1_000_000), -3))
    rider = round(protection * CI_RIDER_RATE) if ci_rider else 0
    fee = PLANS["retirement_plan"]["admin_fee"] + f["fee"]
    pots = {k: _fv(m, years, g, fee) for k, g in _scenarios(f["growth"]).items()}
    incomes = {k: _income(v, iy) for k, v in pots.items()}
    factors = [f"Contribution period {years} years (age {age} → {ra})", f"Income period {iy} years (age {ra} → {ra + iy})",
               f"{f['name']} · {f['risk']} risk · fund fee {f['fee'] * 100:.1f}% a year",
               f"Plan admin fee {PLANS['retirement_plan']['admin_fee'] * 100:.1f}% a year · 100% allocation"]
    breakdown = [("Retirement contributions", annual), ("Critical-illness add-on", rider)]
    rec = recommend_fund(age, ra)
    return {
        "line": "savings",
        "params": {"age": age, "monthly_contribution": m, "retirement_age": ra, "income_years": iy, "fund": fd,
                   "frequency": fq, "ci_rider": bool(ci_rider), "term_years": years + iy, "city": city or "", **extra},
        "subject": f"Retire at {ra} · SAR {m:,.0f}/month · {f['name'].split(' (')[0]}",
        "sum_insured": protection,
        "sum_insured_label": f"Takaful protection SAR {protection:,}",
        "breakdown": [{"label": k, "amount": v} for k, v in breakdown if v],
        "gst_note": "Retirement plans with Takaful protection are VAT-exempt.",
        "location": city or "", "zone": "",
        "coverage": "retirement_plan", "plan": "Retirement Plan", "plan_summary": PLANS["retirement_plan"]["summary"],
        "coverage_details": {"includes": PLANS["retirement_plan"]["includes"], "excludes": PLANS["retirement_plan"]["excludes"]},
        "premium": {"net_premium": annual + rider, "gst": 0, "total_premium": annual + rider, "idv": 0,
                    "monthly": round(m), "instalment": per_instalment, "frequency": fq},
        "projection": {"years": years, "total_contributions": total, **pots,
                       "rates": {k: round(v * 100, 1) for k, v in _scenarios(f["growth"]).items()},
                       "retirement_age": ra, "income_years": iy, "monthly_income": incomes,
                       "note": "Illustrative after fees, at the fund's assumed growth ±2% — not guaranteed."},
        "retirement": {
            "contribution_period": f"{years} years (to age {ra})", "income_period": f"{iy} years (age {ra}–{ra + iy})",
            "fund": f["name"], "fund_risk": f["risk"], "frequency": fq,
            "instalment": f"SAR {per_instalment:,} per {FREQ_LABEL[fq]}",
            "protection": protection, "ci_rider": bool(ci_rider),
            "beneficiary": extra.get("beneficiary"), "declarations": extra.get("declarations"),
        },
        "risk": {"score": {"Low": 20, "Medium": 45, "High": 70}[f["risk"]], "band": f["risk"], "factors": factors},
        "recommendation": {"coverage": "retirement_plan", "plan": "Retirement Plan",
                           "reason": f"With {years} years to retirement we'd suggest the {FUNDS[rec]['name'].split(' (')[0]}."},
        "alternatives": [{"coverage": "retirement_plan", "plan": f"{FUNDS[k]['name'].split(' (')[0]}", "fund": k,
                          "recommended": k == rec, "total_premium": annual + rider,
                          "projected_value": _fv(m, years, FUNDS[k]["growth"], PLANS["retirement_plan"]["admin_fee"] + FUNDS[k]["fee"])}
                         for k in FUNDS],
        "adjustables": [
            {"key": "monthly_contribution", "label": "Monthly contribution", "type": "range", "min": 1_000,
             "max": 20_000, "step": 250, "value": m, "unit": "SAR"},
            {"key": "retirement_age", "label": "Retirement age", "type": "range", "min": max(55, age + 5),
             "max": 65, "step": 1, "value": ra, "unit": "years"},
            {"key": "income_years", "label": "Retirement income paid for", "type": "select", "value": iy,
             "options": [{"value": y, "label": f"{y} years"} for y in INCOME_YEARS]},
            {"key": "fund", "label": "Investment fund", "type": "select", "value": fd,
             "options": [{"value": k, "label": f"{v['name'].split(' (')[0]} · {v['risk']} risk"} for k, v in FUNDS.items()]},
            {"key": "ci_rider", "label": "Critical-illness add-on", "type": "toggle", "value": bool(ci_rider),
             "hint": f"≈ SAR {round(protection * CI_RIDER_RATE):,} a year"},
        ],
        "validity_days": 15,
    }


def calculate_quote(age: int, monthly_contribution: float | None = None, term_years: int | None = None,
                    plan: str | None = None, city: str | None = None, **kw: Any) -> dict[str, Any]:
    age = int(age)
    code = normalize_plan(plan) or "savings_plan"
    if code == "retirement_plan":
        extra = {k: kw[k] for k in ("beneficiary", "declarations", "occupation", "salary") if kw.get(k)}
        return _retirement_quote(age, monthly_contribution, kw.get("retirement_age"), kw.get("income_years"),
                                 kw.get("fund"), kw.get("frequency"), bool(kw.get("ci_rider")), extra, city)
    if not 18 <= age <= 60:
        raise ValueError("Savings plans can be started online between ages 18 and 60.")
    monthly = float(monthly_contribution or recommend_monthly(age, code))
    if not MIN_MONTHLY <= monthly <= MAX_MONTHLY:
        raise ValueError(f"The monthly contribution must be between SAR {MIN_MONTHLY} and SAR {MAX_MONTHLY:,}.")
    term = int(term_years or default_term(code, age))
    term = max(PLANS[code]["min_term"], min(term, 30))
    if age + term > 70:
        term = max(PLANS[code]["min_term"], 70 - age)
    annual = round(monthly * 12)
    total = annual * term
    protection = max(50_000, round(total, -3))
    fee = PLANS[code]["admin_fee"]
    proj = {k: _fv(monthly, term, g, fee) for k, g in {"low": 0.03, "mid": 0.05, "high": 0.07}.items()}
    rec = "retirement_plan" if age >= 35 and code != "education_plan" else code
    rec_reason = {"retirement_plan": "From your mid-thirties, a Retirement Plan gives you an income for life after work.",
                  "savings_plan": "A Savings Plan keeps your money flexible for any goal.",
                  "education_plan": "An Education Plan protects your child's university fund even if you can't."}[rec]
    return {
        "line": "savings",
        "params": {"age": age, "monthly_contribution": monthly, "term_years": term, "city": city or ""},
        "subject": f"SAR {monthly:,.0f}/month · {term} years · age {age}",
        "sum_insured": protection,
        "sum_insured_label": f"Protection SAR {protection:,}",
        "breakdown": [{"label": "Monthly contribution × 12", "amount": annual}],
        "gst_note": "Savings plans with Takaful protection are VAT-exempt.",
        "location": city or "", "zone": "",
        "coverage": code, "plan": PLANS[code]["plan"], "plan_summary": PLANS[code]["summary"],
        "coverage_details": {"includes": PLANS[code]["includes"], "excludes": PLANS[code]["excludes"]},
        "premium": {"net_premium": annual, "gst": 0, "total_premium": annual, "idv": 0, "monthly": round(monthly)},
        "projection": {"years": term, "total_contributions": total, **proj, "rates": {"low": 3, "mid": 5, "high": 7},
                       "note": "Illustrative at 3%, 5% and 7% a year after fees — not guaranteed."},
        "risk": {"score": 20, "band": "Low", "factors": [f"Age {age} · matures at {age + term}",
                                                          f"Admin fee {fee * 100:.1f}% a year"]},
        "recommendation": {"coverage": rec, "plan": PLANS[rec]["plan"], "reason": rec_reason},
        "alternatives": [{"coverage": k, "plan": v["plan"], "recommended": k == rec, "total_premium": annual,
                          "projected_value": _fv(monthly, term, 0.05, v["admin_fee"])}
                         for k, v in PLANS.items() if k != "retirement_plan"],
        "adjustables": [
            {"key": "monthly_contribution", "label": "Monthly contribution", "type": "range", "min": 300,
             "max": 10_000, "step": 100, "value": monthly, "unit": "SAR"},
            {"key": "term_years", "label": "Saving for", "type": "select", "value": term,
             "options": [{"value": y, "label": f"{y} years"} for y in (5, 10, 15, 20, 25, 30) if age + y <= 70]},
        ],
        "validity_days": 15,
    }


def underwrite(params: dict[str, Any], plan: str) -> list[str]:
    issues = []
    if params["monthly_contribution"] > 10_000:
        issues.append("Contributions above SAR 10,000 a month need a source-of-funds check — our team will call you "
                      "within one working day.")
    decl = params.get("declarations") or {}
    if decl.get("pep"):
        issues.append("As a politically exposed person, your application needs enhanced due diligence — our compliance "
                      "team will contact you within two working days.")
    if decl.get("us_person"):
        issues.append("As a US person we need a signed W-9 form under FATCA before issuing — we'll send it to you.")
    return issues
