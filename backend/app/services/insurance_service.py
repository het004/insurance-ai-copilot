"""Business logic shared by REST routes AND agent tools (single source of truth)."""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from typing import Any

from app.database import db, row_to_dict, rows_to_dicts
from app.services import quote_engine
from app.services.excel_store import excel_store

CLAIM_FLOW = ["Reported", "Under Review", "Assessment", "Approved", "Closed"]
CLAIM_NOTES = {
    "Under Review": "Claim documents verified by the claims desk",
    "Assessment": "Surveyor assigned — inspection scheduled within 24 hours",
    "Approved": "Claim approved — settlement initiated",
    "Closed": "Settlement completed and claim closed",
}
NCB_NEXT = {0: 15, 15: 20, 20: 25, 25: 30, 30: 30}  # Saudi No Claim Discount steps


class NotFound(Exception):
    pass


class InvalidRequest(Exception):
    pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{date.today():%y%m}-{random.randint(1000, 9999)}"


def _days_to(end: str) -> int:
    return (date.fromisoformat(end) - date.today()).days


def _decorate_policy(p: dict[str, Any]) -> dict[str, Any]:
    p["days_to_expiry"] = _days_to(p["end_date"])
    if p["status"] in {"Active", "Expiring"}:
        p["status"] = "Expiring" if 0 <= p["days_to_expiry"] <= 30 else "Active" if p["days_to_expiry"] > 30 else "Lapsed"
    p["renewal_due"] = p["status"] == "Expiring"
    return p


# --------------------------------------------------------------------- customers
def _public_customer(c: dict[str, Any]) -> dict[str, Any]:
    c = {k: v for k, v in c.items() if k != "id_hash"}
    c["id"] = c["customer_id"]
    return c


def list_customers() -> list[dict[str, Any]]:
    """Customer master comes from the Customer 360 Excel workbook."""
    return [_public_customer(c) for c in excel_store.customers()]


def get_customer(customer_id: str) -> dict[str, Any]:
    cust = excel_store.get(customer_id or "")
    if not cust:
        raise NotFound(f"Customer {customer_id} not found in Customer 360")
    return _public_customer(cust)


def _payments(customer_id: str) -> list[dict[str, Any]]:
    with db() as c:
        return rows_to_dicts(c.execute("SELECT * FROM payments WHERE customer_id=? ORDER BY created_at DESC", (customer_id,)))


def _sync_excel() -> None:
    """Mirror policies/claims/quotes/payments into art_customer_360.xlsx (best effort)."""
    excel_store.sync()


def get_customer_360(customer_id: str) -> dict[str, Any]:
    customer = get_customer(customer_id)
    policies = list_policies(customer_id)
    claims = list_claims(customer_id)
    quotes = list_quotes(customer_id)
    renewals = [p for p in policies if p["renewal_due"]]
    active = [p for p in policies if p["status"] in {"Active", "Expiring"}]
    open_claims = [c for c in claims if c["status"] not in {"Closed"}]

    actions: list[dict[str, str]] = []
    for p in renewals:
        actions.append({"type": "renewal", "priority": "high",
                        "title": f"Renew {p['policy_type']} policy",
                        "detail": f"{p['policy_id']} expires in {p['days_to_expiry']} days. " +
                                  (f"Renew now to keep your {p['ncb_percent']}% No Claim Discount." if p["policy_type"].startswith("Motor")
                                   else "Renew without a break to stay continuously covered."),
                        "prompt": f"Renew my policy {p['policy_id']}"})
    for cl in open_claims:
        actions.append({"type": "claim", "priority": "medium",
                        "title": f"Track claim {cl['claim_id']}",
                        "detail": f"Currently '{cl['status']}'. {cl.get('remarks') or ''}".strip(),
                        "prompt": f"What is the status of claim {cl['claim_id']}?"})
    types = {p["policy_type"] for p in active}
    if "Health" in types:
        actions.append({"type": "cross_sell", "priority": "low", "title": "Upgrade to Health Premier",
                        "detail": "Upgrade to Health Premier for the VIP network, no co-pay and worldwide emergency cover.",
                        "prompt": "What does Health Premier cover?"})
    else:
        actions.append({"type": "cross_sell", "priority": "medium", "title": "Get individual health cover",
                        "detail": "No active health cover found. Individual plans start from about SAR 3,000 a year.",
                        "prompt": "I want an individual health plan"})
    if not types:
        actions.insert(0, {"type": "quote", "priority": "high", "title": "Get a first motor quote",
                           "detail": "New customer with no active policies yet.",
                           "prompt": "I need insurance for my car"})
    if "Life" not in types:
        actions.append({"type": "cross_sell", "priority": "low", "title": "Protect your family's future",
                        "detail": "Life Protect gives SAR 1–2 million sum covered from around SAR 250 a month.",
                        "prompt": "I want a life insurance quote"})
    if "Retirement & Savings" not in types:
        actions.append({"type": "cross_sell", "priority": "low", "title": "Start saving for retirement",
                        "detail": "A Retirement Plan from SAR 300 a month builds a fund to age 60, with Takaful protection.",
                        "prompt": "I want a retirement savings plan"})
    if "General - Home" not in types:
        actions.append({"type": "cross_sell", "priority": "low", "title": "Insure your home",
                        "detail": "Home Plus covers your home and contents against fire, flood and burglary.",
                        "prompt": "What does home insurance cover?"})
    open_quotes = [q for q in quotes if not (isinstance(q.get("details"), dict) and q["details"].get("purchased_policy_id"))]
    for q in open_quotes[:1]:
        actions.append({"type": "quote", "priority": "low", "title": f"Follow up on quote {q['quote_id']}",
                        "detail": f"{q.get('product')} at SAR {q['premium']:,.0f} — not yet purchased.",
                        "prompt": f"Tell me more about quote {q['quote_id']}"})

    return {
        "customer": customer,
        "summary": {
            "active_policies": len(active),
            "total_annual_premium": round(sum(p["premium"] for p in active)),
            "total_sum_insured": round(sum(p["sum_insured"] or 0 for p in active)),
            "open_claims": len(open_claims),
            "renewals_due": len(renewals),
            "quotes": len(quotes),
        },
        "policies": policies,
        "claims": claims,
        "quotes": quotes,
        "renewals": renewals,
        "recommended_actions": actions,
        "conversations": recent_interactions(customer_id, 8),
        "payments": _payments(customer_id),
        "excel": excel_store.status(),
    }


