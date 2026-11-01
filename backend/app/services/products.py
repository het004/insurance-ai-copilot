"""Product catalogue: one registry over our five individual portfolios — Health, Motor, Life,
Retirement & Savings and General (home).

Each line exposes: quote(params, plan) → standard quote dict, normalize_plan(text), underwrite(params, plan)
and how a purchased policy is recorded (policy_type, id prefix).
"""
from __future__ import annotations

from typing import Any, Callable

from app.services import health_engine, home_engine, life_engine, quote_engine, savings_engine


def _motor_quote(params: dict[str, Any], plan: str | None) -> dict[str, Any]:
    return quote_engine.calculate_quote(params["vehicle_type"], params["vehicle_age"], plan or "comprehensive",
                                        params.get("location") or params.get("city") or "Riyadh", params.get("ncb_percent", 0),
                                        params.get("insured_value"), params.get("deductible") or 500)


def _motor_uw(params: dict[str, Any], plan: str) -> list[str]:
    if plan == "comprehensive_plus" and float(params["vehicle_age"]) > 5:
        return ["Agency repair (Motor Comprehensive Plus) is only available for vehicles up to 5 years old — "
                "please choose Motor Comprehensive instead."]
    return []


def _health_quote(params: dict[str, Any], plan: str | None) -> dict[str, Any]:
    return health_engine.calculate_quote(params.get("age") or params["eldest_age"], params.get("city", "Riyadh"), plan,
                                         bool(params.get("pre_existing")), params.get("copay"),
                                         params.get("maternity", True) is not False)


def _savings_quote(params: dict[str, Any], plan: str | None) -> dict[str, Any]:
    kw = {k: params[k] for k in ("retirement_age", "income_years", "fund", "frequency", "ci_rider", "beneficiary",
                                 "declarations", "occupation", "salary") if k in params}
    if normalize_plan("savings", plan) == "retirement_plan":
        term = None  # the retirement plan's term comes from the retirement age
    else:
        term = params.get("term_years")
    return savings_engine.calculate_quote(params["age"], params.get("monthly_contribution"), term, plan,
                                          params.get("city"), **kw)


def _life_quote(params: dict[str, Any], plan: str | None) -> dict[str, Any]:
    return life_engine.calculate_quote(params["age"], params.get("sum_assured"), params.get("term_years"),
                                       bool(params.get("smoker")), plan, bool(params.get("has_family", True)),
                                       params.get("city"))


def _general_quote(params: dict[str, Any], plan: str | None) -> dict[str, Any]:
    return home_engine.calculate_quote(params.get("property_type", "apartment"), params.get("building_value", 0),
                                       params.get("contents_value", 0), params.get("city", "Riyadh"), plan)


LINES: dict[str, dict[str, Any]] = {
    "health": {"label": "Health", "quote": _health_quote, "normalize_plan": health_engine.normalize_plan,
               "underwrite": health_engine.underwrite, "policy_prefix": "POL-HLT", "policy_type": "Health"},
    "motor": {"label": "Motor", "quote": _motor_quote, "normalize_plan": quote_engine.normalize_coverage,
              "underwrite": _motor_uw, "policy_prefix": "POL-MTR"},
    "life": {"label": "Life", "quote": _life_quote, "normalize_plan": life_engine.normalize_plan,
             "underwrite": life_engine.underwrite, "policy_prefix": "POL-LIF", "policy_type": "Life"},
    "savings": {"label": "Retirement & Savings", "quote": _savings_quote, "normalize_plan": savings_engine.normalize_plan,
                "underwrite": savings_engine.underwrite, "policy_prefix": "POL-SAV", "policy_type": "Retirement & Savings"},
    "general": {"label": "General", "quote": _general_quote, "normalize_plan": home_engine.normalize_plan,
                "underwrite": home_engine.underwrite, "policy_prefix": "POL-GEN", "policy_type": "General - Home"},
}
LINES["home"] = LINES["general"]  # aliases
LINES["retirement"] = LINES["savings"]

MOTOR_POLICY_TYPE = {"car": "Motor - Car", "suv": "Motor - Car", "ev": "Motor - Car",
                     "bike": "Motor - Motorcycle", "commercial": "Motor - Commercial"}
MOTOR_PREFIX = {"bike": "POL-MC", "commercial": "POL-CV"}


def line_of(quote: dict[str, Any]) -> str:
    line = quote.get("line") or ("motor" if quote.get("vehicle_type") else "unknown")
    return {"home": "general", "retirement": "savings"}.get(line, line)


def params_of(quote: dict[str, Any]) -> dict[str, Any]:
    if quote.get("params"):
        return dict(quote["params"])
    return {"vehicle_type": quote.get("vehicle_type"), "vehicle_age": quote.get("vehicle_age", 0),
            "location": quote.get("location", "Riyadh")}


def quote(line: str, params: dict[str, Any], plan: str | None = None) -> dict[str, Any]:
    if line not in LINES:
        raise ValueError(f"We offer Health, Motor, Life, Retirement & Savings and General (home) plans online — '{line}' isn't available.")
    return LINES[line]["quote"](params, plan)


def normalize_plan(line: str, text: str | None) -> str | None:
    return LINES[line]["normalize_plan"](text) if line in LINES and text else None


def underwrite(line: str, params: dict[str, Any], plan: str) -> list[str]:
    fn: Callable = LINES[line]["underwrite"]
    return fn(params, plan)


def policy_type(line: str, params: dict[str, Any]) -> str:
    return MOTOR_POLICY_TYPE.get(params.get("vehicle_type"), "Motor - Car") if line == "motor" else LINES[line]["policy_type"]


def policy_prefix(line: str, params: dict[str, Any]) -> str:
    return MOTOR_PREFIX.get(params.get("vehicle_type"), "POL-MTR") if line == "motor" else LINES[line]["policy_prefix"]


def _cat(plans: dict) -> list[dict[str, str]]:
    return [{"code": k, "plan": v["plan"], "summary": v["summary"]} for k, v in plans.items()]


CATALOGUE = {"health": _cat(health_engine.PLANS), "motor": _cat(quote_engine.COVERAGES),
             "life": _cat(life_engine.PLANS), "savings": _cat(savings_engine.PLANS),
             "general": _cat(home_engine.PLANS)}
