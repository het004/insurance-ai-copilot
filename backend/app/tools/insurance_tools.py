"""The LangGraph tools exposed to Gemini (16 tools).

Identity & onboarding:  identify_customer · fetch_kyc_from_government · confirm_registration · lookup_vehicle
Quotes (5 portfolios):  generate_health_quote · generate_quote (motor) · generate_life_quote ·
                        generate_savings_quote · generate_general_quote
Insurance journeys:     purchase_policy ·
                        get_customer_profile · get_policy_details · create_claim ·
                        track_claim · renew_policy · knowledge_search

Security: the customer is NEVER a tool argument. Tools read the verified customer for this chat
from the session store (keyed by the LangGraph thread_id = chat session id). Personal-data tools
refuse until the session is verified, so the model cannot be talked into showing someone else's data.
"""
from __future__ import annotations

import json
import re
from typing import Annotated, Any, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from app.rag import kb
from app.services import identity_service as ids
from app.services import insurance_service as svc
from app.services import purchase_service, systems
from app.services.session_store import session_store

NOT_IDENTIFIED = ("NOT_IDENTIFIED: this chat is not linked to a verified customer yet. Ask whether they are an "
                  "existing customer (registered mobile number, email, customer ID or policy number → "
                  "identify_customer) or a new customer (National ID or Iqama with consent → fetch_kyc_from_government).")


class NotIdentified(Exception):
    pass


def _session_id(config: RunnableConfig | None) -> str:
    return ((config or {}).get("configurable") or {}).get("thread_id") or "_anon"


def _customer(config: RunnableConfig | None) -> str | None:
    return session_store.get(_session_id(config)).customer_id


def _require(config: RunnableConfig | None) -> str:
    cid = _customer(config)
    if not cid:
        raise NotIdentified(NOT_IDENTIFIED)
    return cid


def _known(config: RunnableConfig | None) -> dict[str, Any]:
    """Facts already verified for this chat (age from date of birth, city from National Address, vehicle from Elm)."""
    return session_store.get(_session_id(config)).extra


def _need(value: Any, what: str) -> Any:
    if value in (None, ""):
        raise ValueError(f"I need the customer's {what} — verify them first (National ID / Iqama) or ask for it.")
    return value


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _customer_typed(config: RunnableConfig | None, value: str, min_digits: int = 6) -> bool:
    """Guardrail: an ID / mobile number must come from the customer, never from the model's imagination."""
    digits = re.sub(r"\D", "", (value or "").translate(_AR_DIGITS))
    if len(digits) < min_digits:
        return True  # not a number-based identifier (email, policy number…) — nothing to check
    said = session_store.get(_session_id(config)).extra.get("said")
    if said is None:  # called outside a chat turn (REST / tests) — allow
        return True
    return any(digits[-9:] in re.sub(r"\D", "", m.translate(_AR_DIGITS)) for m in said)


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, default=str)


def _err(e: Exception) -> str:
    return json.dumps({"ok": False, "error": str(e), "code": "NOT_IDENTIFIED" if isinstance(e, NotIdentified) else None})


