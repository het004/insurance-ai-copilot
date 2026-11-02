"""Policy purchase: choose a plan from a quote → review → simulated payment → policy issued → Customer 360.

Two calls, mirroring a real checkout:
  1. purchase(confirm=False)  → "review": plan, premium, insured vehicle, period, alternatives, payment options.
                                 Underwriting rules run here so problems surface before payment.
  2. purchase(confirm=True, payment_method=…) → proposal → underwriting → payment gateway (SIMULATED)
                                 → policy issued in the policies table → payment recorded → Excel synced.

⚠ The payment gateway is simulated: no money moves and no real gateway is called.
"""
from __future__ import annotations

import html
import json
import random
import re
import time
from datetime import date, datetime, timedelta
from typing import Any

from app.database import db, row_to_dict
from app.config import settings
from app.services import products
from app.services.excel_store import excel_store
from app.services.insurance_service import (InvalidRequest, NotFound, _sync_excel, create_product_quote, get_customer,
                                            list_policies)
from app.services.identity_service import normalize_plate
from app.services.progress import progress
from app.services import systems as sysm

QUOTE_VALIDITY_DAYS = 15
PAYMENT_METHODS = {
    "MADA": ("mada", "mada card authorised with 3-D Secure OTP"),
    "APPLE PAY": ("Apple Pay", "Payment approved with Face ID in Apple Pay"),
    "STC PAY": ("STC Pay", "Payment approved in the STC Pay app"),
    "CARD": ("Credit card", "3-D Secure OTP verified by the issuing bank"),
    "SADAD": ("SADAD", "SADAD bill paid through online banking"),
}


def normalize_method(m: str | None) -> tuple[str, str] | None:
    if not m:
        return None
    t = m.strip().upper().replace("-", " ")
    if re.search(r"\bMADA\b|DEBIT", t):
        return PAYMENT_METHODS["MADA"]
    if "APPLE" in t:
        return PAYMENT_METHODS["APPLE PAY"]
    if re.search(r"\bSTC\b", t):
        return PAYMENT_METHODS["STC PAY"]
    if "SADAD" in t or re.search(r"\bBANK(ING)?\b|TRANSFER", t):
        return PAYMENT_METHODS["SADAD"]
    if re.search(r"\bCARD\b|CREDIT|VISA|MASTERCARD|AMEX", t):
        return PAYMENT_METHODS["CARD"]
    return None


def _sleep(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))  # simulated latency so the progress panel shows each step


def _load_quote(customer_id: str, quote_id: str | None, line: str | None = None) -> dict[str, Any]:
    with db() as c:
        if quote_id:
            row = row_to_dict(c.execute("SELECT * FROM quotes WHERE quote_id=?", (quote_id.upper(),)).fetchone())
        else:  # latest un-purchased motor quote of this customer
            row = next((r for r in (row_to_dict(x) for x in c.execute(
                "SELECT * FROM quotes WHERE customer_id=? ORDER BY created_at DESC", (customer_id,)))
                        if isinstance(r["details"], dict) and products.line_of(r["details"]) in products.LINES
                        and (not line or products.line_of(r["details"]) == line)
                        and not r["details"].get("purchased_policy_id")), None)
    if not row or row["customer_id"] not in {customer_id, "GUEST"}:
        raise NotFound("No quotation found to purchase. Generate a quote first.")
    d = row["details"] if isinstance(row["details"], dict) else {}
    if products.line_of(d) not in products.LINES:
        raise InvalidRequest("This quotation can't be bought online — please contact us and we'll help.")
    d["line"] = products.line_of(d)
    d["params"] = products.params_of(d)
    if d.get("purchased_policy_id"):
        raise InvalidRequest(f"Quote {row['quote_id']} has already been purchased as policy {d['purchased_policy_id']}.")
    if row["customer_id"] == "GUEST":  # a guest quote becomes the customer's once they're verified
        with db() as c:
            d["customer_id"] = customer_id
            c.execute("UPDATE quotes SET customer_id=?, details=? WHERE quote_id=?",
                      (customer_id, json.dumps(d), row["quote_id"]))
    d["quote_id"] = row["quote_id"]
    d["created_at"] = d.get("created_at") or row["created_at"]
    return d


