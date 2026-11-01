"""Live progress events from inside tools → the "What's happening" panel.

Inside LangGraph (Gemini mode) events go through LangGraph's custom stream writer.
In offline mode the agent service installs a sink (a queue) via `use_sink()`.
Both end up as SSE events of type "tool_progress".
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable

_sink: ContextVar[Callable[[dict], None] | None] = ContextVar("progress_sink", default=None)


@contextmanager
def use_sink(fn: Callable[[dict], None]):
    token = _sink.set(fn)
    try:
        yield
    finally:
        _sink.reset(token)


def emit_event(ev: dict[str, Any]) -> None:
    ev.setdefault("ts", int(time.time() * 1000))
    sink = _sink.get()
    if sink is not None:
        sink(ev)
        return
    try:
        from langgraph.config import get_stream_writer

        get_stream_writer()(ev)
    except Exception:  # noqa: BLE001 — called outside a graph run (REST / tests)
        pass


def progress(tool_call_id: str | None, key: str, label: str, status: str = "running",
             detail: str | None = None) -> None:
    """status: running | done | error"""
    if not tool_call_id:
        return
    emit_event({"type": "tool_progress", "tool_call_id": tool_call_id, "id": f"{tool_call_id}:{key}",
                "label": label, "status": status, "detail": detail})
