"""Governance layer: PII masking and a tamper-evident audit trail.

The audit log stores hashes of inputs and outputs, never raw client data, so
a nonprofit can prove what the system did without keeping sensitive records.
Each entry includes the hash of the previous entry, so any edit breaks the chain.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

AUDIT_PATH = Path(__file__).parent / "audit_log.jsonl"

PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b9\d{2}-\d{2}-\d{4}\b"), "[ITIN]"),
    (re.compile(r"\b[A-Z0-9]{8,14}[A-Z]\b"), "[CASE_OR_CIN]"),
    (re.compile(r"\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
]


def mask_pii(text: str) -> str:
    if not text:
        return text
    for pat, repl in PII_PATTERNS:
        text = pat.sub(repl, text)
    return text


def mask_id(value: str | None) -> str | None:
    if not value:
        return value
    v = str(value)
    return "•" * max(len(v) - 4, 0) + v[-4:]


def _h(obj) -> str:
    raw = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _last_hash() -> str:
    if not AUDIT_PATH.exists():
        return "0" * 64
    lines = AUDIT_PATH.read_text().strip().splitlines()
    return json.loads(lines[-1])["entry_hash"] if lines else "0" * 64


def audit(case_id: str, step: str, actor: str, payload_in=None, payload_out=None, meta=None) -> dict:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "case_id": case_id,
        "step": step,
        "actor": actor,
        "input_sha256": _h(payload_in) if payload_in is not None else None,
        "output_sha256": _h(payload_out) if payload_out is not None else None,
        "meta": meta or {},
        "prev_hash": _last_hash(),
    }
    entry["entry_hash"] = _h(entry)
    with AUDIT_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def verify_chain() -> dict:
    if not AUDIT_PATH.exists():
        return {"ok": True, "entries": 0}
    prev = "0" * 64
    lines = AUDIT_PATH.read_text().strip().splitlines()
    for i, line in enumerate(lines):
        e = json.loads(line)
        claimed = e.pop("entry_hash")
        if e["prev_hash"] != prev or _h(e) != claimed:
            return {"ok": False, "entries": len(lines), "broken_at": i}
        prev = claimed
    return {"ok": True, "entries": len(lines)}


def case_trail(case_id: str) -> list:
    if not AUDIT_PATH.exists():
        return []
    return [json.loads(l) for l in AUDIT_PATH.read_text().strip().splitlines() if json.loads(l)["case_id"] == case_id]