def _underwrite(customer: dict[str, Any], q: dict[str, Any]) -> list[str]:
    """Simple POC rules. Returns a list of blocking reasons (empty = accepted)."""
    issues = []
    if (customer.get("kyc_status") or "").lower() != "verified":
        issues.append("We need to update your KYC before we can issue a policy online — "
                      + ("your Iqama on file has expired. Please renew it on Absher and verify again with Nafath, "
                         "or our team will help you." if "iqama" in (customer.get("kyc_status") or "").lower()
                         else "please verify with Nafath, or our team will reach out to help."))
    issues += products.underwrite(q["line"], q["params"], q["coverage"])
    created = datetime.fromisoformat(str(q["created_at"])[:19])
    if datetime.now() - created > timedelta(days=QUOTE_VALIDITY_DAYS):
        issues.append(f"Quote {q['quote_id']} has expired (valid {QUOTE_VALIDITY_DAYS} days). Generate a fresh quote.")
    return issues


def pr_is_retirement(q: dict[str, Any]) -> bool:
    return q.get("coverage") == "retirement_plan" and "retirement_age" in q.get("params", {})


def _asset(q: dict[str, Any], registration: str | None, vahan: dict[str, Any] | None) -> tuple[str, str | None]:
    if q["line"] == "health":
        pr = q["params"]
        return f"Individual · age {pr.get('age') or pr.get('eldest_age')} · {pr.get('city', '')}".rstrip(" ·"), None
    if q["line"] == "savings" and pr_is_retirement(q):
        pr = q["params"]
        return (f"Retire at {pr['retirement_age']} · SAR {pr['monthly_contribution']:,.0f}/month · "
                f"{pr['fund'].title()} fund" + (f" · beneficiary {pr['beneficiary']}" if pr.get("beneficiary") else "")), None
    if q["line"] == "savings":
        pr = q["params"]
        return f"SAR {pr['monthly_contribution']:,.0f}/month · {pr['term_years']} years · age {pr['age']}", None
    if q["line"] in ("general", "home"):
        return f"{q['subject']} · {q['sum_insured_label']}", None
    if q["line"] == "life":
        pr = q["params"]
        return (f"Sum covered SAR {pr['sum_assured']:,.0f} · {pr['term_years']}-year term · age {pr['age']}"
                f"{' · smoker' if pr.get('smoker') else ''}"), None
    reg = normalize_plate(registration) if registration else None
    if registration and not reg:
        raise InvalidRequest(f"'{registration}' doesn't look like a Saudi plate (e.g. 1234 ABJ) or a 9-digit sequence number.")
    if vahan and (not reg or reg == vahan.get("registration_number")):
        return f"{vahan['make_model']} · {vahan['registration_number']}", vahan["registration_number"]
    age = "Brand new" if q["vehicle_age"] == 0 else f"{q['vehicle_age']:g} yrs old"
    return f"{q['vehicle_label']} ({age}) · {reg or 'registration pending'}", reg


