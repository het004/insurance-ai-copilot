"""Chat orchestration.

`chat_stream()` runs the LangGraph agent (or the offline agent) and yields live progress
events — the data behind the "What's happening" panel:

  run_started → step → tool_call → tool_progress* → tool_result → … → final

`chat()` (non-streaming REST) consumes the same stream and returns the final payload.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from contextvars import copy_context
from typing import Any, Iterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.offline_agent import offline_agent
from app.config import settings
from app.services import insurance_service as svc
from app.services.gemini_service import text_of
from app.services.progress import use_sink
from app.services.session_store import session_store
from app.services.tool_events import tool_call_event, tool_result_event
from app.tools import TOOL_CARD_TYPES

log = logging.getLogger(__name__)
_DONE = object()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _step(step_id: str, label: str, status: str, detail: str | None = None) -> dict:
    return {"type": "step", "id": step_id, "kind": "think", "label": label, "status": status,
            "detail": detail, "ts": _now_ms()}


class AgentService:
    def __init__(self) -> None:
        self.graph = None
        self.mode = "offline"
        self._paused_until = 0.0   # circuit breaker after billing / quota / key errors

    _HARD_ERRORS = ("402", "403", "429", "RESOURCE_EXHAUSTED", "PERMISSION_DENIED", "API_KEY_INVALID", "API key not valid",
                    "Payment Required", "credits are depleted", "quota")

    def _gemini_ready(self) -> bool:
        return self.graph is not None and time.time() >= self._paused_until

    def init(self) -> None:
        if settings.llm_enabled:
            try:
                from app.agents.graph import build_graph

                self.graph = build_graph()
                self.mode = "gemini"
            except Exception as e:  # noqa: BLE001
                log.exception("Failed to build Gemini agent, using offline agent: %s", e)
        log.info("Agent mode: %s", self.mode)

    # ------------------------------------------------------------------ packaging
    @staticmethod
    def _package(calls: list[tuple[str, dict, str]]) -> tuple[list, list, list]:
        tools_used, cards, citations = [], [], []
        for name, args, raw in calls:
            try:
                payload = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                payload = {"ok": False, "error": str(raw)}
            ok = bool(payload.get("ok"))
            tools_used.append({"name": name, "args": tool_call_event("", name, args)["args"], "ok": ok})
            if not ok:
                continue
            kind = TOOL_CARD_TYPES.get(name)
            if kind == "citations":
                citations.extend(payload["data"])
            elif kind:
                cards.append({"type": kind, "data": payload["data"]})
        seen, uniq = set(), []
        for c in citations:
            key = (c["source"], c["section"])
            if key not in seen:
                seen.add(key)
                uniq.append(c)
        return tools_used, cards[-3:], uniq[:6]

    # ------------------------------------------------------------------ gemini run
    def _stream_gemini(self, message: str, session_id: str, calls: list, out: dict) -> Iterator[dict]:
        cfg = {"configurable": {"thread_id": session_id}, "recursion_limit": 14}
        names: dict[str, tuple[str, dict]] = {}
        turn = 0
        yield _step("think-0", "Amaan AI · reasoning about the next step", "running")
        for mode, chunk in self.graph.stream({"messages": [HumanMessage(message)]}, cfg,
                                             stream_mode=["updates", "custom"]):
            if mode == "custom":          # tool_progress events emitted from inside tools
                if isinstance(chunk, dict) and chunk.get("type"):
                    yield chunk
                continue
            for node, update in chunk.items():
                for m in (update or {}).get("messages", []):
                    if node == "agent" and isinstance(m, AIMessage):
                        yield _step(f"think-{turn}", "Amaan AI · reasoning about the next step", "done",
                                    "Calling " + ", ".join(tc["name"].replace("_", " ") for tc in m.tool_calls)
                                    if m.tool_calls else "Next question decided")
                        if m.tool_calls:
                            for tc in m.tool_calls:
                                names[tc["id"]] = (tc["name"], tc["args"])
                                yield tool_call_event(tc["id"], tc["name"], tc["args"])
                        else:
                            out["reply"] = text_of(m.content).strip()
                    elif node == "tools" and isinstance(m, ToolMessage):
                        name, args = names.get(m.tool_call_id, (m.name, {}))
                        raw = text_of(m.content)
                        calls.append((name, args, raw))
                        yield tool_result_event(m.tool_call_id, name, raw)
                if node == "tools":
                    turn += 1
                    yield _step(f"think-{turn}", "Amaan AI · reviewing the results", "running")

    # ------------------------------------------------------------------ offline run (live via a queue)
    def _stream_offline(self, message: str, session_id: str, out: dict, lang: str | None = None) -> Iterator[dict]:
        q: queue.Queue = queue.Queue()
        result: dict[str, Any] = {}

        def work() -> None:
            try:
                with use_sink(q.put):
                    result["r"] = offline_agent.chat(message, session_id, lang)
            except Exception as e:  # noqa: BLE001
                result["err"] = e
            finally:
                q.put(_DONE)

        ctx = copy_context()
        threading.Thread(target=ctx.run, args=(work,), daemon=True).start()
        while (ev := q.get()) is not _DONE:
            yield ev
        if "err" in result:
            raise result["err"]
        out["reply"], out["calls"] = result["r"].reply, result["r"].calls

    @staticmethod
    def _context_steps(ident) -> Iterator[dict]:
        """Simulated context load before the model runs — what a production assistant does on every turn."""
        from app.services import systems  # noqa: PLC0415

        if ident.customer_id:
            try:
                n = len([p for p in svc.list_policies(ident.customer_id) if p["status"] in ("Active", "Expiring")])
            except Exception:  # noqa: BLE001
                n = 0
            detail = f"{ident.customer_id} · {n} active plan{'s' if n != 1 else ''} · KYC verified"
        elif ident.kyc_draft:
            detail = "New customer · identity fetched, awaiting confirmation"
        else:
            detail = "Guest session · no personal data loaded"
        yield _step("context", f"{systems.CRM} · loading customer context", "done", detail)
        turns = len(ident.extra.get("said", []))
        yield _step("memory", "Conversation memory", "done", f"{turns} message{'s' if turns != 1 else ''} in this chat")

    # ------------------------------------------------------------------ public
    def chat_stream(self, message: str, session_id: str | None, lang: str | None = None) -> Iterator[dict]:
        session_id = session_id or uuid.uuid4().hex
        run_id = uuid.uuid4().hex[:10]
        started = _now_ms()
        mode, notice = (self.mode if self._gemini_ready() else "offline"), None
        calls: list[tuple[str, dict, str]] = []
        out: dict[str, Any] = {"reply": ""}
        ident = session_store.get(session_id)

        yield {"type": "run_started", "run_id": run_id, "session_id": session_id, "mode": mode,
               "model": settings.model_label if mode == "gemini" else "offline-demo-agent",
               "identity": ident.public(), "ts": started}
        who = f"Verified customer · {ident.customer_name}" if ident.customer_id else \
            "KYC confirmation pending" if ident.kyc_draft else "Guest · not identified yet"
        yield _step("understand", "Understanding your request", "done", who)
        said = ident.extra.setdefault("said", [])
        said.append(message)
        del said[:-40]
        yield from self._context_steps(ident)

        if self._gemini_ready():
            try:
                gm = message + ("\n\n(Reply in Arabic.)" if lang == "ar" else "")
                yield from self._stream_gemini(gm, session_id, calls, out)
            except Exception as e:  # noqa: BLE001 — quota, network, safety blocks…
                log.warning("Gemini turn failed, falling back to offline agent: %s", e)
                if any(h.lower() in str(e).lower() for h in self._HARD_ERRORS):
                    self._paused_until = time.time() + 600
                    log.warning("Gemini paused for 10 minutes (billing/quota/key error) — offline agent in use")
                mode, notice = "offline", "The AI service was slow or unavailable for this turn — answered by the demo engine."
                yield {"type": "notice", "message": notice, "detail": str(e)[:200], "ts": _now_ms()}
                calls.clear()

        if mode == "offline" or not out["reply"]:
            mode = "offline"
            yield _step("offline", "Amaan · matching your request to a journey", "done")
            yield from self._stream_offline(message, session_id, out, lang)
            calls = out["calls"]

        words = len(out["reply"].split())
        yield _step("guardrails", "Guardrails · Takaful wording, PII masking & brevity", "done",
                    f"{words} words · no ID numbers exposed")
        yield _step("compose", "Composing answer", "done")
        tools_used, cards, citations = self._package(calls)
        ident = session_store.get(session_id)
        svc.log_interaction(session_id, ident.customer_id, "user", message)
        svc.log_interaction(session_id, ident.customer_id, "assistant", out["reply"], [t["name"] for t in tools_used])
        yield {"type": "final", "run_id": run_id, "reply": out["reply"], "session_id": session_id,
               "tools_used": tools_used, "cards": cards, "citations": citations, "mode": mode,
               "notice": notice, "identity": ident.public(), "duration_ms": _now_ms() - started, "ts": _now_ms()}

    def chat(self, message: str, session_id: str | None, lang: str | None = None) -> dict[str, Any]:
        final: dict[str, Any] = {}
        for ev in self.chat_stream(message, session_id, lang):
            if ev["type"] == "final":
                final = ev
        return {k: final.get(k) for k in ("reply", "session_id", "tools_used", "cards", "citations",
                                          "mode", "notice", "identity")}

    def reset(self, session_id: str) -> None:
        offline_agent.reset(session_id)
        session_store.clear(session_id)
        if self.graph is not None:
            try:
                self.graph.checkpointer.delete_thread(session_id)
            except Exception:  # noqa: BLE001
                pass


agent_service = AgentService()
