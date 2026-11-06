"""Carethropic as an MCP connector.

Exposes the same closed-world operations the web app uses, so a navigator can work from
claude.ai (custom connector), Claude Code, or any MCP client. Mounted inside the FastAPI
app at /mcp (Streamable HTTP), so one process and one SQLite store serve both.

Every tool calls the existing modules: nothing here computes a date, cites an authority
or phrases an answer on its own. Tools that change state (check-ins, approvals, consent,
saving deadlines) are marked as such with annotations; everything else is read-only.

Access: set CARETHROPIC_MCP_TOKEN to require `Authorization: Bearer <token>` on /mcp.
Without it, anyone who can reach the server can call the tools, which is fine for a
local demo behind a tunnel you control and not fine for a pilot. Production should put
OAuth in front; see the README.
"""
from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse

import ask as ask_mod
import briefing
import emergency
import nonprofits
import pipeline
import vault
from common import AUDIT, env, scrub, today

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

mcp = MCPServer(
    name="Carethropic",
    version="2.4",
    instructions=(
        "Carethropic helps nonprofit navigators serving Asian American women and elders in the Bay Area. "
        "Deadlines, defects, exemptions, check-in status and nonprofit rankings are computed in code; "
        "every legal claim cites an authority ID from the knowledge base. Never state a deadline that a tool "
        "did not return. Nothing is sent to a county or a client: the navigator approves every letter. "
        "Record IDs (people, medications, events) are the keys; never use display names as keys."
    ),
)


def _person_or_error(pid: str) -> dict | None:
    return vault.get(pid)


# ---------- caseload ----------
@mcp.tool(annotations=READ, description="Navigator console: every person in the caseload with language, city, check-in status, flags (Act today, Attorney review, Missed check-in, Upcoming), next date, and decoded notices.")
def navigator_console() -> dict:
    return pipeline_console()


def pipeline_console() -> dict:
    # Reuse the API's console logic without importing FastAPI routes.
    from app import console  # local import: app imports this module
    return console()


@mcp.tool(annotations=READ, description="List the people in the caseload: id, display name, language code, segment (elder or women), city.")
def list_people() -> dict:
    return {"people": [{"id": p["id"], "name": p["display_name"], "language": p["language"], "segment": p["segment"], "city": p["city"]}
                       for p in vault.all_people()]}


@mcp.tool(annotations=READ, description="One person's Carethropic record: medications, appointments and deadlines, coverage (member IDs masked), emergency information, today's check-in status. Pass the person id from list_people.")
def get_record(person_id: str) -> dict:
    p = _person_or_error(person_id)
    if p is None:
        return {"error": f"Unknown person id '{person_id}'. Call list_people."}
    return vault.public_view(p)


# ---------- notices ----------
@mcp.tool(annotations=READ, description="The recorded demo notices (synthetic): case id, person, headline, and whether the case has been run.")
def list_cases() -> dict:
    return {"cases": pipeline.cases()}


@mcp.tool(annotations=WRITE, description="Run the notice pipeline on a recorded case: extract → rules engine (deadlines, defects, exemptions) → agents → citation verifier → drafts → human gate. Returns deadlines with authority IDs, findings, verified claims, removed claims, the plain-language explanation in her language, a draft letter and a document checklist. Idempotent: re-running replaces the cached result.")
def run_case(case_id: str) -> dict:
    if case_id not in pipeline._CASES:
        return {"error": f"Unknown case id '{case_id}'. Call list_cases."}
    return _trim(pipeline.run_case(case_id))


@mcp.tool(annotations=WRITE, description="Decode a new notice from pasted text for a person in the caseload (Medi-Cal, CalFresh, IHSS, or Medicare Savings Program). SSNs, phone numbers and emails are scrubbed before any model sees the text. Optional client facts (JSON object) such as {\"pregnant\": true, \"countable_assets\": 112000, \"household_size\": 1} drive exemption and asset screening. Returns the same structure as run_case.")
def decode_notice(person_id: str, notice_text: str, client_facts: dict | None = None) -> dict:
    if _person_or_error(person_id) is None:
        return {"error": f"Unknown person id '{person_id}'. Call list_people."}
    if not notice_text or not notice_text.strip():
        return {"error": "notice_text is empty."}
    return _trim(pipeline.decode_custom(person_id, scrub(notice_text), client=client_facts))


@mcp.tool(annotations=READ, description="The cached result of a case that has already been run (run_case or decode_notice), or result: null.")
def get_case(case_id: str) -> dict:
    res = pipeline.RESULTS.get(case_id)
    return {"result": _trim(res) if res else None}


@mcp.tool(annotations=WRITE, description="Record the navigator's approval of a case's draft letter after she has reviewed it. Optionally pass the edited letter text. The approval is hashed into the audit chain. This does not send anything.")
def approve_letter(case_id: str, navigator_name: str, letter: str | None = None) -> dict:
    if case_id not in pipeline.RESULTS:
        return {"error": "Run the case first."}
    if not navigator_name.strip():
        return {"error": "navigator_name is required."}
    return pipeline.approve(case_id, navigator_name.strip(), letter)


@mcp.tool(annotations=WRITE, description="Save every computed deadline of a run case into the person's record as dated, cited entries with titles in her language, so check-ins and Ask Carethropic can remind her.")
def save_deadlines_to_record(case_id: str) -> dict:
    if case_id not in pipeline.RESULTS:
        return {"error": "Run the case first."}
    return {"saved": pipeline.save_to_record(case_id)}