def purchase(customer_id: str, *, quote_id: str | None = None, coverage: str | None = None, confirm: bool = False,
             payment_method: str | None = None, registration_number: str | None = None,
             default_quote_id: str | None = None, vahan_vehicle: dict[str, Any] | None = None,
             tool_call_id: str | None = None) -> dict[str, Any]:
    customer = get_customer(customer_id)
    q = _load_quote(customer_id, quote_id or default_quote_id)

    # switching plan → re-price the same risk with the chosen plan
    cov = products.normalize_plan(q["line"], coverage) if coverage else None
    if coverage and not cov:
        names = ", ".join(a["plan"] for a in q["alternatives"])
        raise InvalidRequest(f"Plan not recognised. For this quote choose one of: {names}.")
    if cov and cov != q["coverage"]:
        q = create_product_quote(customer_id, q["line"], q["params"], cov)
        q["params"] = products.params_of(q)

    issues = _underwrite(customer, q)
    asset, reg = _asset(q, registration_number, vahan_vehicle)
    start = date.today()
    years = int(q["params"].get("term_years") or 1) if q["line"] in ("life", "savings") else 1
    end = (date(start.year + years, start.month, min(start.day, 28)) - timedelta(days=1)) if years > 1 \
        else start + timedelta(days=364)
    notes = []
    same_line = [p for p in list_policies(customer_id) if p["status"] in ("Active", "Expiring")
                 and products.policy_type(q["line"], q["params"]) == p["policy_type"]]
    if same_line:
        notes.append(f"You already have {same_line[0]['product_name']} ({same_line[0]['policy_id']}) with us — "
                     "this will be an additional policy.")
    review = {
        "line": q["line"], "line_label": products.LINES[q["line"]]["label"],
        "quote_id": q["quote_id"], "plan": q["plan"], "coverage": q["coverage"], "plan_summary": q["plan_summary"],
        "subject": q["subject"], "sum_insured": q["sum_insured"], "sum_insured_label": q["sum_insured_label"],
        "breakdown": q["breakdown"], "gst_note": q.get("gst_note"),
        "vehicle_type": q.get("vehicle_type"), "vehicle_label": q.get("vehicle_label") or products.LINES[q["line"]]["label"],
        "vehicle_age": q.get("vehicle_age"),
        "location": q["location"], "insured_asset": asset, "registration_number": reg,
        "premium": q["premium"], "total_premium": q["premium"]["total_premium"], "idv": q["premium"].get("idv", 0),
        "notes": notes,
        "includes": q["coverage_details"]["includes"][:6], "start_date": start.isoformat(), "end_date": end.isoformat(),
        "alternatives": q["alternatives"], "recommendation": q["recommendation"],
        "retirement": q.get("retirement"), "projection": q.get("projection"),
        "customer": {"customer_id": customer_id, "name": customer["name"]},
        "payment_methods": [v[0] for v in PAYMENT_METHODS.values()],
        "underwriting": {"accepted": not issues, "issues": issues},
    }
    if not confirm:
        return {"status": "review", **review,
                "next_step": "Show the plan and contribution. Ask which payment method (mada, Apple Pay, STC Pay, credit card or SADAD) and "
                             "for explicit confirmation, then call purchase_policy(confirm=true, payment_method=…)."
                             if not issues else "Explain the underwriting issue and offer the suggested alternative."}
    if issues:
        raise InvalidRequest(" ".join(issues))
    method = normalize_method(payment_method)
    if not method:
        raise InvalidRequest("Ask the customer how they'd like to pay: mada, Apple Pay, STC Pay, credit card or SADAD.")
    method_name, auth_note = method

    # ---------------------------------------------------------------- simulated checkout
    def step(key: str, label: str, lo: float, hi: float, detail: str) -> None:
        progress(tool_call_id, key, label)
        _sleep(lo, hi)
        progress(tool_call_id, key, label, "done", detail)

    proposal_no = f"PRP-{date.today():%y%m}-{random.randint(10000, 99999)}"
    step("proposal", f"{sysm.CORE} · creating proposal", 0.2, 0.4, f"{proposal_no} · {customer['name']}")
    uw_detail = {"health": "Accepted · no medical review required", "general": "Accepted · no survey required",
                 "life": "Accepted · no medical examination required",
                 "savings": "Accepted · source of funds verified"}
    if q["line"] == "savings" and (q["params"].get("declarations") or {}):
        step("aml", f"{sysm.CRM} · FATCA / CRS, PEP & sanctions screening", 0.3, 0.5, "Clear · declarations recorded")
    step("underwriting", f"{sysm.CORE} · underwriting rules", 0.3, 0.6, uw_detail.get(q["line"], "Accepted · standard risk"))
    step("schedule", f"{sysm.PAYMENTS} · building contribution schedule", 0.2, 0.4,
         f"SAR {q['premium'].get('instalment') or q['premium']['total_premium']:,} · "
         + ("per " + q['premium']['frequency'].replace('semi_annual', 'half-year').replace('ly', '').replace('annual', 'year')
            if q['premium'].get('frequency') else "annual") + " · first collection today")
    gateway = f"{sysm.PAYMENTS} → payment gateway (sandbox — simulated)"
    order = f"order_{random.randbytes(7).hex()}"
    step("gateway", f"{sysm.PAYMENTS} · opening {method_name} session", 0.3, 0.5, f"{order}")
    step("auth", "Waiting for payment authorisation", 0.8, 1.3, auth_note)
    pay_id = f"pay_{random.randbytes(7).hex()}"
    bank_ref = f"{random.randint(10**11, 10**12 - 1)}"
    step("captured", f"Payment of SAR {q['premium']['total_premium']:,} captured", 0.2, 0.4, f"{pay_id} · bank ref {bank_ref}")

    progress(tool_call_id, "issue", f"{sysm.CORE} · issuing Takaful certificate")
    policy_id = f"{products.policy_prefix(q['line'], q['params'])}-{random.randint(100000, 999999)}"
    now = datetime.now().isoformat(timespec="seconds")
    details = {
        "add_ons": [i for i in q["coverage_details"]["includes"] if not i.lower().startswith(("own damage", "all third", "everything"))][:5],
        "line": q["line"], "params": q["params"],
        "coverage": q["coverage"], "registration_number": reg, "location": q["location"], "zone": q.get("zone"),
        "quote_id": q["quote_id"], "proposal_no": proposal_no, "payment_id": pay_id,
        "purchased_via": "AI Copilot chat", "purchased_at": now,
    }
    with db() as c:
        c.execute("INSERT INTO policies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (policy_id, customer_id, products.policy_type(q["line"], q["params"]), q["plan"], asset, q["sum_insured"] or None,
                   q["premium"]["total_premium"], start.isoformat(), end.isoformat(), "Active", 0, json.dumps(details)))
        c.execute("INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (pay_id, customer_id, policy_id, q["quote_id"], q["premium"]["total_premium"], method_name, "Captured",
                   bank_ref, gateway, now))
        qd = row_to_dict(c.execute("SELECT details FROM quotes WHERE quote_id=?", (q["quote_id"],)).fetchone())["details"]
        qd["purchased_policy_id"] = policy_id
        c.execute("UPDATE quotes SET details=? WHERE quote_id=?", (json.dumps(qd), q["quote_id"]))
    progress(tool_call_id, "issue", f"{sysm.CORE} · issuing Takaful certificate", "done", policy_id)
    step("document", f"{sysm.CORE} · generating certificate & schedule", 0.2, 0.4, "Certificate PDF ready")
    step("crm", f"{sysm.CRM} · updating customer profile", 0.15, 0.3, f"{customer_id} · new holding {policy_id}")

    progress(tool_call_id, "excel", "Updating Customer 360 (art_customer_360.xlsx)")
    _sync_excel()
    st = excel_store.status()
    synced = not st["pending_sync"]
    progress(tool_call_id, "excel", "Updating Customer 360 (art_customer_360.xlsx)", "done" if synced else "error",
             "Policies + Payments sheets updated" if synced else st["last_error"])

    return {"status": "issued", **review, "policy_id": policy_id, "proposal_no": proposal_no,
            "payment": {"payment_id": pay_id, "amount": q["premium"]["total_premium"], "method": method_name,
                        "status": "Captured", "bank_reference": bank_ref, "gateway": gateway, "paid_at": now},
            "document_url": f"/api/policies/{policy_id}/document",
            "excel": {"synced": synced, "warning": None if synced else st["last_error"], "file": "art_customer_360.xlsx"},
            "next_step": "Policy is active immediately. Schedule emailed to the customer (simulated)."}