# --------------------------------------------------------------------- policies
def list_policies(customer_id: str) -> list[dict[str, Any]]:
    with db() as c:
        rows = rows_to_dicts(c.execute(
            "SELECT * FROM policies WHERE customer_id=? ORDER BY end_date", (customer_id,)))
    return [_decorate_policy(p) for p in rows]


def get_policy(policy_id: str, customer_id: str | None = None) -> dict[str, Any]:
    with db() as c:
        p = row_to_dict(c.execute("SELECT * FROM policies WHERE policy_id=?", (policy_id.upper(),)).fetchone())
    if not p or (customer_id and p["customer_id"] != customer_id):
        raise NotFound(f"Policy {policy_id} not found for this customer")
    return _decorate_policy(p)


def _claims_in_term(policy: dict[str, Any]) -> int:
    with db() as c:
        return c.execute(
            "SELECT COUNT(*) FROM claims WHERE policy_id=? AND incident_date>=? AND incident_type NOT LIKE 'Windshield%'",
            (policy["policy_id"], policy["start_date"])).fetchone()[0]


def renewal_quote(policy_id: str, customer_id: str | None = None) -> dict[str, Any]:
    p = get_policy(policy_id, customer_id)
    if p["status"] == "Renewed":
        raise InvalidRequest(f"Policy {policy_id} has already been renewed")
    claims = _claims_in_term(p)
    is_motor = p["policy_type"].startswith("Motor")
    old_ncb = p["ncb_percent"] or 0
    if is_motor:
        new_ncb = 0 if claims else NCB_NEXT.get(old_ncb, old_ncb)
        od_share = 0.7 * p["premium"]
        od_before_ncb = od_share / (1 - old_ncb / 100) if old_ncb < 100 else od_share
        od_new = od_before_ncb * 1.04 * (1 - new_ncb / 100)   # 4% claims-cost inflation
        new_premium = od_new + 0.3 * p["premium"] * 1.03       # TP revision ~3%
        sum_insured = round((p["sum_insured"] or 0) * 0.9, -2)  # IDV depreciates a year
        recommendation = ("Claim-free year — your No Claim Discount steps up from "
                          f"{old_ncb}% to {new_ncb}%." if not claims else
                          "A claim was made this year so your No Claim Discount resets to 0%.")
        add_on_tip = "Add agency repair and a replacement car for about SAR 600 more." \
            if "Motorcycle" not in p["policy_type"] else "Add rider personal accident cover for SAR 75."
    else:
        new_ncb = old_ncb
        new_premium = p["premium"] * (1.0 if p["policy_type"] in ("Life", "Retirement & Savings") else 1.06)
        sum_insured = p["sum_insured"]
        recommendation = {"Life": "Your life contribution is level for the whole term — renewing keeps your cover in force.",
                          "Retirement & Savings": "Keep contributing to stay on track for your goal.",
                          "Health": "Renew without a break so chronic-condition cover and your network continue."}.get(
            p["policy_type"], "Renew without a break to stay continuously covered.")
        add_on_tip = {"Health": "Consider Health Premier for the VIP network and no co-pay.",
                      "Life": "You can increase your sum covered at renewal with a short health declaration.",
                      "Retirement & Savings": "You can top up or raise your monthly contribution any time."}.get(
            p["policy_type"], "Consider Home Premier to add valuables and personal liability cover.")
    discount_early = 0.02 if p["days_to_expiry"] > 7 else 0.0
    new_premium *= (1 - discount_early)
    new_start = max(date.fromisoformat(p["end_date"]) + timedelta(days=1), date.today())
    return {
        "policy": p,
        "claims_this_term": claims,
        "current_premium": round(p["premium"]),
        "renewal_premium": round(new_premium),
        "change_percent": round((new_premium / p["premium"] - 1) * 100, 1),
        "ncb_current": old_ncb,
        "ncb_renewal": new_ncb,
        "early_renewal_discount_percent": int(discount_early * 100),
        "new_sum_insured": sum_insured,
        "new_start_date": new_start.isoformat(),
        "new_end_date": (new_start + timedelta(days=364)).isoformat(),
        "recommendation": recommendation,
        "add_on_tip": add_on_tip,
    }


