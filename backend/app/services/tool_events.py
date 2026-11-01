"""Shared formatting of tool activity for the "What's happening" panel."""
from __future__ import annotations

import json
import time
from typing import Any

TOOL_LABELS = {
    "identify_customer": "Looking you up in Customer 360",
    "fetch_kyc_from_government": "Verifying with Nafath · Yakeen",
    "lookup_vehicle": "Fetching vehicle from Elm",
    "confirm_registration": "Registering you in Customer 360",
    "generate_quote": "Generating motor quotation",
    "generate_health_quote": "Generating health quotation",
    "generate_general_quote": "Generating general (home) quotation",
    "generate_life_quote": "Generating life quotation",
    "generate_savings_quote": "Generating retirement & savings quotation",
    "reprice_quote": "Re-pricing your quote",
    "purchase_policy": "Checkout",
    "get_customer_profile": "Loading Customer 360 profile",
    "get_policy_details": "Looking up policies",
    "create_claim": "Registering claim",
    "track_claim": "Checking claim status",
    "renew_policy": "Calculating renewal",
    "knowledge_search": "Searching policy documents",
}

# never show these argument values in the panel
SENSITIVE_ARGS = {"id_number"}  # National ID / Iqama


def _now_ms() -> int:
    return int(time.time() * 1000)


def safe_args(args: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in (args or {}).items():
        if k in SENSITIVE_ARGS and isinstance(v, str) and len(v) > 4:
            out[k] = "•" * (len(v) - 4) + v[-4:]
        else:
            out[k] = v
    return out


def summarize_tool(name: str, payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        err = str(payload.get("error", "unknown error"))
        return "Customer not identified yet" if err.startswith("NOT_IDENTIFIED") else f"Failed: {err}"
    d = payload.get("data")
    try:
        if name == "identify_customer":
            return f"Matched {d['customer']['name']} ({d['customer']['customer_id']})" if d["found"] else "No registered customer found"
        if name == "fetch_kyc_from_government":
            if d.get("already_registered"):
                return f"Already registered as {d['customer']['customer_id']}"
            dr = d["draft"]
            return f"{dr['name']} · {dr['city']} · {len(dr['lookups'])} checks passed"
        if name == "confirm_registration":
            if not d["registered"]:
                return "Details updated — awaiting confirmation"
            x = d["excel"]
            return f"Added {d['customer']['customer_id']}" + (" · synced to Excel" if x["synced"] else " · Excel sync pending")
        if name == "lookup_vehicle":
            v = d["vehicle"]
            return f"{v['make_model']} {v.get('model_year', '')} · {v['registration_number']}"
        if name in ("generate_quote", "generate_health_quote", "generate_general_quote", "generate_life_quote",
                    "generate_savings_quote", "reprice_quote"):
            return (f"{d['plan']} · SAR {d['premium']['total_premium']:,} · risk {d['risk']['score']} "
                    f"({d['risk']['band']}) · {d['quote_id']}")
        if name == "purchase_policy":
            if d["status"] == "issued":
                return f"Issued {d['policy_id']} · SAR {d['total_premium']:,} paid by {d['payment']['method']}"
            uw = d["underwriting"]
            return f"Review: {d['plan']} · SAR {d['total_premium']:,}" + ("" if uw["accepted"] else " · underwriting referral")
        if name == "get_customer_profile":
            s = d["summary"]
            return (f"{d['customer']['name']} · {s['active_policies']} policies · "
                    f"{s['open_claims']} open claims · {s['renewals_due']} renewals due")
        if name == "get_policy_details":
            if isinstance(d, list):
                active = [p for p in d if p["status"] in ("Active", "Expiring")]
                due = sum(1 for p in active if p.get("renewal_due"))
                return f"{len(active)} active policies" + (f" · {due} due for renewal" if due else "")
            return f"{d['policy_id']} · {d['policy_type']} · {d['status']}"
        if name == "create_claim":
            return f"{d['claim_id']} registered on {d['policy_id']} · status {d['status']}"
        if name == "track_claim":
            if isinstance(d, list):
                return f"{len(d)} claims found"
            return f"{d['claim_id']} · {d['status']} · {d['progress']}% complete"
        if name == "renew_policy":
            if d["status"] == "renewed":
                return f"Renewed as {d['new_policy_id']} · SAR {d['renewal_premium']:,} paid"
            return (f"SAR {d['current_premium']:,} → SAR {d['renewal_premium']:,} · "
                    f"NCD {d['ncb_current']}% → {d['ncb_renewal']}%")
        if name == "knowledge_search":
            titles = sorted({h["title"] for h in d})
            return f"{len(d)} passages · " + ", ".join(titles[:3])
    except (KeyError, TypeError):
        pass
    return "Done"


def tool_call_event(call_id: str, name: str, args: dict) -> dict:
    return {"type": "tool_call", "id": call_id, "name": name, "label": TOOL_LABELS.get(name, name),
            "args": safe_args(args), "ts": _now_ms()}


def tool_result_event(call_id: str, name: str, raw: str) -> dict:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        payload = {"ok": False, "error": str(raw)}
    return {"type": "tool_result", "id": call_id, "name": name, "ok": bool(payload.get("ok")),
            "summary": summarize_tool(name, payload), "ts": _now_ms()}
