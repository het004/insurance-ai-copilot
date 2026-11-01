"""Live re-pricing when the customer moves a slider / toggle on a quote card.

Streams the same events as a chat turn (run_started → step → tool_call → tool_progress* → tool_result → final)
so the "What's happening" panel shows the request going to the rating engine, rules and payment engine and
coming back. The new quote replaces the card in place and becomes the chat's current quote for checkout.
"""
from __future__ import annotations

import queue
import threading
import time
import uuid
from contextvars import copy_context
from typing import Any, Iterator

from app.services import insurance_service as svc
from app.services import products, systems
from app.services.progress import use_sink
from app.services.session_store import session_store
from app.services.tool_events import tool_call_event, tool_result_event

_DONE = object()
ALLOWED = {"insured_value", "deductible", "copay", "maternity", "sum_assured", "term_years", "monthly_contribution",
           "retirement_age", "income_years", "fund", "frequency", "ci_rider", "building_value", "contents_value"}


def _now() -> int:
    return int(time.time() * 1000)


def _describe(q: dict[str, Any], changes: dict[str, Any]) -> str:
    labels = {a["key"]: a for a in q.get("adjustables", [])}
    parts = []
    for k, v in changes.items():
        a = labels.get(k, {"label": k.replace("_", " ")})
        if a.get("type") == "toggle":
            val = "on" if v else "off"
        elif a.get("options"):
            val = next((o["label"] for o in a["options"] if str(o["value"]) == str(v)), str(v))
        elif a.get("unit") == "SAR":
            val = f"SAR {float(v):,.0f}"
        else:
            val = f"{v} {a.get('unit', '')}".strip()
        parts.append(f"{a['label'].lower()} → {val}")
    return ", ".join(parts)


def reprice_stream(quote_id: str, changes: dict[str, Any], session_id: str | None) -> Iterator[dict[str, Any]]:
    run_id, call_id, started = uuid.uuid4().hex[:10], f"rp-{uuid.uuid4().hex[:8]}", _now()
    row = svc.get_quote(quote_id)
    old = row["details"]
    clean = {k: v for k, v in (changes or {}).items() if k in ALLOWED}
    what = _describe(old, clean) or "no change"
    ident = session_store.get(session_id) if session_id else None
    yield {"type": "run_started", "run_id": run_id, "session_id": session_id, "mode": "engine", "model": systems.RATING,
           "identity": ident.public() if ident else None, "ts": started, "message": f"Adjusted {what}"}
    yield {"type": "step", "id": "understand", "kind": "think", "label": "Customer adjusted the quote", "status": "done",
           "detail": what, "ts": _now()}
    args = {"quote_id": row["quote_id"], **clean}
    yield tool_call_event(call_id, "reprice_quote", args)

    q: queue.Queue = queue.Queue()
    result: dict[str, Any] = {}

    def work() -> None:
        try:
            with use_sink(q.put):
                params = {**products.params_of(old), **clean}
                if "fund" in clean or "retirement_age" in clean:
                    params.pop("term_years", None)
                nq = svc.create_product_quote(row["customer_id"], products.line_of(old), params, old.get("coverage"),
                                              sync=False)
                systems.quote_steps(call_id, nq, row["customer_id"], changed=what)
                result["q"] = nq
        except Exception as e:  # noqa: BLE001
            result["err"] = str(e)
        finally:
            q.put(_DONE)

    threading.Thread(target=copy_context().run, args=(work,), daemon=True).start()
    while (ev := q.get()) is not _DONE:
        yield ev

    import json  # noqa: PLC0415

    if "err" in result:
        raw = json.dumps({"ok": False, "error": result["err"]})
        yield tool_result_event(call_id, "reprice_quote", raw)
        yield {"type": "error", "message": result["err"], "run_id": run_id, "ts": _now()}
        return
    nq = result["q"]
    if ident is not None:
        ident.extra["last_quote_id"], ident.extra["last_quote_line"] = nq["quote_id"], nq["line"]
    yield tool_result_event(call_id, "reprice_quote", json.dumps({"ok": True, "data": nq}, default=str))
    yield {"type": "final", "run_id": run_id, "reply": "", "session_id": session_id, "mode": "engine",
           "tools_used": [{"name": "reprice_quote", "args": args, "ok": True}], "cards": [{"type": "quote", "data": nq}],
           "citations": [], "identity": ident.public() if ident else None, "replaces_quote": row["quote_id"],
           "duration_ms": _now() - started, "ts": _now()}
