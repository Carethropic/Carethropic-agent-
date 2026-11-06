"""Carethropic: FastAPI backend.

Run:  cd backend && uvicorn app:app --port 8000
"""
from __future__ import annotations

import base64
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ask as ask_mod
import briefing
import emergency
import llm
import nonprofits
import pipeline
import vault
from common import AUDIT, load, today, now, scrub

app = FastAPI(title="Carethropic", version="2.0")
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
I18N = load("i18n.json")
INSIGHTS = load("insights.json")


# ---------- meta ----------
@app.get("/api/meta")
def meta():
    return {"name": "Carethropic", "engine": "Kalinga", "mode": "live" if llm.live() else "replay", "model": llm.MODEL,
            "today": today().isoformat(), "now": now().strftime("%H:%M"), "kb_version": pipeline.KB["version"],
            "directory_version": nonprofits.DIR["version"], "organization": vault.ORG,
            "seeded_on": vault.seeded_on(), "db": pipeline.STORE.path,
            "languages": I18N["languages"], "translation_review": I18N["review_status"]}


@app.get("/api/i18n/{lang}")
def i18n(lang: str):
    return I18N["ui"].get(lang, I18N["ui"]["en"])


@app.get("/api/insights")
def insights():
    return INSIGHTS


@app.get("/api/audit")
def audit():
    return {"valid": AUDIT.verify(), "entries": list(reversed(AUDIT.entries))[:50], "count": len(AUDIT.entries)}


@app.post("/api/reset")
def reset():
    vault.reset()
    pipeline.RESULTS.clear()
    pipeline.STORE.clear_results()
    return {"ok": True}


# ---------- console ----------
@app.get("/api/console")
def console():
    rows = []
    cases_by_person = {}
    for c in pipeline.cases():
        cases_by_person.setdefault(c["person_id"], []).append(c)
    for p in vault.all_people():
        st = vault.status(p)
        upcoming = sorted([e for e in p["events"] if e["date"] >= today().isoformat()], key=lambda e: (e["date"], e.get("time", "")))
        flags = []
        next_ev = upcoming[0] if upcoming else None
        if next_ev and next_ev["type"] == "deadline":
            from datetime import date as _d
            days = (_d.fromisoformat(next_ev["date"]) - today()).days
            if days <= 3:
                flags.append({"kind": "act_today", "text": f"Deadline in {days} day(s): {next_ev['title']}"})
            elif days <= 14:
                flags.append({"kind": "upcoming", "text": f"Deadline {next_ev['date']}: {next_ev['title']}"})
        for c in cases_by_person.get(p["id"], []):
            res = pipeline.RESULTS.get(c["id"])
            if res:
                if res["gate"]["urgent"]:
                    flags.insert(0, {"kind": "act_today", "text": "Notice deadline within 3 days"})
                if res["gate"]["route"] == "attorney":
                    flags.append({"kind": "attorney", "text": "Attorney review"})
        if st["level"] in ("missed", "missed_2_days"):
            flags.append({"kind": "missed_checkin", "text": "Two days without a check-in" if st["level"] == "missed_2_days" else "Missed medication check-in"})
        elif st["level"] == "late":
            flags.append({"kind": "late", "text": "Check-in coming due"})
        rows.append({"id": p["id"], "name": p["display_name"], "age": p["age"], "language": p["language"], "city": p["city"],
                     "segment": p["segment"], "lives_alone": p["lives_alone"], "status": st["level"], "flags": flags,
                     "next_event": next_ev, "cases": cases_by_person.get(p["id"], [])})
    order = {"act_today": 0, "attorney": 1, "missed_checkin": 2, "late": 3, "upcoming": 4}
    rows.sort(key=lambda r: min([order[f["kind"]] for f in r["flags"]] or [9]))
    return {"today": today().isoformat(), "rows": rows}


# ---------- notices ----------
@app.get("/api/cases")
def cases():
    return pipeline.cases()


@app.post("/api/cases/{case_id}/run")
def run_case(case_id: str):
    if case_id not in pipeline._CASES:
        raise HTTPException(404, "Unknown case")
    return pipeline.run_case(case_id)


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    """Returns the cached result, or result: null when the case has not run yet."""
    return {"result": pipeline.RESULTS.get(case_id)}


