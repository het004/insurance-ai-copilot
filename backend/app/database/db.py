"""SQLite access layer: schema, connection helper, row mappers."""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import settings

log = logging.getLogger(__name__)

SCHEMA = """
-- Customers live in the Customer 360 Excel workbook (services/excel_store.py).

CREATE TABLE IF NOT EXISTS policies (
    policy_id       TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    policy_type     TEXT NOT NULL,   -- Motor - Car / Motor - Two Wheeler / Health / Home
    product_name    TEXT,
    insured_asset   TEXT,            -- e.g. "Hyundai Creta 2023 · MH12 AB 4521"
    sum_insured     REAL,            -- IDV for motor, cover for health/home
    premium         REAL NOT NULL,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    status          TEXT NOT NULL,   -- Active / Expiring / Lapsed / Renewed
    ncb_percent     INTEGER DEFAULT 0,
    details         TEXT             -- JSON: add-ons, deductibles, members...
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id         TEXT PRIMARY KEY,
    customer_id      TEXT NOT NULL,
    policy_id        TEXT REFERENCES policies(policy_id),
    incident_date    TEXT NOT NULL,
    incident_type    TEXT,
    description      TEXT,
    location         TEXT,
    estimated_amount REAL,
    status           TEXT NOT NULL,  -- Reported / Under Review / Assessment / Approved / Closed
    remarks          TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id    TEXT NOT NULL REFERENCES claims(claim_id),
    status      TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quotes (
    quote_id     TEXT PRIMARY KEY,
    customer_id  TEXT NOT NULL,
    product      TEXT,
    premium      REAL NOT NULL,
    coverage     TEXT NOT NULL,
    risk_score   INTEGER,
    details      TEXT,               -- JSON: full quotation payload
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    customer_id TEXT,
    role        TEXT NOT NULL,       -- user / assistant
    content     TEXT NOT NULL,
    tools       TEXT,                -- JSON list of tool names used
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_policies_customer ON policies(customer_id);
CREATE INDEX IF NOT EXISTS idx_claims_customer   ON claims(customer_id);
CREATE INDEX IF NOT EXISTS idx_quotes_customer   ON quotes(customer_id);
CREATE INDEX IF NOT EXISTS idx_events_claim      ON claim_events(claim_id);

-- Simulated payment-gateway transactions for policy purchases
CREATE TABLE IF NOT EXISTS payments (
    payment_id   TEXT PRIMARY KEY,
    customer_id  TEXT NOT NULL,
    policy_id    TEXT,
    quote_id     TEXT,
    amount       REAL NOT NULL,
    method       TEXT NOT NULL,      -- mada / Apple Pay / STC Pay / Credit card / SADAD
    status       TEXT NOT NULL,      -- Captured / Failed
    reference    TEXT,               -- gateway / bank reference
    gateway      TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


JSON_FIELDS = {"details", "tools"}


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for k in JSON_FIELDS & d.keys():
        if isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


def rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def init_db() -> None:
    from app.database.seed import seed

    with db() as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
        if count == 0:
            seed(conn)
            log.info("Seeded SQLite demo data at %s", settings.SQLITE_PATH)
