"""Who is chatting in each session — the backend, not the browser, decides this.

A chat session starts as a GUEST. It becomes VERIFIED when either
  • identify_customer() matches a registered customer in Customer 360, or
  • a new customer confirms their government-fetched KYC and is registered.
All personal-data tools read the customer id from here (never from the model or the client).
"""
from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SessionIdentity:
    customer_id: str | None = None
    customer_name: str | None = None
    verified_via: str | None = None      # e.g. "registered mobile", "policy number", "new registration (National ID + Nafath)"
    verified_at: str | None = None
    kyc_draft: dict[str, Any] | None = None  # fetched but not yet confirmed new-customer record
    is_new_customer: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "verified" if self.customer_id else ("kyc_pending" if self.kyc_draft else "guest")

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("kyc_draft", None)
        d.pop("extra", None)
        d["status"] = self.status
        return d


class SessionStore:
    def __init__(self) -> None:
        self._s: dict[str, SessionIdentity] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str | None) -> SessionIdentity:
        with self._lock:
            return self._s.setdefault(session_id or "_anon", SessionIdentity())

    def bind(self, session_id: str, customer_id: str, name: str, via: str, new: bool = False) -> SessionIdentity:
        s = self.get(session_id)
        s.customer_id, s.customer_name, s.verified_via = customer_id, name, via
        s.verified_at = datetime.now().isoformat(timespec="seconds")
        s.is_new_customer, s.kyc_draft = new, None
        return s

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._s.pop(session_id, None)

    def active(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"session_id": k, **v.public()} for k, v in self._s.items() if v.customer_id]


session_store = SessionStore()
