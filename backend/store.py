"""SQLite persistence for Carethropic.

Records, check-ins, consents, decoded-notice results and the audit chain survive a restart.
The JSON files in data/ stay the seed: `vault.reset()` wipes the tables and reseeds them.

Layout is a small document store: one row per person and per case result, holding the
same JSON the API already serves, plus a flat table for the hash chain. Set
CARETHROPIC_DB to choose the file (default backend/carethropic.db) or ":memory:" for tests.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from common import env, AUDIT

DEFAULT_PATH = Path(__file__).parent / "carethropic.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS people  (id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS results (case_id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit   (i INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL,
                                    payload_hash TEXT NOT NULL, prev TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta    (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _dumps(doc) -> str:
    return json.dumps(doc, ensure_ascii=False, default=str)


class Store:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = str(path)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL") if self.path != ":memory:" else None
        self._db.executescript(SCHEMA)
        self._db.commit()

    # ---------- people ----------
    def load_people(self) -> dict[str, dict]:
        rows = self._db.execute("SELECT id, doc FROM people ORDER BY rowid").fetchall()
        return {pid: json.loads(doc) for pid, doc in rows}

    def save_person(self, p: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO people (id, doc) VALUES (?, ?)", (p["id"], _dumps(p)))
            self._db.commit()

    def replace_people(self, people: dict[str, dict]) -> None:
        with self._lock:
            self._db.execute("DELETE FROM people")
            self._db.executemany("INSERT INTO people (id, doc) VALUES (?, ?)", [(pid, _dumps(p)) for pid, p in people.items()])
            self._db.commit()

    # ---------- case results ----------
    def load_results(self) -> dict[str, dict]:
        rows = self._db.execute("SELECT case_id, doc FROM results").fetchall()
        return {cid: json.loads(doc) for cid, doc in rows}

    def save_result(self, case_id: str, result: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO results (case_id, doc) VALUES (?, ?)", (case_id, _dumps(result)))
            self._db.commit()

    def clear_results(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM results")
            self._db.commit()

    # ---------- audit ----------
    def load_audit(self) -> list[dict]:
        rows = self._db.execute("SELECT i, ts, kind, payload_hash, prev, hash FROM audit ORDER BY i").fetchall()
        return [dict(zip(("i", "ts", "kind", "payload_hash", "prev", "hash"), r)) for r in rows]

    def append_audit(self, e: dict) -> None:
        with self._lock:
            self._db.execute("INSERT INTO audit (i, ts, kind, payload_hash, prev, hash) VALUES (?, ?, ?, ?, ?, ?)",
                             (e["i"], e["ts"], e["kind"], e["payload_hash"], e["prev"], e["hash"]))
            self._db.commit()

    # ---------- meta ----------
    def get_meta(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
            self._db.commit()

    def close(self) -> None:
        self._db.close()


def open_store() -> Store:
    s = Store(env("DB", str(DEFAULT_PATH)))
    AUDIT.attach(s)
    return s


STORE = open_store()
