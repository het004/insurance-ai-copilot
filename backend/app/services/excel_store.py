"""Customer 360 maintained in an Excel workbook (POC store).

data/art_customer_360.xlsx
  ├─ Customers   MASTER — read by the Copilot; rows added on new-customer registration.
  │              Staff can edit it in Excel; changes are picked up automatically (file mtime).
  ├─ Policies    mirrored from the app database after every change (read-only view)
  ├─ Claims      mirrored
  ├─ Quotes      mirrored
  └─ About       what this file is

Windows note: Excel locks a workbook while it's open. If a save fails because the file is open,
the change is kept in memory, `pending_sync` is set, and the next successful write flushes it.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.config import settings

log = logging.getLogger(__name__)

CUSTOMER_COLS = [
    "customer_id", "name", "phone", "email", "address", "city", "date_of_birth", "nationality", "segment", "kyc_status",
    "customer_since", "id_type", "id_reference", "id_hash", "kyc_source", "onboarded_via", "registered_at",
]
HEADER_FILL = PatternFill("solid", fgColor="4F46E5")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _digits(s: Any) -> str:
    return re.sub(r"\D", "", str(s or ""))


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat(timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    return str(v).strip()


class Customer360Workbook:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.EXCEL_PATH
        self._lock = threading.RLock()
        self._customers: list[dict[str, str]] = []
        self._mtime: float | None = None
        self.pending_sync = False
        self.last_error: str | None = None
        self.last_synced_at: str | None = None

    # ------------------------------------------------------------------ lifecycle
    def init(self) -> None:
        with self._lock:
            if not self.path.exists():
                from app.database.seed import CUSTOMERS

                self._customers = [{**{c: "" for c in CUSTOMER_COLS}, **row} for row in CUSTOMERS]
                self._save()
                log.info("Created Customer 360 workbook at %s", self.path)
            self._load()

    def _load(self) -> None:
        wb = load_workbook(self.path, read_only=True, data_only=True)
        try:
            ws = wb["Customers"]
            rows = list(ws.iter_rows(values_only=True))
        finally:
            wb.close()
        if not rows:
            self._customers = []
            return
        header = [_cell(h) for h in rows[0]]
        out = []
        for r in rows[1:]:
            rec = {h: _cell(v) for h, v in zip(header, r) if h}
            if rec.get("customer_id"):
                out.append({c: rec.get(c, "") for c in CUSTOMER_COLS})
        self._customers = out
        self._mtime = self.path.stat().st_mtime

    def _maybe_reload(self) -> None:
        """Pick up edits a human made in Excel (unless we have unsaved changes of our own)."""
        try:
            mtime = self.path.stat().st_mtime
        except FileNotFoundError:
            self.init()
            return
        if self.pending_sync:
            self.sync()
        elif mtime != self._mtime:
            try:
                self._load()
                log.info("Reloaded Customer 360 workbook (edited externally)")
            except Exception as e:  # noqa: BLE001 — partially-saved file, bad edit…
                log.warning("Could not reload workbook, keeping cached copy: %s", e)

    # ------------------------------------------------------------------ writing
    @staticmethod
    def _write_sheet(ws, header: list[str], rows: list[list[Any]]) -> None:
        ws.append(header)
        for r in rows:
            ws.append(r)
        for i, h in enumerate(header, start=1):
            c = ws.cell(row=1, column=i)
            c.fill, c.font = HEADER_FILL, HEADER_FONT
            c.alignment = Alignment(vertical="center")
            width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows if i - 1 < len(r)] + [8])
            ws.column_dimensions[get_column_letter(i)].width = min(width + 2, 60)
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions

    def _mirror_rows(self) -> dict[str, tuple[list[str], list[list[Any]]]]:
        from app.database import db

        out = {}
        with db() as c:
            for sheet, sql in [
                ("Policies", "SELECT policy_id, customer_id, policy_type, product_name, insured_asset, sum_insured, premium, "
                             "start_date, end_date, status, ncb_percent, "
                             "COALESCE(json_extract(details, '$.purchased_via'), 'Branch') AS channel, "
                             "COALESCE(json_extract(details, '$.quote_id'), '') AS quote_id, "
                             "COALESCE(json_extract(details, '$.payment_id'), '') AS payment_id "
                             "FROM policies ORDER BY customer_id, end_date"),
                ("Claims", "SELECT claim_id, customer_id, policy_id, incident_date, incident_type, location, "
                           "estimated_amount, status, remarks, created_at, updated_at FROM claims ORDER BY created_at DESC"),
                ("Quotes", "SELECT quote_id, customer_id, product, premium, coverage, risk_score, created_at, "
                           "COALESCE(json_extract(details, '$.purchased_policy_id'), '') AS purchased_policy_id "
                           "FROM quotes ORDER BY created_at DESC"),
                ("Payments", "SELECT payment_id, customer_id, policy_id, quote_id, amount, method, status, reference, "
                             "gateway, created_at FROM payments ORDER BY created_at DESC"),
            ]:
                cur = c.execute(sql)
                out[sheet] = ([d[0] for d in cur.description], [list(r) for r in cur.fetchall()])
        return out

    def _save(self) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "Customers"
        self._write_sheet(ws, CUSTOMER_COLS, [[c.get(k, "") for k in CUSTOMER_COLS] for c in self._customers])
        try:
            for sheet, (header, rows) in self._mirror_rows().items():
                self._write_sheet(wb.create_sheet(sheet), header, rows)
        except Exception as e:  # noqa: BLE001 — DB not ready during first init
            log.debug("Mirror sheets skipped: %s", e)
        about = wb.create_sheet("About")
        for line in [
            ["Insurance AI Copilot — Customer 360 (POC)"],
            ["Customers sheet is the master record. Edit it here and the Copilot picks it up."],
            ["Policies / Claims / Quotes / Payments are mirrored from the app database and overwritten on each change."],
            ["Policies bought in the Copilot chat show channel = 'AI Copilot chat' with their quote and payment ids."],
            ["Payments are SIMULATED gateway transactions — no money moves."],
            ["New customers are appended after confirming KYC fetched from SIMULATED government sources."],
            ["id_reference is masked; id_hash is a one-way hash used to detect duplicate registrations."],
            [f"Last written: {datetime.now().isoformat(timespec='seconds')}"],
        ]:
            about.append(line)
        about["A1"].font = Font(bold=True, size=13)
        about.column_dimensions["A"].width = 100
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"~tmp_{self.path.name}")
        wb.save(tmp)
        os.replace(tmp, self.path)  # atomic; raises PermissionError if Excel has the file open
        self._mtime = self.path.stat().st_mtime

    def sync(self) -> dict[str, Any]:
        """Write the workbook. Never raises — returns status so callers can tell the user."""
        with self._lock:
            try:
                self._save()
                self.pending_sync, self.last_error = False, None
                self.last_synced_at = datetime.now().isoformat(timespec="seconds")
                return {"synced": True, "path": str(self.path)}
            except PermissionError:
                self.pending_sync = True
                self.last_error = "art_customer_360.xlsx is open in Excel — close it and the update will sync automatically."
            except Exception as e:  # noqa: BLE001
                self.pending_sync, self.last_error = True, f"Workbook write failed: {e}"
            log.warning(self.last_error)
            return {"synced": False, "path": str(self.path), "warning": self.last_error}

    # ------------------------------------------------------------------ reads
    def customers(self) -> list[dict[str, str]]:
        with self._lock:
            self._maybe_reload()
            return [dict(c) for c in self._customers]

    def get(self, customer_id: str) -> dict[str, str] | None:
        cid = (customer_id or "").strip().upper()
        return next((c for c in self.customers() if c["customer_id"].upper() == cid), None)

    def find(self, identifier: str) -> dict[str, str] | None:
        """Match by customer id, email or Saudi mobile (last 9 digits: 5XXXXXXXX)."""
        ident = (identifier or "").strip()
        if not ident:
            return None
        if c := self.get(ident):
            return c
        custs = self.customers()
        if "@" in ident:
            return next((c for c in custs if c["email"].lower() == ident.lower()), None)
        d = _digits(ident)[-9:]
        if len(d) == 9:
            return next((c for c in custs if _digits(c["phone"])[-9:] == d), None)
        return None

    def find_by_id_hash(self, id_hash: str) -> dict[str, str] | None:
        return next((c for c in self.customers() if id_hash and c.get("id_hash") == id_hash), None)

    def next_id(self) -> str:
        nums = [int(m.group(1)) for c in self.customers() if (m := re.match(r"CUST-(\d+)", c["customer_id"]))]
        return f"CUST-{max(nums or [1000]) + 1}"

    # ------------------------------------------------------------------ writes
    def add_customer(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._maybe_reload()
            row = {c: _cell(record.get(c, "")) for c in CUSTOMER_COLS}
            self._customers.append(row)
            status = self.sync()
            return {"customer": dict(row), **status}

    def status(self) -> dict[str, Any]:
        return {"path": str(self.path), "exists": self.path.exists(), "pending_sync": self.pending_sync,
                "last_error": self.last_error, "last_synced_at": self.last_synced_at,
                "customers": len(self._customers)}


excel_store = Customer360Workbook()
