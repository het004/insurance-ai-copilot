"""Ingestion pipeline: load → clean → chunk (heading-aware) → id/metadata."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

MAX_CHARS = 1100
OVERLAP = 150


@dataclass
class Chunk:
    id: str
    source: str           # file name
    title: str            # document title
    section: str          # nearest heading
    content: str
    metadata: dict = field(default_factory=dict)


def load_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    paras = re.split(r"\n\s*\n", text)
    out, buf = [], ""
    for p in paras:
        if len(buf) + len(p) > MAX_CHARS and buf:
            out.append(buf.strip())
            buf = buf[-OVERLAP:] + "\n\n"
        while len(p) > MAX_CHARS:  # very long paragraph (e.g. PDF)
            out.append((buf + p[:MAX_CHARS]).strip())
            p, buf = p[MAX_CHARS - OVERLAP:], ""
        buf += p + "\n\n"
    if buf.strip():
        out.append(buf.strip())
    return out


def _brand(text: str) -> str:
    from app.config import settings

    return text.replace("{{INSURER}}", settings.INSURER_NAME).replace("{{SHORT}}", settings.INSURER_SHORT)


def chunk_document(path: Path) -> list[Chunk]:
    text = _brand(load_text(path)).replace("\r\n", "\n").strip()
    if not text:
        return []
    m = re.search(r"^#\s+(.+)$", text, re.M)
    title = m.group(1).strip() if m else path.stem.replace("_", " ").title()
    sections: list[tuple[str, str]] = []
    current, buf = "Overview", []
    for line in text.split("\n"):
        h = re.match(r"^#{2,3}\s+(.+)$", line)
        if h:
            if "\n".join(buf).strip():
                sections.append((current, "\n".join(buf).strip()))
            current, buf = h.group(1).strip(), []
        elif not re.match(r"^#\s+", line):
            buf.append(line)
    if "\n".join(buf).strip():
        sections.append((current, "\n".join(buf).strip()))

    chunks = []
    for s_idx, (section, body) in enumerate(sections):
        for p_idx, piece in enumerate(_split_long(body)):
            content = f"{title} — {section}\n{piece}"
            h = hashlib.sha1(content.encode()).hexdigest()[:10]
            chunks.append(Chunk(id=f"{path.name}::{s_idx}.{p_idx}::{h}", source=path.name, title=title,
                                section=section, content=content,
                                metadata={"source": path.name, "title": title, "section": section}))
    return chunks