def renew_policy(policy_id: str, confirm: bool = False, customer_id: str | None = None) -> dict[str, Any]:
    rq = renewal_quote(policy_id, customer_id)
    if not confirm:
        return {"status": "quote", **rq,
                "next_step": "Ask the customer to confirm; then call renew_policy again with confirm=true."}
    p = rq["policy"]
    new_id = f"{p['policy_id'].rsplit('-', 1)[0]}-{random.randint(100000, 999999)}"
    with db() as c:
        c.execute(
            "INSERT INTO policies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (new_id, p["customer_id"], p["policy_type"], p["product_name"], p["insured_asset"],
             rq["new_sum_insured"], rq["renewal_premium"], rq["new_start_date"], rq["new_end_date"],
             "Active", rq["ncb_renewal"], json.dumps({**(p.get("details") or {}), "renewed_from": p["policy_id"]})))
        c.execute("UPDATE policies SET status='Renewed' WHERE policy_id=?", (p["policy_id"],))
    _sync_excel()
    return {"status": "renewed", **rq, "new_policy_id": new_id,
            "payment": {"amount": rq["renewal_premium"], "mode": "Mock payment — auto-approved",
                        "reference": f"PAY{random.randint(10**8, 10**9 - 1)}"},
            "next_step": "Policy document will be emailed within 15 minutes."}


# --------------------------------------------------------------------- quotes
def create_quote(customer_id: str, vehicle_type: str, vehicle_age: float, coverage: str,
                 location: str, ncb_percent: int = 0) -> dict[str, Any]:
    """Motor quote (kept for the original API/tool signature)."""
    return save_quote(customer_id, quote_engine.calculate_quote(vehicle_type, vehicle_age, coverage, location, ncb_percent))


def create_product_quote(customer_id: str, line: str, params: dict[str, Any], plan: str | None = None,
                         sync: bool = True) -> dict[str, Any]:
    """Quote any portfolio we sell online: motor, health, life, savings or general."""
    from app.services import products

    return save_quote(customer_id, products.quote(line, params, plan), sync)


def get_quote(quote_id: str) -> dict[str, Any]:
    with db() as c:
        row = row_to_dict(c.execute("SELECT * FROM quotes WHERE quote_id=?", (quote_id.upper(),)).fetchone())
    if not row or not isinstance(row.get("details"), dict):
        raise NotFound(f"Quote {quote_id} not found")
    return row


def save_quote(customer_id: str, q: dict[str, Any], sync: bool = True) -> dict[str, Any]:
    q["quote_id"] = _new_id("QT")
    q["customer_id"] = customer_id
    q["created_at"] = _now()
    with db() as c:
        c.execute("INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?)",
                  (q["quote_id"], customer_id, q["plan"], q["premium"]["total_premium"], q["coverage"],
                   q["risk"]["score"], json.dumps(q), q["created_at"]))
    if sync:
        _sync_excel()
    return q


