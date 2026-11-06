"""Claude agents for Kalinga.

Every agent is forced to answer through a JSON tool schema, so outputs are
structured and machine-checkable. Agents may only cite authority IDs that the
deterministic rules layer selected, and the verifier rejects anything else.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re

from anthropic import AsyncAnthropic

from rules import AUTH_BY_ID, KB

MODEL = os.environ.get("KALINGA_MODEL", "claude-sonnet-4-5")
FAST_MODEL = os.environ.get("KALINGA_FAST_MODEL", MODEL)

_client: AsyncAnthropic | None = None


def client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic()
    return _client


def live_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def _call_tool(system: str, content: list, tool_name: str, schema: dict, model: str = MODEL, max_tokens: int = 3000) -> dict:
    resp = await client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=[{"name": tool_name, "description": f"Return the {tool_name} result.", "input_schema": schema}],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": content}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Model returned no structured output")


# ---------------------------------------------------------------- Extractor
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "program": {"type": "string", "description": "Benefit program, for example Medi-Cal, CalFresh, CalWORKs."},
        "notice_type": {"type": "string", "enum": ["ce_noncompliance", "request_for_information", "renewal", "discontinuance", "denial", "reduction", "approval", "informational", "unknown"]},
        "notice_date": {"type": ["string", "null"], "description": "YYYY-MM-DD date printed as the notice or mailing date."},
        "effective_date": {"type": ["string", "null"], "description": "YYYY-MM-DD date the action takes effect, if any."},
        "response_due_date": {"type": ["string", "null"], "description": "YYYY-MM-DD date by which the person must respond, if printed."},
        "reason_code": {"type": "string", "enum": ["missing_information", "renewal_not_returned", "income_over_limit", "ce_hours_not_met", "other", "none"]},
        "reason_text": {"type": ["string", "null"], "description": "The reason exactly as stated, or null if the notice states none."},
        "regulations_cited": {"type": "array", "items": {"type": "string"}},
        "documents_requested": {"type": "array", "items": {"type": "string"}},
        "months_referenced": {"type": "array", "items": {"type": "string"}},
        "hearing_rights_included": {"type": "boolean"},
        "language": {"type": "string"},
        "agency": {"type": "string"},
        "case_number": {"type": ["string", "null"]},
        "topics": {"type": "array", "items": {"type": "string"}, "description": "Tags such as community_engagement, renewal, income, pregnancy."},
        "plain_summary": {"type": "string", "description": "Two sentences at a 6th grade reading level."},
        "confidence": {
            "type": "object",
            "properties": {k: {"type": "number"} for k in ["notice_type", "notice_date", "effective_date", "response_due_date", "documents_requested"]},
            "required": ["notice_type", "notice_date"],
        },
        "unreadable_parts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["program", "notice_type", "notice_date", "reason_code", "documents_requested", "hearing_rights_included", "language", "plain_summary", "confidence"],
}

EXTRACT_SYSTEM = """You are a meticulous benefits-notice reader working for trained navigators at a community nonprofit.
Read the notice and extract facts exactly as printed. Never guess a date. If a date is missing or unreadable, return null
and lower the confidence for that field. Confidence is your probability that the field is exactly right (0 to 1).
Use null for reason_text if the notice does not actually state a reason. List each document requested as its own item."""


async def extract_notice(file_bytes: bytes | None, media_type: str | None, text: str | None) -> dict:
    content = []
    if file_bytes:
        b64 = base64.standard_b64encode(file_bytes).decode()
        if media_type == "application/pdf":
            content.append({"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64}})
        else:
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})
    if text:
        content.append({"type": "text", "text": f"Notice text:\n{text}"})
    content.append({"type": "text", "text": "Extract the notice facts."})
    return await _call_tool(EXTRACT_SYSTEM, content, "notice_facts", EXTRACT_SCHEMA)


# ---------------------------------------------------------------- Specialists
CLAIMS_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "authority_ids": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "string", "enum": ["urgent", "important", "helpful"]},
                },
                "required": ["text", "authority_ids", "priority"],
            },
        }
    },
    "required": ["claims"],
}


def _authority_pack(ids: list[str]) -> str:
    return json.dumps([{k: AUTH_BY_ID[i][k] for k in ("id", "title", "citation", "summary", "how_to_use")} for i in ids if i in AUTH_BY_ID], indent=1)


SPECIALIST_RULES = """Rules you must follow:
1. Every claim must cite one or more authority_ids from the provided list. Never cite anything else.
2. Use only dates from the COMPUTED DEADLINES list. Never compute or invent a date yourself.
3. Write for a trained navigator: concrete, short, and actionable. Full sentences. No em dashes.
4. Return 3 to 6 claims, most urgent first."""


async def rights_agent(facts: dict, client_profile: dict, rules: dict, allowed: list[str]) -> dict:
    system = "You are Kalinga's Rights Agent, a benefits-law specialist who explains a Medi-Cal member's legal options and protections.\n" + SPECIALIST_RULES
    content = [{"type": "text", "text": f"NOTICE FACTS:\n{json.dumps(facts)}\n\nCLIENT PROFILE:\n{json.dumps(client_profile)}\n\nCOMPUTED DEADLINES AND FLAGS:\n{json.dumps(rules)}\n\nAUTHORITIES YOU MAY CITE:\n{_authority_pack(allowed)}\n\nWhat legal options and protections should the navigator act on?"}]
    return await _call_tool(system, content, "rights_claims", CLAIMS_SCHEMA)


async def health_agent(facts: dict, client_profile: dict, rules: dict, allowed: list[str]) -> dict:
    system = ("You are Kalinga's Health Navigator, a public health specialist focused on continuity of care for women and families. "
              "Identify care at risk from a coverage gap (prenatal, postpartum, maternal mental health, prescriptions, children's care) and how to protect it.\n" + SPECIALIST_RULES)
    content = [{"type": "text", "text": f"NOTICE FACTS:\n{json.dumps(facts)}\n\nCLIENT PROFILE:\n{json.dumps(client_profile)}\n\nCOMPUTED DEADLINES AND FLAGS:\n{json.dumps(rules)}\n\nAUTHORITIES YOU MAY CITE:\n{_authority_pack(allowed)}\n\nWhat care is at risk and what should the navigator do to protect it?"}]
    return await _call_tool(system, content, "health_claims", CLAIMS_SCHEMA)


# ---------------------------------------------------------------- Verifier
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "verdict": {"type": "string", "enum": ["supported", "partially_supported", "unsupported"]},
                    "reason": {"type": "string"},
                },
                "required": ["index", "verdict", "reason"],
            },
        }
    },
    "required": ["verdicts"],
}

DATE_RE = re.compile(r"\b(20\d\d-\d\d-\d\d|(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2},? 20\d\d)\b")


def deterministic_check(claims: list[dict], allowed: set[str], known_dates: set[str]) -> list[dict]:
    """Hard checks a model cannot talk its way past."""
    from datetime import datetime
    out = []
    for c in claims:
        problems = []
        ids = c.get("authority_ids") or []
        if not ids:
            problems.append("no citation")
        bad = [i for i in ids if i not in allowed]
        if bad:
            problems.append("cites unknown or out-of-scope authority " + ", ".join(bad))
        for m in DATE_RE.findall(c.get("text", "")):
            iso = m
            if not re.match(r"\d{4}-", m):
                try:
                    iso = datetime.strptime(m.replace(",", ""), "%B %d %Y").date().isoformat()
                except ValueError:
                    continue
            if iso not in known_dates:
                problems.append(f"date {m} does not match any computed deadline")
        out.append({**c, "hard_check": "pass" if not problems else "fail", "hard_problems": problems})
    return out


async def verifier_agent(claims: list[dict]) -> dict:
    system = ("You are Kalinga's Citation Verifier, a skeptical legal reviewer. For each claim, decide whether the cited authority summaries "
              "actually support the claim as written. Mark unsupported if the claim goes beyond what the authority says.")
    packs = {i: _authority_pack(c.get("authority_ids", [])) for i, c in enumerate(claims)}
    content = [{"type": "text", "text": "\n\n".join(f"CLAIM {i}: {c['text']}\nCITED AUTHORITIES:\n{packs[i]}" for i, c in enumerate(claims))}]
    return await _call_tool(system, content, "verdicts", VERIFY_SCHEMA, model=FAST_MODEL)


# ---------------------------------------------------------------- Drafter
DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "client_explanation": {"type": "string", "description": "Plain-language explanation for the client in the requested language, 6th grade reading level, warm and calm."},
        "response_letter": {"type": "string", "description": "Letter the client can send to the agency, for navigator review. Placeholders in [BRACKETS] only for facts not provided."},
        "document_checklist": {
            "type": "array",
            "items": {"type": "object", "properties": {"item": {"type": "string"}, "why": {"type": "string"}}, "required": ["item", "why"]},
        },
        "navigator_notes": {"type": "string", "description": "Short notes on judgment calls the navigator should double check."},
    },
    "required": ["client_explanation", "response_letter", "document_checklist", "navigator_notes"],
}


async def drafter_agent(facts: dict, client_profile: dict, rules: dict, verified_claims: list[dict], language: str) -> dict:
    system = ("You are Kalinga's Drafter. You write the client explanation and a response letter for a navigator to review. "
              "Use only the computed deadlines and verified claims you are given. Never invent dates, laws, or facts. "
              "Write in full sentences with good grammar and a calm, encouraging tone. Do not use em dashes.")
    content = [{"type": "text", "text": f"CLIENT LANGUAGE: {language}\n\nNOTICE FACTS:\n{json.dumps(facts)}\n\nCLIENT PROFILE:\n{json.dumps(client_profile)}\n\nCOMPUTED DEADLINES, FLAGS, EXEMPTIONS:\n{json.dumps(rules)}\n\nVERIFIED CLAIMS:\n{json.dumps(verified_claims)}\n\nDraft the client explanation (in {language}), the response letter (in English, addressed to the agency), the document checklist, and navigator notes."}]
    return await _call_tool(system, content, "drafts", DRAFT_SCHEMA, max_tokens=4000)
