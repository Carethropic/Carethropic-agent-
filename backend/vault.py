"""Carethropic record: one care record per person (meds, events, coverage, emergency), check-ins, consent."""
from __future__ import annotations

import copy
import threading
from datetime import datetime, timedelta, date

from common import load, today, now, AUDIT, mask
from store import STORE

GRACE = timedelta(hours=2)
_lock = threading.Lock()
_people: dict[str, dict] = {}
ORG: dict = {}


def _resolve(p: dict, base: date) -> dict:
    p = copy.deepcopy(p)
    for m in p["medications"]:
        m["refill_date"] = (base + timedelta(days=m.pop("refill_offset", 30))).isoformat()
    for e in p["events"]:
        if "offset" in e:
            e["date"] = (base + timedelta(days=e.pop("offset"))).isoformat()
    for c in p["checkins"]:
        if "offset" in c:
            c["date"] = (base + timedelta(days=c.pop("offset"))).isoformat()
    p["consent"] = None
    return p


def reset() -> None:
    """Wipe the records and reseed them from data/people.json, dated relative to today."""
    seed = load("people.json")
    base = today()
    with _lock:
        ORG.clear()
        ORG.update(seed["organization"])
        _people.clear()
        for p in seed["people"]:
            _people[p["id"]] = _resolve(p, base)
        STORE.replace_people(_people)
        STORE.set_meta("seeded_on", base.isoformat())
    AUDIT.add("records_reseeded", {"people": len(_people), "seeded_on": base.isoformat()})


def init() -> None:
    """On startup: keep what the store already holds; seed only when it is empty."""
    saved = STORE.load_people()
    if not saved:
        reset()
        return
    with _lock:
        ORG.clear()
        ORG.update(load("people.json")["organization"])
        _people.clear()
        _people.update(saved)


def seeded_on() -> str | None:
    return STORE.get_meta("seeded_on")


def get(pid: str) -> dict | None:
    return _people.get(pid)


def all_people() -> list[dict]:
    return list(_people.values())


def item_index(p: dict) -> dict[str, dict]:
    """Every citable record item by ID."""
    idx = {m["id"]: {"kind": "medication", **m} for m in p["medications"]}
    idx.update({e["id"]: {"kind": e["type"], **e} for e in p["events"]})
    idx.update({c["id"]: {"kind": "coverage", **c} for c in p["coverage"]})
    idx[p["emergency"]["id"]] = {"kind": "emergency", **p["emergency"]}
    return idx


def add_event(pid: str, event: dict) -> dict:
    p = _people[pid]
    with _lock:
        existing = next((e for e in p["events"] if e.get("dedupe_key") and e.get("dedupe_key") == event.get("dedupe_key")), None)
        if existing:
            existing.update(event)
            STORE.save_person(p)
            return existing
        event.setdefault("id", f"evt-{pid}-{len(p['events']) + 1}")
        p["events"].append(event)
        STORE.save_person(p)
    AUDIT.add("record_event_saved", {"pid": pid, "event": event["id"]})
    return event


def checkin(pid: str, kind: str, item_id: str | None = None) -> dict:
    p = _people[pid]
    if kind == "med" and item_id not in {m["id"] for m in p["medications"]}:
        raise ValueError("Unknown medication for this person.")
    t = now()
    entry = {"type": kind, "item_id": item_id, "date": t.date().isoformat(), "time": t.strftime("%H:%M")}
    with _lock:
        p["checkins"].append(entry)
        STORE.save_person(p)
    AUDIT.add("checkin", {"pid": pid, "type": kind, "item": item_id})
    return entry


def confirmations_today(p: dict, item_id: str, on: date) -> list[dict]:
    return sorted([c for c in p["checkins"] if c["type"] == "med" and c.get("item_id") == item_id and c["date"] == on.isoformat()],
                  key=lambda c: c["time"])


def status(p: dict, at: datetime | None = None) -> dict:
    at = at or now()
    d = at.date()
    if not p.get("lives_alone"):
        return {"level": "none", "items": [], "last_daily": None}
    dailies = sorted(c["date"] for c in p["checkins"] if c["type"] == "daily")
    last_daily = dailies[-1] if dailies else None
    items, level = [], "ok"
    rank = {"ok": 0, "late": 1, "missed": 2, "missed_2_days": 3}

    def bump(lv):
        nonlocal level
        if rank[lv] > rank[level]:
            level = lv

    if last_daily is None or (d - date.fromisoformat(last_daily)).days >= 2:
        bump("missed_2_days")
        items.append({"kind": "daily", "state": "missed_2_days", "last": last_daily})
    elif last_daily != d.isoformat() and at.hour >= 12:
        bump("late")
        items.append({"kind": "daily", "state": "late"})

    for m in p["medications"]:
        confirmed = confirmations_today(p, m["id"], d)
        for i, t in enumerate(sorted(m["times"])):
            hh, mm = map(int, t.split(":"))
            due = at.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if due > at:
                continue
            if i < len(confirmed):
                items.append({"kind": "med", "item_id": m["id"], "name": m["name"], "due": t, "state": "taken", "at": confirmed[i]["time"]})
                continue
            st = "missed" if at - due > GRACE else "late"
            bump(st)
            items.append({"kind": "med", "item_id": m["id"], "name": m["name"], "due": t, "state": st})
    return {"level": level, "items": items, "last_daily": last_daily}


def set_consent(pid: str, granted: bool, given_by: str, recorded_by: str) -> dict | None:
    p = _people[pid]
    c = {"scope": "emergency_card", "given_by": given_by, "recorded_by": recorded_by,
         "at": now().isoformat(timespec="seconds")} if granted else None
    with _lock:
        p["consent"] = c
        STORE.save_person(p)
    AUDIT.add("consent_granted" if granted else "consent_revoked", {"pid": pid, "by": given_by, "recorder": recorded_by})
    return c


def public_view(p: dict) -> dict:
    """Record as sent to the UI: member IDs masked."""
    v = copy.deepcopy(p)
    for c in v["coverage"]:
        c["member_id"] = mask(c["member_id"])
    v["status"] = status(p)
    v["events"] = sorted(v["events"], key=lambda e: (e["date"], e.get("time", "")))
    return v


init()