class Approve(BaseModel):
    navigator: str = Field(min_length=1)
    letter: str | None = None


@app.post("/api/cases/{case_id}/approve")
def approve(case_id: str, body: Approve):
    if case_id not in pipeline.RESULTS:
        raise HTTPException(404, "Run the case first")
    return pipeline.approve(case_id, body.navigator, body.letter)


@app.post("/api/cases/{case_id}/save")
def save(case_id: str):
    if case_id not in pipeline.RESULTS:
        raise HTTPException(404, "Run the case first")
    return {"saved": pipeline.save_to_record(case_id)}


@app.post("/api/decode")
async def decode(person_id: str = Form(...), text: str = Form(""), image: UploadFile | None = File(None)):
    if vault.get(person_id) is None:
        raise HTTPException(404, "Unknown person")
    b64 = None
    media = "image/jpeg"
    if image is not None:
        data = await image.read()
        if len(data) > 8_000_000:
            raise HTTPException(413, "Image over 8 MB")
        b64 = base64.b64encode(data).decode()
        media = image.content_type or media
    if not text and not b64:
        raise HTTPException(400, "Paste notice text or upload an image")
    return pipeline.decode_custom(person_id, text, b64, media)


# ---------- record ----------
@app.get("/api/people")
def people():
    return [{"id": p["id"], "name": p["display_name"], "language": p["language"], "segment": p["segment"], "city": p["city"]} for p in vault.all_people()]


@app.get("/api/people/{pid}")
def person(pid: str):
    p = vault.get(pid)
    if p is None:
        raise HTTPException(404, "Unknown person")
    return vault.public_view(p)


class Checkin(BaseModel):
    type: str = Field(pattern="^(daily|med)$")
    item_id: str | None = None
    lang: str | None = None


@app.get("/api/people/{pid}/briefing")
def get_briefing(pid: str, lang: str | None = None):
    """Spoken daily summary composed in code from her record, in her language. Lists the record IDs it used."""
    p = vault.get(pid)
    if p is None:
        raise HTTPException(404, "Unknown person")
    return briefing.compose(p, lang or p["language"])


@app.post("/api/people/{pid}/checkin")
def checkin(pid: str, body: Checkin):
    if vault.get(pid) is None:
        raise HTTPException(404, "Unknown person")
    try:
        entry = vault.checkin(pid, body.type, body.item_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    p = vault.get(pid)
    lang = body.lang or p["language"]
    if body.type == "med":
        med = next(m for m in p["medications"] if m["id"] == body.item_id)
        spoken = briefing.feedback("med", lang, name=med["name"], time=entry["time"])
    else:
        spoken = briefing.feedback("daily", lang)
    return {"entry": entry, "status": vault.status(p), "spoken": spoken, "bcp47": briefing.BCP47.get(lang, "en-US")}


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    lang: str | None = None


@app.post("/api/people/{pid}/ask")
def ask(pid: str, body: Ask):
    if vault.get(pid) is None:
        raise HTTPException(404, "Unknown person")
    return ask_mod.ask(pid, scrub(body.question), body.lang)


class Consent(BaseModel):
    granted: bool
    given_by: str = "self"
    recorded_by: str = Field(min_length=1)


@app.post("/api/people/{pid}/consent")
def consent(pid: str, body: Consent):
    if vault.get(pid) is None:
        raise HTTPException(404, "Unknown person")
    return {"consent": vault.set_consent(pid, body.granted, body.given_by, body.recorded_by)}


@app.get("/api/people/{pid}/emergency-card")
def emergency_card(pid: str):
    try:
        return emergency.card(pid)
    except KeyError:
        raise HTTPException(404, "Unknown person")
    except emergency.ConsentRequired as e:
        raise HTTPException(403, str(e))


# ---------- nonprofit finder ----------
@app.get("/api/nonprofits/search")
def nonprofit_search(q: str = "", limit: int = 12):
    if not q.strip():
        raise HTTPException(400, "Enter a search, for example: Claude nonprofit partners in San Francisco")
    return nonprofits.search(q.strip()[:200], max(1, min(limit, 30)))


# ---------- static ----------
@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