def list_quotes(customer_id: str) -> list[dict[str, Any]]:
    with db() as c:
        return rows_to_dicts(c.execute(
            "SELECT * FROM quotes WHERE customer_id=? ORDER BY created_at DESC", (customer_id,)))


# --------------------------------------------------------------------- claims
def _timeline(conn, claim_id: str) -> list[dict[str, Any]]:
    events = rows_to_dicts(conn.execute(
        "SELECT status, note, created_at FROM claim_events WHERE claim_id=? ORDER BY id", (claim_id,)))
    done = {e["status"]: e for e in events}
    return [{"status": s, "completed": s in done, "note": done.get(s, {}).get("note"),
             "at": done.get(s, {}).get("created_at")} for s in CLAIM_FLOW]


def _next_steps(claim: dict[str, Any]) -> list[str]:
    steps = {
        "Reported": ["Get a Najm (or Taqdeer) accident report if you haven't already",
                     "Upload 4 photos of the damage, your driving licence and Istimara",
                     "A claims officer will call you within 2 hours"],
        "Under Review": ["Our team is verifying documents — no action needed",
                         "A surveyor will be assigned within 24 hours"],
        "Assessment": ["Surveyor inspection in progress", "Approve the repair estimate when shared with you"],
        "Approved": ["Repairs can begin at the workshop or agency", "We settle directly with the repairer"],
        "Closed": ["Claim settled. Share feedback on your experience"],
    }
    s = steps.get(claim["status"], [])
    if "Health" in (claim.get("incident_type") or "") and claim["status"] == "Reported":
        s = ["Show your Al Rajhi Takaful medical card or ID at the hospital's insurance desk",
             "Pre-approval is usually decided within 1 hour", "Keep original invoices for any reimbursement"]
    if "Home" in (claim.get("incident_type") or "") and claim["status"] == "Reported":
        s = ["Take photos before cleaning up and prevent further damage if safe",
             "For burglary, file a police report and share it with us", "A surveyor visits within 48 hours"]
    if "theft" in (claim.get("incident_type") or "").lower():
        s = ["Report the theft to the police within 24 hours", "Share the police report and both original keys",
             "Keep the Istimara copy ready"] + s[2:]
    return s


def get_claim(claim_id: str, customer_id: str | None = None) -> dict[str, Any]:
    with db() as c:
        cl = row_to_dict(c.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id.upper(),)).fetchone())
        if not cl or (customer_id and cl["customer_id"] != customer_id):
            raise NotFound(f"Claim {claim_id} not found for this customer")
        cl["timeline"] = _timeline(c, cl["claim_id"])
    cl["next_steps"] = _next_steps(cl)
    cl["progress"] = round((CLAIM_FLOW.index(cl["status"]) + 1) / len(CLAIM_FLOW) * 100)
    return cl


def list_claims(customer_id: str) -> list[dict[str, Any]]:
    with db() as c:
        ids = [r[0] for r in c.execute(
            "SELECT claim_id FROM claims WHERE customer_id=? ORDER BY created_at DESC", (customer_id,))]
    return [get_claim(i) for i in ids]


def _infer_incident_type(description: str) -> str:
    d = description.lower()
    for kw, label in [("theft", "Theft"), ("stolen", "Theft"), ("flood", "Flood / Natural Calamity"),
                      ("fire", "Fire"), ("windshield", "Windshield"), ("glass", "Windshield"),
                      ("hospital", "Health - Hospitalisation"), ("surgery", "Health - Hospitalisation"),
                      ("admitted", "Health - Hospitalisation"),
                      ("burglary", "Home - Burglary"), ("break-in", "Home - Burglary"), ("broke into", "Home - Burglary"),
                      ("my house", "Home - Damage"), ("my home", "Home - Damage"), ("my flat", "Home - Damage"),
                      ("my apartment", "Home - Damage"), ("pipe burst", "Home - Damage"), ("seepage", "Home - Damage"),
                      ("third party", "Accident - Third Party"), ("hit someone", "Accident - Third Party")]:
        if kw in d:
            return label
    return "Accident - Own Damage"


TWO_WHEELER_WORDS = ("bike", "scooter", "motorcycle", "motorbike", "helmet")