def list_payments(customer_id: str) -> list[dict[str, Any]]:
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM payments WHERE customer_id=? ORDER BY created_at DESC",
                                           (customer_id,))]


# ---------------------------------------------------------------- policy schedule (HTML)
def policy_document(policy_id: str) -> str:
    with db() as c:
        p = row_to_dict(c.execute("SELECT * FROM policies WHERE policy_id=?", (policy_id.upper(),)).fetchone())
        pay = c.execute("SELECT * FROM payments WHERE policy_id=?", (policy_id.upper(),)).fetchone()
    if not p:
        raise NotFound(f"Policy {policy_id} not found")
    cust = get_customer(p["customer_id"])
    d = p.get("details") or {}
    e = html.escape
    pt = p["policy_type"]
    kind = "Motor" if pt.startswith("Motor") else pt
    kind = {"General - Home": "General", "Retirement & Savings": "Savings"}.get(pt, kind)
    asset_label = {"Motor": "Insured vehicle", "Health": "Insured members", "General": "Insured property",
                   "Life": "Covered person", "Savings": "Plan"}.get(kind, "Insured")
    si_label = {"Motor": "Insured market value", "Health": "Annual limit per member", "General": "Sum insured",
                "Life": "Sum covered", "Savings": "Takaful protection"}.get(kind, "Sum insured")
    rows = [("Policy number", p["policy_id"]), ("Product", f"{pt} · {p['product_name']}"),
            ("Participant", cust["name"]), ("Customer ID", cust["id"]), ("Address", cust.get("address", "")),
            (asset_label, p["insured_asset"]), ("Period of insurance", f"{p['start_date']} to {p['end_date']} (both days inclusive)"),
            (si_label, f"SAR {(p['sum_insured'] or 0):,.0f}" if p["sum_insured"] else "Not applicable (third-party liability)"),
            ("Annual contribution", f"SAR {p['premium']:,.0f}" + (" (VAT-exempt)" if kind in ("Life", "Savings") else " (incl. 15% VAT)"))]
    if kind == "Motor":
        rows.append(("No Claim Discount", f"{p['ncb_percent']}%"))
    if pay:
        rows.append(("Payment", f"{pay['method']} · {pay['payment_id']} · bank ref {pay['reference']}"))
    if d.get("proposal_no"):
        rows.append(("Proposal / quote", f"{d['proposal_no']} / {d.get('quote_id', '')}"))
    covers = "".join(f"<li>{e(a)}</li>" for a in d.get("add_ons", []))
    body = "".join(f"<tr><th>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in rows)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Policy schedule {e(p['policy_id'])}</title>
<style>
 body{{font-family:Poppins,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f3f7fc;color:#1c2d4f;margin:0;padding:24px}}
 .doc{{max-width:760px;margin:auto;background:#fff;border-radius:16px;box-shadow:0 8px 30px #0001;overflow:hidden}}
 header{{background:linear-gradient(135deg,#009ade,#1d6fc4 55%,#22447d);color:#fff;padding:24px 28px}}
 header h1{{margin:0;font-size:20px}} header p{{margin:4px 0 0;opacity:.85;font-size:13px}}
 .wm{{background:#fff4d6;color:#8a5a00;font-size:12px;padding:8px 28px}}
 table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{text-align:left;padding:10px 28px;border-bottom:1px solid #eceef6;vertical-align:top}}
 th{{width:38%;color:#5d6080;font-weight:500}} section{{padding:16px 28px}} h2{{font-size:14px;margin:0 0 8px}}
 li{{font-size:14px;margin:4px 0}} footer{{font-size:11px;color:#7a7d99;padding:16px 28px 24px}}
 .print{{float:right;background:#fff;color:#1d6fc4;border:0;border-radius:10px;padding:8px 14px;font-weight:600;cursor:pointer}}
 @media print{{.print,.wm{{display:none}} body{{background:#fff;padding:0}} .doc{{box-shadow:none}}}}
</style></head><body><div class="doc">
<header><button class="print" onclick="window.print()">Print / Save PDF</button>
<h1>{e(settings.INSURER_NAME)}</h1><p>{'Certificate of Motor Takaful' if kind == 'Motor' else 'Takaful Certificate'} · {e(kind)} · issued {e(str(d.get('purchased_at', p['start_date'])))}</p></header>
<div class="wm">DEMO DOCUMENT — generated by a proof of concept for {e(settings.INSURER_NAME)}. Not a valid Takaful contract.</div>
<table>{body}</table>
<section><h2>Key covers</h2><ul>{covers or '<li>As per policy wordings</li>'}</ul></section>
<footer>Claims: tell our AI Copilot what happened (for example “I had an accident” or “I was admitted to hospital”) or call our
24/7 helpline (demo). Motor accidents must be reported to Najm (or Taqdeer where applicable). This schedule is to be read with the policy wordings in our knowledge base.</footer>
</div></body></html>"""
