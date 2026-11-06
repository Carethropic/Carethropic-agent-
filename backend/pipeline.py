"""Kalinga orchestration: extract -> compute -> (rights || health) -> verify -> draft -> human gate."""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime

import agents
import samples
from governance import audit, mask_id, mask_pii
from rules import AUTH_BY_ID, KB, compute


def fmt_long(iso: str) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y")


def fill(text: str, deadlines: list[dict]) -> str:
    for d in deadlines:
        text = text.replace("{D:" + d["rule"] + "}", fmt_long(d["act_by"]))
    return text


def ev(kind: str, **kw) -> dict:
    return {"type": kind, **kw}


async def run(case: dict):
    """Async generator of streaming events. Final event has type 'result'."""
    case_id = case["case_id"]
    client = case.get("client") or {}
    language = client.get("preferred_language") or "English"
    today = date.fromisoformat(case["as_of"]) if case.get("as_of") else date.today()
    fixture = samples.SAMPLES.get(case.get("sample_id") or "")
    live = agents.live_available() and not case.get("force_replay")
    mode = "live" if live else "replay"
    if not live and not fixture:
        yield ev("error", message="Live analysis needs an ANTHROPIC_API_KEY. Sample cases run in replay mode without one.")
        return

    audit(case_id, "case_opened", "navigator", meta={"mode": mode, "as_of": today.isoformat()})

    # 1. Extraction (vision)
    yield ev("step", agent="Reader", status="running", detail="Reading the notice with Claude vision")
    if live:
        facts = await agents.extract_notice(case.get("file_bytes"), case.get("media_type"), mask_pii(case.get("text") or ""))
    else:
        await asyncio.sleep(0.9)
        facts = json.loads(json.dumps(fixture["facts"]))
    facts["case_number"] = mask_id(facts.get("case_number"))
    audit(case_id, "extract", f"claude:{agents.MODEL}" if live else "replay", payload_out=facts)
    yield ev("step", agent="Reader", status="done", detail=f"{facts.get('program')} · {facts.get('notice_type','').replace('_',' ')}", data=facts)

    # 2. Deterministic rules
    yield ev("step", agent="Rules Engine", status="running", detail="Computing deadlines, notice defects, and exemptions in code")
    rr = compute(facts, client, today).to_dict()
    audit(case_id, "rules", "deterministic", payload_in=facts, payload_out=rr)
    await asyncio.sleep(0.3)
    yield ev("step", agent="Rules Engine", status="done",
             detail=f"{len(rr['deadlines'])} deadlines, {len(rr['flags'])} flags, {len(rr['exemptions'])} exemptions", data=rr)

    allowed = rr["authority_ids"]
    rules_for_llm = {"deadlines": rr["deadlines"], "flags": rr["flags"], "exemptions": rr["exemptions"]}

    # 3. Parallel specialists
    yield ev("step", agent="Rights Agent", status="running", detail="Mapping legal options to cited authority")
    yield ev("step", agent="Health Navigator", status="running", detail="Checking care continuity for women and families")
    if live:
        rights, health = await asyncio.gather(
            agents.rights_agent(facts, client, rules_for_llm, allowed),
            agents.health_agent(facts, client, rules_for_llm, allowed),
        )
    else:
        await asyncio.sleep(1.2)
        rights = {"claims": [dict(c, text=fill(c["text"], rr["deadlines"])) for c in fixture["rights"]]}
        health = {"claims": [dict(c, text=fill(c["text"], rr["deadlines"])) for c in fixture["health"]]}
    for c in rights["claims"]:
        c["agent"] = "rights"
    for c in health["claims"]:
        c["agent"] = "health"
    audit(case_id, "rights_agent", mode, payload_out=rights)
    audit(case_id, "health_agent", mode, payload_out=health)
    yield ev("step", agent="Rights Agent", status="done", detail=f"{len(rights['claims'])} claims")
    yield ev("step", agent="Health Navigator", status="done", detail=f"{len(health['claims'])} claims")

    # 4. Verification: hard checks in code, then Claude as a skeptical reviewer
    yield ev("step", agent="Verifier", status="running", detail="Checking every claim against its citation")
    claims = rights["claims"] + health["claims"]
    known = {d["due"] for d in rr["deadlines"]} | {d["act_by"] for d in rr["deadlines"]}
    known |= {v for v in (facts.get("notice_date"), facts.get("effective_date"), facts.get("response_due_date")) if v}
    claims = agents.deterministic_check(claims, set(allowed), known)
    if live:
        verdicts = (await agents.verifier_agent(claims))["verdicts"]
    else:
        await asyncio.sleep(0.8)
        verdicts = [{"index": i, "verdict": "supported", "reason": "Claim matches the cited authority summary."} for i in range(len(claims))]
    vmap = {v["index"]: v for v in verdicts}
    kept, dropped = [], []
    for i, c in enumerate(claims):
        v = vmap.get(i, {"verdict": "unsupported", "reason": "No verdict returned."})
        c["verdict"], c["verdict_reason"] = v["verdict"], v["reason"]
        (kept if c["hard_check"] == "pass" and v["verdict"] != "unsupported" else dropped).append(c)
    audit(case_id, "verify", mode, payload_in=claims, payload_out={"kept": len(kept), "dropped": len(dropped)})
    yield ev("step", agent="Verifier", status="done", detail=f"{len(kept)} verified, {len(dropped)} removed")

    # 5. Drafting
    yield ev("step", agent="Drafter", status="running", detail=f"Writing client explanation in {language} and a response letter")
    if live:
        drafts = await agents.drafter_agent(facts, client, rules_for_llm, kept, language)
    else:
        await asyncio.sleep(1.0)
        drafts = {k: (fill(v, rr["deadlines"]) if isinstance(v, str) else v) for k, v in fixture["drafts"].items()}
    audit(case_id, "draft", mode, payload_out=drafts)
    yield ev("step", agent="Drafter", status="done", detail="Drafts ready for navigator review")

    # 6. Human gate
    status = rr["review_status"]
    yield ev("step", agent="Human Review Gate", status="done",
             detail="Escalate to a benefits attorney or senior navigator" if status == "needs_human_expert" else "Ready for navigator approval")
    audit(case_id, "gate", "deterministic", meta={"status": status})

    resources = [r for r in KB["resources"] if set(r["tags"]) & set(_resource_tags(facts, client, rr))]
    result = {
        "case_id": case_id, "mode": mode, "model": agents.MODEL if live else "recorded run", "as_of": today.isoformat(),
        "facts": facts, "client": client, "rules": rr,
        "claims": kept, "dropped_claims": dropped, "drafts": drafts,
        "authorities": [AUTH_BY_ID[i] for i in allowed], "resources": resources,
        "disclaimer": KB["disclaimer"],
    }
    yield ev("result", data=result)


def _resource_tags(facts, client, rr):
    tags = {"hearing", "legal_aid"}
    if client.get("pregnant") or client.get("pregnancy_end_date"):
        tags |= {"pregnancy", "postpartum", "mental_health", "emergency"}
    if rr["review_status"] == "needs_human_expert":
        tags.add("legal_aid")
    tags.add("continuity")
    return tags
