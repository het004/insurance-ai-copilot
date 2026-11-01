"""Keep the demo's data across Cloud Run restarts by mirroring it to a Cloud Storage bucket.

Cloud Run's disk is temporary, so when STATE_BUCKET is set:
  • on startup, restore() downloads the last snapshot (SQLite DB, Customer 360 workbook, uploaded documents)
  • every SYNC_SECONDS a background thread uploads whatever changed
  • on shutdown, flush() uploads a final snapshot

SQLite is copied with the online-backup API, so the uploaded file is always consistent. The ChromaDB index is not
synced; it is rebuilt from the documents and uploads at startup. Locally (STATE_BUCKET empty) this does nothing.
Run the service with a single instance (max-instances=1): one writer, one copy of the data.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import threading
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)

BUCKET = os.getenv("STATE_BUCKET", "").removeprefix("gs://").strip("/")
PREFIX = os.getenv("STATE_PREFIX", "copilot-state").strip("/")
SYNC_SECONDS = int(os.getenv("STATE_SYNC_SECONDS", "20"))


class StateSync:
    def __init__(self) -> None:
        self.enabled = bool(BUCKET)
        self._bucket = None
        self._seen: dict[str, float] = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ helpers
    def _b(self):
        if self._bucket is None:
            from google.cloud import storage  # noqa: PLC0415 — only needed on GCP

            self._bucket = storage.Client().bucket(BUCKET)
        return self._bucket

    def _files(self) -> dict[str, Path]:
        files = {"art_ksa.db": settings.SQLITE_PATH, "art_customer_360.xlsx": settings.EXCEL_PATH}
        for p in settings.UPLOAD_DIR.glob("*"):
            if p.is_file():
                files[f"uploads/{p.name}"] = p
        return files

    # ------------------------------------------------------------------ restore
    def restore(self) -> None:
        if not self.enabled:
            return
        try:
            n = 0
            for blob in self._b().list_blobs(prefix=f"{PREFIX}/"):
                rel = blob.name[len(PREFIX) + 1:]
                if not rel or rel.endswith("/"):
                    continue
                dest = settings.UPLOAD_DIR / rel.split("/", 1)[1] if rel.startswith("uploads/") else \
                    settings.SQLITE_PATH if rel == "art_ksa.db" else settings.EXCEL_PATH if rel == "art_customer_360.xlsx" else None
                if dest is None:
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                blob.download_to_filename(str(dest))
                self._seen[rel] = dest.stat().st_mtime
                n += 1
            log.info("State restored from gs://%s/%s (%d files)", BUCKET, PREFIX, n)
        except Exception as e:  # noqa: BLE001 — start with fresh demo data rather than fail
            log.warning("Could not restore state from gs://%s/%s: %s", BUCKET, PREFIX, e)

    # ------------------------------------------------------------------ upload
    def flush(self, force: bool = False) -> int:
        if not self.enabled:
            return 0
        uploaded = 0
        with self._lock:
            for rel, path in self._files().items():
                if not path.exists():
                    continue
                mtime = path.stat().st_mtime
                if not force and self._seen.get(rel) == mtime:
                    continue
                try:
                    if rel == "art_ksa.db":  # consistent snapshot of a live SQLite file
                        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                            snap = Path(tmp.name)
                        with sqlite3.connect(path) as src, sqlite3.connect(snap) as dst:
                            src.backup(dst)
                        self._b().blob(f"{PREFIX}/{rel}").upload_from_filename(str(snap))
                        snap.unlink(missing_ok=True)
                    else:
                        self._b().blob(f"{PREFIX}/{rel}").upload_from_filename(str(path))
                    self._seen[rel] = mtime
                    uploaded += 1
                except Exception as e:  # noqa: BLE001
                    log.warning("State sync of %s failed: %s", rel, e)
        if uploaded:
            log.info("State synced to gs://%s/%s (%d files)", BUCKET, PREFIX, uploaded)
        return uploaded

    def start(self) -> None:
        if not self.enabled or self._thread:
            return

        def loop() -> None:
            while not self._stop.wait(SYNC_SECONDS):
                self.flush()

        self._thread = threading.Thread(target=loop, name="state-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop.set()
        self.flush()


state_sync = StateSync()