# ---------- elder record ----------
@mcp.tool(annotations=WRITE, description="Record a check-in for a person: type 'daily' (she is OK today) or 'med' with the medication item_id from her record. Returns the entry, her new status and a spoken confirmation in her language.")
def record_checkin(person_id: str, type: str, item_id: str | None = None, lang: str | None = None) -> dict:
    p = _person_or_error(person_id)
    if p is None:
        return {"error": f"Unknown person id '{person_id}'."}
    if type not in ("daily", "med"):
        return {"error": "type must be 'daily' or 'med'."}
    try:
        entry = vault.checkin(person_id, type, item_id)
    except ValueError as e:
        return {"error": str(e), "medications": [{"id": m["id"], "name": m["name"]} for m in p["medications"]]}
    lang = lang or p["language"]
    if type == "med":
        med = next(m for m in p["medications"] if m["id"] == item_id)
        spoken = briefing.feedback("med", lang, name=med["name"], time=entry["time"])
    else:
        spoken = briefing.feedback("daily", lang)
    return {"entry": entry, "status": vault.status(vault.get(person_id)), "spoken": spoken}


@mcp.tool(annotations=READ, description="Ask a question about one person's own record (medicines, appointments, deadlines, coverage, emergency contacts). Answers only from record items selected in code, cites their IDs, and never gives dosing advice: dose-change questions in seven languages get the medical advice guard. lang is a code: en, tl, zh-Hant, vi, ko, es, hi.")
def ask_record(person_id: str, question: str, lang: str | None = None) -> dict:
    if _person_or_error(person_id) is None:
        return {"error": f"Unknown person id '{person_id}'."}
    if not question.strip():
        return {"error": "question is empty."}
    return ask_mod.ask(person_id, scrub(question), lang)


@mcp.tool(annotations=READ, description="Spoken daily briefing for a person, composed in code from her record in her language: greeting, check-in status, medicines still to confirm, next appointment or deadline, what to tap. Lists the record IDs used.")
def daily_briefing(person_id: str, lang: str | None = None) -> dict:
    p = _person_or_error(person_id)
    if p is None:
        return {"error": f"Unknown person id '{person_id}'."}
    return briefing.compose(p, lang or p["language"])


@mcp.tool(annotations=WRITE, description="Record or revoke consent to print the emergency wallet card. given_by is 'self' or the name of the person who gave consent on her behalf; recorded_by is the navigator. Hashed into the audit chain.")
def record_consent(person_id: str, granted: bool, given_by: str, recorded_by: str) -> dict:
    if _person_or_error(person_id) is None:
        return {"error": f"Unknown person id '{person_id}'."}
    return {"consent": vault.set_consent(person_id, granted, given_by, recorded_by)}


@mcp.tool(annotations=READ, description="The emergency wallet card text (name, language, allergies, shared conditions, medications, emergency contacts; no member IDs or addresses). Refuses unless consent is recorded.")
def emergency_card(person_id: str) -> dict:
    if _person_or_error(person_id) is None:
        return {"error": f"Unknown person id '{person_id}'."}
    try:
        card = emergency.card(person_id)
    except emergency.ConsentRequired as e:
        return {"error": str(e), "consent": None}
    return {k: v for k, v in card.items() if k != "qr_svg"}


# ---------- finder ----------
@mcp.tool(annotations=READ, description="Search the curated, versioned directory of Claude for Nonprofits partners and Bay Area nonprofits serving Asian American women and elders. The query is parsed in code (place, Claude-partner intent, services, languages); results come in two groups with source links.")
def find_nonprofits(query: str) -> dict:
    if not query.strip():
        return {"error": "query is empty."}
    return nonprofits.search(query.strip())


# ---------- audit ----------
@mcp.tool(annotations=READ, description="The audit chain (hashes only, newest first) and whether it verifies.")
def audit_trail(limit: int = 50) -> dict:
    return {"valid": AUDIT.verify(), "entries": list(reversed(AUDIT.entries))[:max(1, min(limit, 500))], "count": len(AUDIT.entries)}


def _trim(res: dict) -> dict:
    """Drop the trace and large duplicates so a result stays well under the connector result limit."""
    out = {k: v for k, v in res.items() if k not in ("trace",)}
    return out


# ---------- auth ----------
class BearerTokenMiddleware:
    """Require Authorization: Bearer <CARETHROPIC_MCP_TOKEN> when the token is configured."""

    def __init__(self, app, token: str | None):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.token and scope.get("path", "").startswith("/mcp"):
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            if headers.get("authorization", "") != f"Bearer {self.token}":
                resp = JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
                await resp(scope, receive, send)
                return
        await self.app(scope, receive, send)


def build_app():
    """The Starlette app that serves /mcp. Mount it at the root, after the host's own routes; the host's lifespan runs mcp.session_manager."""
    from mcp.server.transport_security import TransportSecuritySettings
    # CARETHROPIC_MCP_ALLOWED_HOSTS="demo.example.org,abc.trycloudflare.com" turns on Host/Origin checking
    # (DNS-rebinding protection) for those names plus localhost. Unset, any Host is accepted, which is what a
    # tunnel or a container behind a load balancer needs; the bearer token is then the only gate.
    hosts = [h.strip() for h in (env("MCP_ALLOWED_HOSTS", "") or "").split(",") if h.strip()]
    if hosts:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                             allowed_hosts=["127.0.0.1:*", "localhost:*", *hosts],
                                             allowed_origins=["http://127.0.0.1:*", "http://localhost:*", *[f"https://{h}" for h in hosts]])
    else:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    inner = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True, transport_security=security)
    return BearerTokenMiddleware(inner, env("MCP_TOKEN"))
