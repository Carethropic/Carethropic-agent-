"""Shared helpers: clock, data loading, privacy scrubbing, audit hash chain."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).parent / "data"

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Los_Angeles")
except Exception:  # pragma: no cover
    TZ = timezone(timedelta(hours=-8))


def env(name: str, default: str | None = None) -> str | None:
    """Read CARETHROPIC_<name>; fall back to the legacy KALINGA_<name> so old .env files keep working."""
    return os.environ.get(f"CARETHROPIC_{name}", os.environ.get(f"KALINGA_{name}", default))


def now() -> datetime:
    """Server clock in Pacific time. CARETHROPIC_NOW=YYYY-MM-DDTHH:MM pins it for tests and rehearsals."""
    pinned = env("NOW")
    if pinned:
        return datetime.fromisoformat(pinned).replace(tzinfo=TZ)
    return datetime.now(TZ)


def today() -> date:
    return now().date()


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ---------- privacy ----------
SSN = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
PHONE = re.compile(r"\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")


def scrub(text: str) -> str:
    """Remove SSNs, phone numbers, and emails before text reaches the model."""
    text = SSN.sub("[SSN removed]", text)
    text = EMAIL.sub("[email removed]", text)
    return PHONE.sub("[phone removed]", text)


def mask(identifier: str | None, keep: int = 3) -> str:
    if not identifier:
        return ""
    return "•" * max(len(identifier) - keep, 0) + identifier[-keep:]


# ---------- audit ----------
class AuditChain:
    """Tamper-evident log. Stores only hashes of payloads, never client data."""

    def __init__(self):
        self._lock = threading.Lock()
        self.entries: list[dict] = []
        self._store = None

    def attach(self, store) -> None:
        """Persist the chain through `store` (see store.py). Loads what the store already holds."""
        with self._lock:
            self._store = store
            self.entries = store.load_audit()

    @staticmethod
    def _h(s: str) -> str:
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def add(self, kind: str, payload) -> dict:
        with self._lock:
            prev = self.entries[-1]["hash"] if self.entries else "0" * 64
            payload_hash = self._h(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str))
            ts = now().isoformat(timespec="seconds")
            h = self._h(prev + kind + payload_hash + ts)
            entry = {"i": len(self.entries), "ts": ts, "kind": kind, "payload_hash": payload_hash, "prev": prev, "hash": h}
            self.entries.append(entry)
            if self._store is not None:
                self._store.append_audit(entry)
            return entry

    def verify(self) -> bool:
        prev = "0" * 64
        for e in self.entries:
            if e["prev"] != prev or self._h(prev + e["kind"] + e["payload_hash"] + e["ts"]) != e["hash"]:
                return False
            prev = e["hash"]
        return True


AUDIT = AuditChain()
