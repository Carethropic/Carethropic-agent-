"""Kalinga API server. Run: uvicorn app:app --reload --port 8000 (from backend/)."""
from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agents
import pipeline
import samples
from governance import audit, case_trail, verify_chain
from rules import compute

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Kalinga", version="1.0")
app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
app.mount("/samples", StaticFiles(directory=ROOT / "samples"), name="samples")


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/api/status")
def status():
    return {"live": agents.live_available(), "model": agents.MODEL, "kb_version": pipeline.KB["version"]}


@app.get("/api/samples")
def list_samples():
    out = []
    for sid, s in samples.SAMPLES.items():
        rr = compute(s["facts"], s["client"], date.fromisoformat(s["as_of"]))
        nxt = min(rr.deadlines, key=lambda d: d.days_left) if rr.deadlines else None
        out.append({
            "id": sid, "title": s["title"], "client": s["client"], "as_of": s["as_of"],
            "simulated": s.get("simulated", False), "image": "/" + s["image"],
            "triage": rr.triage_score, "review_status": rr.review_status,
            "next_deadline": nxt.__dict__ if nxt else None,
        })
    return sorted(out, key=lambda x: -x["triage"])


@app.post("/api/analyze")
async def analyze(
    sample_id: str = Form(""),
    client_json: str = Form("{}"),
    text: str = Form(""),
    force_replay: bool = Form(False),
    file: UploadFile | None = File(None),
):
    client = json.loads(client_json or "{}")
    case = {"case_id": f"case-{uuid.uuid4().hex[:8]}", "client": client, "text": text, "force_replay": force_replay}
    if sample_id and sample_id in samples.SAMPLES:
        s = samples.SAMPLES[sample_id]
        case.update(sample_id=sample_id, as_of=s["as_of"], client=client or s["client"])
        img = ROOT / s["image"]
        if img.exists():
            case.update(file_bytes=img.read_bytes(), media_type="image/png")
    if file is not None:
        case.update(file_bytes=await file.read(), media_type=file.content_type or "image/png")

    async def stream():
        try:
            async for event in pipeline.run(case):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:  # surface failures to the UI rather than hanging
            audit(case["case_id"], "error", "system", meta={"error": type(exc).__name__})
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


class Approval(BaseModel):
    case_id: str
    navigator: str
    letter: str
    edits_made: bool


@app.post("/api/approve")
def approve(a: Approval):
    entry = audit(a.case_id, "navigator_approved", f"navigator:{a.navigator}", payload_out=a.letter, meta={"edits_made": a.edits_made})
    return {"ok": True, "entry_hash": entry["entry_hash"]}


@app.get("/api/audit/{case_id}")
def get_trail(case_id: str):
    return {"trail": case_trail(case_id), "chain": verify_chain()}