def _pick_policy(customer_id: str, policy_id: str | None, incident_type: str, description: str = "") -> dict[str, Any]:
    if policy_id:
        return get_policy(policy_id, customer_id)
    candidates = [p for p in list_policies(customer_id) if p["status"] in {"Active", "Expiring"}]
    if incident_type.startswith("Health"):
        matching = [p for p in candidates if p["policy_type"] == "Health"]
    elif incident_type.startswith("Home"):
        matching = [p for p in candidates if p["policy_type"] == "Home"]
    else:
        motor = [p for p in candidates if p["policy_type"].startswith("Motor")]
        d = description.lower()
        # match the asset named in the description (e.g. "Creta", "Activa"), else bike words, else prefer car
        named = [p for p in motor if any(w in d for w in p["insured_asset"].lower().split()[:2] if len(w) > 3)]
        if named:
            matching = named
        elif any(w in d for w in TWO_WHEELER_WORDS):
            matching = [p for p in motor if "Motorcycle" in p["policy_type"]] or motor
        else:
            order = {"Motor - Car": 0, "Motor - Motorcycle": 1}
            matching = sorted(motor, key=lambda p: order.get(p["policy_type"], 3))
    if not matching:
        raise InvalidRequest("No active policy found that covers this incident")
    return matching[0]


def create_claim(customer_id: str, description: str, incident_date: str | None = None,
                 location: str | None = None, policy_id: str | None = None,
                 incident_type: str | None = None, estimated_amount: float | None = None) -> dict[str, Any]:
    if not description or len(description.strip()) < 5:
        raise InvalidRequest("Please describe what happened")
    incident_type = incident_type or _infer_incident_type(description)
    policy = _pick_policy(customer_id, policy_id, incident_type, description)
    if policy["status"] not in {"Active", "Expiring"}:
        raise InvalidRequest(f"Policy {policy['policy_id']} is {policy['status']} and cannot be claimed against")
    inc_date = incident_date or date.today().isoformat()
    try:
        d = date.fromisoformat(inc_date)
    except ValueError as e:
        raise InvalidRequest("incident_date must be YYYY-MM-DD") from e
    if d > date.today():
        raise InvalidRequest("Incident date cannot be in the future")
    if not (date.fromisoformat(policy["start_date"]) <= d <= date.fromisoformat(policy["end_date"])):
        raise InvalidRequest("Incident date is outside the policy period")
    claim_id = _new_id("CLM")
    now = _now()
    with db() as c:
        c.execute("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (claim_id, customer_id, policy["policy_id"], inc_date, incident_type, description.strip(),
                   location or "Not specified", estimated_amount, "Reported",
                   "First notice of loss registered by AI Copilot", now, now))
        c.execute("INSERT INTO claim_events (claim_id,status,note,created_at) VALUES (?,?,?,?)",
                  (claim_id, "Reported", "First notice of loss registered via AI Copilot", now))
    _sync_excel()
    claim = get_claim(claim_id)
    claim["policy"] = {k: policy[k] for k in ("policy_id", "policy_type", "product_name", "insured_asset")}
    return claim


def advance_claim(claim_id: str) -> dict[str, Any]:
    cl = get_claim(claim_id)
    idx = CLAIM_FLOW.index(cl["status"])
    if idx == len(CLAIM_FLOW) - 1:
        return cl
    nxt = CLAIM_FLOW[idx + 1]
    now = _now()
    with db() as c:
        c.execute("UPDATE claims SET status=?, remarks=?, updated_at=? WHERE claim_id=?",
                  (nxt, CLAIM_NOTES[nxt], now, cl["claim_id"]))
        c.execute("INSERT INTO claim_events (claim_id,status,note,created_at) VALUES (?,?,?,?)",
                  (cl["claim_id"], nxt, CLAIM_NOTES[nxt], now))
    _sync_excel()
    return get_claim(claim_id)


# --------------------------------------------------------------------- interactions
def log_interaction(session_id: str, customer_id: str, role: str, content: str,
                    tools: list[str] | None = None) -> None:
    with db() as c:
        c.execute("INSERT INTO interactions (session_id,customer_id,role,content,tools,created_at) "
                  "VALUES (?,?,?,?,?,?)", (session_id, customer_id, role, content, json.dumps(tools or []), _now()))


def recent_interactions(customer_id: str, limit: int = 6) -> list[dict[str, Any]]:
    with db() as c:
        rows = rows_to_dicts(c.execute(
            """SELECT u.session_id, u.content AS prompt, u.created_at,
                      (SELECT a.content FROM interactions a WHERE a.session_id=u.session_id AND a.role='assistant'
                        AND a.id>u.id ORDER BY a.id LIMIT 1) AS reply,
                      (SELECT a.tools FROM interactions a WHERE a.session_id=u.session_id AND a.role='assistant'
                        AND a.id>u.id ORDER BY a.id LIMIT 1) AS tools
               FROM interactions u WHERE u.role='user' AND u.customer_id=? ORDER BY u.id DESC LIMIT ?""",
            (customer_id, limit)))
    return rows