# ================================================================== identity & onboarding
@tool
def identify_customer(identifier: str, config: RunnableConfig,
                      tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
    """Identify an EXISTING registered customer and link them to this chat.

    Args:
        identifier: their registered mobile number, email, customer ID (CUST-…) or a policy number (POL-…).
    Returns found=true with a customer summary, or found=false (then offer new-customer onboarding).
    """
    try:
        if not _customer_typed(config, identifier):
            raise ValueError("NOT_PROVIDED: the customer has not given this number. Ask them for their registered "
                             "mobile number — never guess or invent it.")
        return _ok(ids.identify(_session_id(config), identifier, tool_call_id))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def fetch_kyc_from_government(id_type: str, id_number: str, consent: bool, config: RunnableConfig,
                              tool_call_id: Annotated[str, InjectedToolCallId],
                              vehicle_number: Optional[str] = None, full_name: Optional[str] = None) -> str:
    """For a NEW customer: verify identity and fetch their details from Saudi government sources —
    Nafath authentication, Yakeen (Elm) identity data, National Address (SPL), and optionally the vehicle
    registration (Elm).

    Only call after the customer has explicitly agreed (consent=true).
    Args:
        id_type: "NATIONAL_ID" (Saudi citizens, starts with 1) or "IQAMA" (residents, starts with 2).
        id_number: the 10-digit National ID or Iqama number.
        consent: true only if the customer explicitly consented.
        vehicle_number: optional Saudi plate (e.g. "7788 BDR") or 9-digit Istimara sequence number (motor).
        full_name: the name the customer gave, checked against Yakeen.
    If the ID is already registered, the chat is linked to that customer (already_registered=true).
    Otherwise returns the fetched details (draft): show them briefly and ask the customer to confirm.
    """
    try:
        if not _customer_typed(config, id_number, 10):
            raise ValueError("NOT_PROVIDED: the customer has not shared a National ID or Iqama number yet. Ask for it "
                             "(10 digits) — a name alone is not enough, and never guess or invent an ID.")
        return _ok(ids.fetch_kyc(_session_id(config), id_type, id_number, consent, vehicle_number, tool_call_id,
                                 full_name))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def confirm_registration(confirm: bool, config: RunnableConfig,
                         tool_call_id: Annotated[str, InjectedToolCallId],
                         name: Optional[str] = None, address: Optional[str] = None,
                         phone: Optional[str] = None, email: Optional[str] = None) -> str:
    """Confirm (or correct) the KYC details fetched for a new customer and register them in Customer 360.

    Args:
        confirm: true ONLY after the customer explicitly says the details are correct; false to just apply corrections.
        name, address, phone, email: optional corrections or additions provided by the customer.
    On confirm=true the customer is added to Customer 360 (Excel) and this chat becomes verified.
    """
    corrections = {k: v for k, v in {"name": name, "address": address, "phone": phone, "email": email}.items() if v}
    try:
        return _ok(ids.confirm_registration(_session_id(config), confirm, corrections, tool_call_id))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def lookup_vehicle(vehicle_number: str, config: RunnableConfig,
                   tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
    """Fetch a vehicle's registration (make, model, year, type) from Elm (simulated) for a VERIFIED customer.
    Use for motor quotes when the customer is already identified (new customers pass vehicle_number to
    fetch_kyc_from_government instead).
    Args:
        vehicle_number: Saudi plate (e.g. "7788 BDR") or 9-digit Istimara sequence number.
    """
    try:
        _require(config)
        return _ok(ids.lookup_vehicle(_session_id(config), vehicle_number, tool_call_id))
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ================================================================== insurance journeys
@tool
def generate_quote(coverage: str, config: RunnableConfig, tool_call_id: Annotated[str, InjectedToolCallId],
                   vehicle_type: Optional[str] = None, vehicle_age: Optional[float] = None,
                   location: Optional[str] = None, insured_value: Optional[float] = None,
                   deductible: Optional[int] = None) -> str:
    """Generate a MOTOR Takaful quotation (private car, SUV, EV, motorcycle) from our plans:
    Motor TPL (mandatory third-party liability), Motor Comprehensive, Motor Comprehensive Plus (agency repair).

    Vehicle type, vehicle age and city default to what was fetched from Elm / the National Address for this chat,
    so normally you only pass coverage.
    Args:
        coverage: tpl, comprehensive or comprehensive_plus (use our recommendation if the customer is unsure).
        vehicle_type: car, suv, ev or bike (only if no vehicle was fetched).
        vehicle_age: years (0 = brand new), only if no vehicle was fetched.
        location: city in Saudi Arabia, only if not known.
        insured_value: vehicle value to insure in SAR (market value ±20%); omit for market value.
        deductible: excess per claim — 500, 1000, 2000 or 3000 SAR (higher = lower contribution).
    """
    try:
        k = _known(config)
        v = k.get("vehicle") or {}
        vtype = vehicle_type or v.get("vehicle_type") or "car"
        vage = vehicle_age if vehicle_age is not None else v.get("vehicle_age", 0)
        params = {"vehicle_type": vtype, "vehicle_age": vage, "location": location or k.get("city") or "Riyadh",
                  "ncb_percent": 0, "insured_value": insured_value, "deductible": deductible or 500}
        q = svc.create_product_quote(_customer(config) or "GUEST", "motor", params, coverage)
        systems.quote_steps(tool_call_id, q, _customer(config))
        _remember_quote(config, q)
        return _ok(q)
    except Exception as e:  # noqa: BLE001
        return _err(e)


def _remember_quote(config: RunnableConfig | None, q: dict[str, Any]) -> None:
    extra = session_store.get(_session_id(config)).extra
    extra["last_quote_id"], extra["last_quote_line"] = q["quote_id"], q.get("line", "motor")


@tool
def generate_health_quote(config: RunnableConfig, tool_call_id: Annotated[str, InjectedToolCallId],
                          pre_existing_conditions: bool = False, plan: Optional[str] = None,
                          age: Optional[int] = None, city: Optional[str] = None, copay_percent: Optional[int] = None,
                          maternity: bool = True) -> str:
    """Generate an INDIVIDUAL health Takaful quotation (one person) from our plans:
    Health Essential (Class C network), Health Gold (Class B), Health Premier (Class A / VIP).
    Age and city default to the verified customer's ID record and National Address.

    Args:
        pre_existing_conditions: true if they have a chronic condition (diabetes, hypertension, asthma…).
        plan: health_essential, health_gold or health_premier. Omit to use our recommendation.
        age, city: only if not already known for this chat.
        copay_percent: outpatient co-pay 0, 10 or 20 (omit for the plan's default).
        maternity: include maternity cover (default true).
    """
    try:
        k = _known(config)
        q = svc.create_product_quote(_customer(config) or "GUEST", "health",
                                     {"age": _need(age or k.get("age"), "age"), "city": city or k.get("city") or "Riyadh",
                                      "pre_existing": pre_existing_conditions, "copay": copay_percent,
                                      "maternity": maternity}, plan)
        systems.quote_steps(tool_call_id, q, _customer(config))
        _remember_quote(config, q)
        return _ok(q)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def generate_life_quote(config: RunnableConfig, tool_call_id: Annotated[str, InjectedToolCallId], age: Optional[int] = None, sum_assured: Optional[float] = None,
                        term_years: Optional[int] = None, smoker: bool = False, plan: Optional[str] = None,
                        has_dependants: bool = True) -> str:
    """Generate a LIFE (family Takaful protection) quotation for one person from our plans: Life Protect,
    Life Protect Plus (+ critical illness, accidental death), Life Premier (+ waiver of contributions, family income).
    VAT-exempt. Age defaults to the verified customer's ID record.

    Args:
        age: only if not already known (18–65).
        sum_assured: sum covered in SAR (e.g. 1500000). Omit to use our recommendation.
        term_years: 10, 15, 20, 25 or 30 (cover must end by age 70). Omit for our default.
        smoker: true if they smoke or use tobacco.
        plan: life_protect, life_protect_plus or life_premier. Omit to use our recommendation.
        has_dependants: whether a spouse/children depend on their income.
    """
    try:
        q = svc.create_product_quote(_customer(config) or "GUEST", "life",
                                     {"age": _need(age or _known(config).get("age"), "age"), "sum_assured": sum_assured, "term_years": term_years,
                                      "smoker": smoker, "has_family": has_dependants}, plan)
        systems.quote_steps(tool_call_id, q, _customer(config))
        _remember_quote(config, q)
        return _ok(q)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def generate_savings_quote(config: RunnableConfig, tool_call_id: Annotated[str, InjectedToolCallId],
                           plan: Optional[str] = None, monthly_contribution: Optional[float] = None,
                           term_years: Optional[int] = None, age: Optional[int] = None,
                           retirement_age: Optional[int] = None, income_years: Optional[int] = None,
                           fund: Optional[str] = None, frequency: Optional[str] = None, ci_rider: bool = False,
                           beneficiary: Optional[str] = None, us_person: Optional[bool] = None,
                           pep: Optional[bool] = None, source_of_funds: Optional[str] = None) -> str:
    """Generate a RETIREMENT & SAVINGS quotation (individual Takaful savings with protection). VAT-exempt.

    Plans: retirement_plan (flagship: contribution period to a chosen retirement age 55–65, then a monthly
    retirement income for 5–20 years; min SAR 1,000/month), savings_plan (any goal), education_plan.
    For the Retirement Plan collect, one per message: retirement age, monthly contribution, payment frequency,
    fund (conservative / balanced / growth), beneficiary for the protection, FATCA (US person) and PEP
    declarations, and source of funds. Projections are ILLUSTRATIVE — not guaranteed.

    Args:
        plan: retirement_plan, savings_plan or education_plan.
        monthly_contribution: SAR per month. Omit to use our suggestion.
        term_years: savings / education plans only.
        age: only if not already known.
        retirement_age: 55–65 (retirement plan).
        income_years: 5, 10, 15 or 20 years of retirement income (retirement plan).
        fund: conservative, balanced or growth.
        frequency: monthly, quarterly, semi_annual or annual.
        ci_rider: add critical-illness cover.
        beneficiary: name and relationship of the beneficiary.
        us_person: FATCA — US citizen or US tax resident.
        pep: politically exposed person.
        source_of_funds: salary, business, investments, inheritance…
    """
    try:
        k = _known(config)
        decl = {kk: v for kk, v in {"us_person": us_person, "pep": pep, "source_of_funds": source_of_funds}.items()
                if v is not None}
        params = {"age": _need(age or k.get("age"), "age"), "monthly_contribution": monthly_contribution,
                  "term_years": term_years, "city": k.get("city") or "", "retirement_age": retirement_age,
                  "income_years": income_years, "fund": fund, "frequency": frequency, "ci_rider": ci_rider,
                  "beneficiary": beneficiary, "declarations": decl or None}
        q = svc.create_product_quote(_customer(config) or "GUEST", "savings",
                                     {kk: v for kk, v in params.items() if v is not None}, plan)
        systems.quote_steps(tool_call_id, q, _customer(config))
        _remember_quote(config, q)
        return _ok(q)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def generate_general_quote(building_value: float, config: RunnableConfig,
                           tool_call_id: Annotated[str, InjectedToolCallId], city: Optional[str] = None,
                           property_type: str = "apartment", contents_value: float = 0, plan: Optional[str] = None) -> str:
    """Generate a GENERAL (home & property) Takaful quotation from our plans: Home Basic (building),
    Home Plus (+ contents, burglary), Home Premier (+ valuables, personal liability, domestic workers).

    Args:
        building_value: rebuilding cost of the building in SAR (e.g. 1200000).
        city: city of the property; defaults to the customer's National Address city.
        property_type: "apartment" or "villa".
        contents_value: value of belongings in SAR (0 if building only).
        plan: home_basic, home_plus or home_premier. Omit to use our recommendation.
    """
    try:
        q = svc.create_product_quote(_customer(config) or "GUEST", "general",
                                     {"property_type": property_type, "building_value": building_value,
                                      "contents_value": contents_value, "city": city or _known(config).get("city") or "Riyadh"}, plan)
        systems.quote_steps(tool_call_id, q, _customer(config))
        _remember_quote(config, q)
        return _ok(q)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def purchase_policy(config: RunnableConfig, tool_call_id: Annotated[str, InjectedToolCallId],
                    quote_id: Optional[str] = None, coverage: Optional[str] = None, confirm: bool = False,
                    payment_method: Optional[str] = None, registration_number: Optional[str] = None) -> str:
    """Buy a plan (health, motor, life, retirement & savings or general) from a quotation for the verified customer (checkout).

    Step 1 — confirm=false: returns a purchase review (plan, contribution, insured vehicle, policy period,
    other plan options, underwriting result). Present it, let the customer pick a plan, and ask how they
    want to pay (mada, Apple Pay, STC Pay, credit card or SADAD).
    Step 2 — ONLY after the customer explicitly agrees to pay: confirm=true with payment_method. Runs the
    (simulated) payment, issues the policy and adds it to Customer 360.
    Args:
        quote_id: the quote to buy; defaults to the latest quote in this chat.
        coverage: switch plan before buying — a plan code from the quote's alternatives
            (health: health_essential/health_gold/health_premier; motor: tpl/comprehensive/comprehensive_plus;
            life: life_protect/life_protect_plus/life_premier; savings: savings_plan/retirement_plan/education_plan;
            general: home_basic/home_plus/home_premier).
        confirm: true only after explicit consent to pay.
        payment_method: "mada", "Apple Pay", "STC Pay", "Credit card" or "SADAD" (required when confirm=true).
        registration_number: motor only — Saudi plate (e.g. "1234 ABJ") or Istimara sequence number.
    """
    try:
        cid = _require(config)
        extra = session_store.get(_session_id(config)).extra
        r = purchase_service.purchase(cid, quote_id=quote_id, coverage=coverage, confirm=confirm,
                                      payment_method=payment_method, registration_number=registration_number,
                                      default_quote_id=extra.get("last_quote_id"), vahan_vehicle=extra.get("vehicle"),
                                      tool_call_id=tool_call_id)
        extra["last_quote_id"], extra["last_quote_line"] = r["quote_id"], r["line"]
        return _ok(r)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def get_customer_profile(config: RunnableConfig) -> str:
    """Get the verified customer's 360° profile from Customer 360: personal details, policy summary,
    open claims, renewals due, previous quotes and recommended next-best actions."""
    try:
        return _ok(svc.get_customer_360(_require(config)))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def get_policy_details(config: RunnableConfig, policy_id: Optional[str] = None) -> str:
    """Get the verified customer's policies. Without policy_id returns all policies (type, asset, premium,
    sum insured, dates, status, days to expiry). With policy_id returns that single policy."""
    try:
        cid = _require(config)
        return _ok(svc.get_policy(policy_id, cid) if policy_id else svc.list_policies(cid))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def create_claim(description: str, config: RunnableConfig, tool_call_id: Annotated[str, InjectedToolCallId],
                 incident_date: Optional[str] = None,
                 location: Optional[str] = None, policy_id: Optional[str] = None,
                 incident_type: Optional[str] = None) -> str:
    """Register a new insurance claim (first notice of loss) for the verified customer and return the
    claim ID, status timeline and next steps.

    Args:
        description: what happened and what was damaged.
        incident_date: YYYY-MM-DD (convert 'today'/'yesterday' using the current date).
        location: where it happened.
        policy_id: optional; if omitted the matching active motor/health policy is chosen.
        incident_type: optional, e.g. 'Accident - Own Damage', 'Theft', 'Windshield',
            'Accident - Third Party', 'Flood / Natural Calamity', 'Health - Hospitalisation'.
    """
    try:
        c = svc.create_claim(_require(config), description, incident_date, location, policy_id, incident_type)
        systems.step(tool_call_id, "fnol", f"{systems.CORE} Claims · registering first notice of loss",
                     f"{c['claim_id']} on {c['policy_id']}", 0.3, 0.5)
        systems.step(tool_call_id, "triage", f"{systems.CORE} Claims · triage & surveyor assignment",
                     f"{c.get('incident_type', 'Claim')} · fast-track eligible")
        systems.step(tool_call_id, "crm", f"{systems.CRM} · notifying the customer", "SMS + email sent (simulated)")
        return _ok(c)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def track_claim(config: RunnableConfig, claim_id: Optional[str] = None) -> str:
    """Check claim status for the verified customer. With claim_id returns that claim's stage, progress and
    timeline (Reported → Under Review → Assessment → Approved → Closed). Without claim_id lists all claims."""
    try:
        cid = _require(config)
        return _ok(svc.get_claim(claim_id, cid) if claim_id else svc.list_claims(cid))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def renew_policy(policy_id: str, config: RunnableConfig, tool_call_id: Annotated[str, InjectedToolCallId],
                 confirm: bool = False) -> str:
    """Policy renewal workflow for the verified customer.

    With confirm=false (default) returns a renewal quotation: current vs renewal premium,
    No Claim Discount change (motor), new period and a recommendation — present it and ask the customer to confirm.
    Only after the customer explicitly agrees, call again with confirm=true to issue the renewed policy.
    """
    try:
        r = svc.renew_policy(policy_id, confirm, _require(config))
        if confirm:
            systems.step(tool_call_id, "pay", f"{systems.PAYMENTS} · collecting renewal contribution",
                         f"SAR {r['renewal_premium']:,} captured", 0.4, 0.7)
            systems.step(tool_call_id, "issue", f"{systems.CORE} · issuing renewal certificate", r["new_policy_id"])
        else:
            systems.step(tool_call_id, "claims", f"{systems.CORE} · claims history this term",
                         f"{r['claims_this_term']} claim(s)")
            systems.step(tool_call_id, "rating", f"{systems.RATING} · renewal re-rating",
                         f"SAR {r['current_premium']:,} → SAR {r['renewal_premium']:,}", 0.35, 0.6)
        return _ok(r)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@tool
def knowledge_search(query: str) -> str:
    """Search insurance knowledge documents (motor guide, claim process, policy servicing, FAQs,
    terms & conditions, and any uploaded documents) via ChromaDB. Use for coverage, exclusions,
    procedures and definitions. Works for guests. Cite results as [1], [2] in the answer."""
    try:
        return _ok(kb.search(query, k=4))
    except Exception as e:  # noqa: BLE001
        return _err(e)


ALL_TOOLS = [identify_customer, fetch_kyc_from_government, confirm_registration, lookup_vehicle,
             generate_health_quote, generate_quote, generate_life_quote, generate_savings_quote, generate_general_quote,
             purchase_policy, get_customer_profile, get_policy_details, create_claim,
             track_claim, renew_policy, knowledge_search]

# How the frontend should render each tool's output
TOOL_CARD_TYPES = {
    "identify_customer": "identity",
    "fetch_kyc_from_government": "kyc",
    "confirm_registration": "registered",
    "lookup_vehicle": "vehicle",
    "generate_quote": "quote",
    "generate_health_quote": "quote",
    "generate_life_quote": "quote",
    "generate_savings_quote": "quote",
    "generate_general_quote": "quote",
    "purchase_policy": "purchase",
    "get_customer_profile": "profile",
    "get_policy_details": "policies",
    "create_claim": "claim",
    "track_claim": "claim",
    "renew_policy": "renewal",
    "knowledge_search": "citations",
}
