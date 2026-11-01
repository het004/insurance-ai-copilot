"""Knowledge base: ChromaDB vector store with Google embeddings.

Retrieval pipeline: query → embed (Gemini) → Chroma cosine kNN → citations.
Offline fallback (no API key / embedding failure): BM25-style keyword ranking
over the same chunks so the Knowledge page still works in a demo without a key.
"""
from __future__ import annotations

import logging
import math
import re
import shutil
import threading
from collections import Counter
from pathlib import Path
from typing import Any

from app.config import settings
from app.rag.ingest import Chunk, chunk_document

log = logging.getLogger(__name__)

COLLECTION = "insurance_knowledge"
SUPPORTED = {".md", ".txt", ".pdf"}
STOP = set("""a an the and or of to in on for is are was were be been with by at as it its this that these those
from what which who whom how when where why do does did can could should would will my your our their i you we
they me us them if not no yes any all about into than then there here have has had get got also just""".split())


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2 and t not in STOP]


class KnowledgeBase:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.collection = None
        self.mode = "keyword"
        self._lock = threading.Lock()
        self._df: Counter = Counter()
        self._tf: list[Counter] = []

    # ------------------------------------------------------------ ingestion
    def _files(self) -> list[Path]:
        files = [p for p in sorted(settings.DOCS_DIR.glob("*")) if p.suffix.lower() in SUPPORTED]
        files += [p for p in sorted(settings.UPLOAD_DIR.glob("*")) if p.suffix.lower() in SUPPORTED]
        return files

    def _build_keyword_index(self) -> None:
        self._tf = [Counter(_tokens(c.content)) for c in self.chunks]
        self._df = Counter()
        for tf in self._tf:
            self._df.update(tf.keys())

    def _sync_chroma(self) -> None:
        import chromadb

        from app.services import gemini_service

        client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
        col = client.get_or_create_collection(COLLECTION, embedding_function=None,
                                              metadata={"hnsw:space": "cosine"})
        existing = set(col.get(include=[])["ids"])
        wanted = {c.id: c for c in self.chunks}
        stale = list(existing - wanted.keys())
        if stale:
            col.delete(ids=stale)
        missing = [c for cid, c in wanted.items() if cid not in existing]
        for i in range(0, len(missing), 50):
            batch = missing[i:i + 50]
            vectors = gemini_service.embed_documents([c.content for c in batch])
            col.add(ids=[c.id for c in batch], embeddings=vectors,
                    documents=[c.content for c in batch], metadatas=[c.metadata for c in batch])
        log.info("Chroma synced: %d chunks (%d embedded now, %d removed)", col.count(), len(missing), len(stale))
        self.collection = col
        self.mode = "vector"

    def load(self) -> None:
        with self._lock:
            self.chunks = [c for f in self._files() for c in chunk_document(f)]
            self._build_keyword_index()
            if settings.llm_enabled:
                try:
                    self._sync_chroma()
                except Exception as e:  # noqa: BLE001
                    log.warning("Vector index unavailable, using keyword retrieval: %s", e)
                    self.collection, self.mode = None, "keyword"
            log.info("Knowledge base ready: %d chunks from %d files (%s mode)",
                     len(self.chunks), len(self._files()), self.mode)

    def add_document(self, filename: str, data: bytes) -> dict[str, Any]:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
        if Path(safe).suffix.lower() not in SUPPORTED:
            raise ValueError("Only .md, .txt and .pdf files are supported")
        dest = settings.UPLOAD_DIR / safe
        dest.write_bytes(data)
        n = len(chunk_document(dest))
        if n == 0:
            dest.unlink(missing_ok=True)
            raise ValueError("No readable text found in the document")
        self.load()
        return {"source": safe, "chunks": n}

    def sources(self) -> list[dict[str, Any]]:
        counts = Counter(c.source for c in self.chunks)
        titles = {c.source: c.title for c in self.chunks}
        uploaded = {p.name for p in settings.UPLOAD_DIR.glob("*")}
        return [{"source": s, "title": titles[s], "chunks": n, "uploaded": s in uploaded}
                for s, n in counts.items()]

    def reset_vectors(self) -> None:
        shutil.rmtree(settings.CHROMA_DIR, ignore_errors=True)
        settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self.load()

    # ------------------------------------------------------------ retrieval
    def _keyword_search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        q = _tokens(query)
        n = len(self.chunks) or 1
        scored = []
        for chunk, tf in zip(self.chunks, self._tf):
            length = sum(tf.values()) or 1
            s = 0.0
            for t in q:
                if t in tf:
                    idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
                    s += idf * (tf[t] * 2.2) / (tf[t] + 1.2 * (0.25 + 0.75 * length / 120))
            head = (chunk.title + " " + chunk.section).lower()
            s += 0.6 * sum(1 for t in q if t in head)
            if s > 0:
                scored.append((chunk, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:k]
        mx = top[0][1] if top else 1
        return [(c, round(s / mx, 3)) for c, s in top]

    def search(self, query: str, k: int = 4) -> list[dict[str, Any]]:
        results: list[tuple[Chunk, float]] = []
        if self.collection is not None:
            try:
                from app.services import gemini_service

                res = self.collection.query(query_embeddings=[gemini_service.embed_query(query)], n_results=k)
                by_id = {c.id: c for c in self.chunks}
                for cid, dist in zip(res["ids"][0], res["distances"][0]):
                    if cid in by_id:
                        results.append((by_id[cid], round(1 - dist, 3)))
            except Exception as e:  # noqa: BLE001
                log.warning("Vector search failed, falling back to keyword: %s", e)
        if not results:
            results = self._keyword_search(query, k)
        return [{"ref": i + 1, "source": c.source, "title": c.title, "section": c.section,
                 "content": c.content.split("\n", 1)[-1], "score": s}
                for i, (c, s) in enumerate(results)]


kb = KnowledgeBase()
