"""Names of the (simulated) enterprise systems the Copilot "talks to" — shown in the What's happening panel.

The demo calls no real system: each step below is a short, timed simulation so the audience sees the request
travel through the platform (CRM → rating engine → policy admin → payment engine) and come back.
Rename the systems in backend/.env to match the client's landscape.
"""
from __future__ import annotations

import os
import random
import time
from typing import Any

from app.services.progress import progress

CRM = os.getenv("SYSTEM_CRM", "ESKA")                      # customer & product context
RATING = os.getenv("SYSTEM_RATING", "Neutrinos")           # rating / pricing engine
CORE = os.getenv("SYSTEM_CORE", "iFoundry")                # policy administration, product rules, claims
PAYMENTS = os.getenv("SYSTEM_PAYMENTS", "Payment Engine")  # instalments, VAT, collection
FAST = os.getenv("SYSTEM_STEPS_FAST", "") == "1"           # tests: no artificial latency

LINE_TARIFF = {"motor": "MOTOR-PVT", "health": "MED-IND", "life": "FT-PROT", "savings": "FT-SAV", "general": "PROP-HOME"}


def _sleep(lo: float, hi: float) -> None:
    if not FAST:
        time.sleep(random.uniform(lo, hi))


def step(tool_call_id: str | None, key: str, label: str, detail: str, lo: float = 0.15, hi: float = 0.35) -> None:
    progress(tool_call_id, key, label)
    _sleep(lo, hi)
    progress(tool_call_id, key, label, "done", detail)


def _fmt(n: float) -> str:
    return f"SAR {n:,.0f}"


def quote_steps(tool_call_id: str | None, q: dict[str, Any], customer_id: str | None, changed: str | None = None) -> None:
    """Simulated round trip for a quotation (or a re-quote after the customer moves a slider)."""
    line = q.get("line", "motor")
    tariff = LINE_TARIFF.get(line, line.upper())
    who = customer_id if customer_id and customer_id != "GUEST" else "guest session"
    p = q["premium"]
    step(tool_call_id, "crm", f"{CRM} · loading customer & product context", f"{who} · product {tariff} · channel AI Copilot")
    label = f"{RATING} · re-rating — {changed}" if changed else f"{RATING} · rating engine ({tariff} tariff)"
    n_factors = len(q.get("risk", {}).get("factors", [])) + len(q.get("breakdown", [])) + 3
    step(tool_call_id, "rating", label, f"{n_factors} rating factors · contribution {_fmt(p['total_premium'])}", 0.35, 0.7)
    step(tool_call_id, "rules", f"{CORE} · product rules & underwriting check",
         f"{q['plan']} · eligible · quote valid {q.get('validity_days', 15)} days")
    if line == "savings":
        pj = q.get("projection") or {}
        detail = f"{_fmt(p.get('monthly', 0))}/month · projected {_fmt(pj.get('mid', 0))} · VAT-exempt"
    elif line == "life":
        detail = f"{_fmt(p['total_premium'] / 12)}/month instalments · VAT-exempt"
    else:
        detail = f"{_fmt(p['total_premium'] / 12)}/month or {_fmt(p['total_premium'])}/year · VAT 15% {_fmt(p.get('gst', 0))}"
    step(tool_call_id, "payments", f"{PAYMENTS} · instalment schedule & VAT", detail)
