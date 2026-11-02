"""RAG answerer for the Knowledge page: retrieve → ground → cite."""
from __future__ import annotations

import logging
import re
from typing import Any

from app.config import settings
from app.rag import kb

log = logging.getLogger(__name__)

RAG_SYSTEM = """You are {short}'s Takaful knowledge assistant (Saudi Arabia). Say "contribution", not "premium". Answer ONLY from the numbered context passages.
Cite passages inline like [1] or [2][3] right after the facts they support.
If the context does not contain the answer, say so plainly and suggest contacting support.
Be concise (under 80 words), amounts in SAR."""


def _extractive_answer(question: str, hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "I couldn't find that in the policy documents. Please contact support for help."
    q = set(re.findall(r"[a-z]{4,}", question.lower()))
    lines = []
    for h in hits[:3]:
        sents = re.split(r"(?<=[.!?])\s+", h["content"].replace("\n", " "))
        ranked = sorted(sents, key=lambda s: -len(q & set(re.findall(r"[a-z]{4,}", s.lower()))))
        best = " ".join(s.strip("*- ") for s in ranked[:2] if s.strip())
        if best:
            lines.append(f"- {best} [{h['ref']}]")
    return "Here's what the policy documents say:\n\n" + "\n".join(lines)


def answer(question: str, k: int = 4) -> dict[str, Any]:
    hits = kb.search(question, k=k)
    mode = "offline"
    text = None
    if settings.llm_enabled and hits:
        from app.services import gemini_service

        context = "\n\n".join(f"[{h['ref']}] ({h['title']} — {h['section']})\n{h['content']}" for h in hits)
        try:
            text = gemini_service.generate(f"Context:\n{context}\n\nQuestion: {question}", system=RAG_SYSTEM.format(short=settings.INSURER_SHORT))
            mode = "gemini"
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini RAG generation failed: %s", e)
    if not text:
        text = _extractive_answer(question, hits)
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    for h in hits:
        h["cited"] = h["ref"] in cited
    return {"answer": text, "sources": hits, "mode": mode, "retrieval": kb.mode}
