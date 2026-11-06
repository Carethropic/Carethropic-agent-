"""Deterministic legal logic for Kalinga.

Everything in this file is plain Python on purpose. Dates, deadlines, notice
defects, and exemption screening are never left to a language model. Claude
reads and explains; this module computes. The LLM output is then checked
against these computed values by the verifier.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

KB_PATH = Path(__file__).parent / "knowledge_base.json"


def load_kb() -> dict:
    return json.loads(KB_PATH.read_text())


KB = load_kb()
AUTH_BY_ID = {a["id"]: a for a in KB["authorities"]}


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def prev_business_day(d: date) -> date:
    """Conservative rule: if a deadline lands on a weekend, act by the Friday before."""
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


@dataclass
class Deadline:
    rule: str
    label: str
    due: str
    act_by: str
    days_left: int
    basis: str
    authority_id: str
    severity: str  # critical | high | normal
    note: str = ""


@dataclass
class Flag:
    code: str
    level: str  # escalate | warn | info
    message: str
    authority_id: Optional[str] = None


@dataclass
class RuleResult:
    deadlines: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    exemptions: list = field(default_factory=list)
    authority_ids: list = field(default_factory=list)
    triage_score: int = 0
    review_status: str = "ready_for_navigator"
    review_reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _mk(rule, label, due: date, today: date, basis, auth, note="") -> Deadline:
    act_by = prev_business_day(due)
    left = (act_by - today).days
    sev = "critical" if left <= 3 else "high" if left <= 10 else "normal"
    return Deadline(rule, label, due.isoformat(), act_by.isoformat(), left, basis, auth, sev, note)


ADVERSE = {"discontinuance", "denial", "reduction", "ce_noncompliance"}


def compute(facts: dict, client: dict, today: date) -> RuleResult:
    """facts: structured notice extraction. client: navigator-entered profile."""
    r = RuleResult()
    ntype = (facts.get("notice_type") or "unknown").lower()
    notice_date = parse_date(facts.get("notice_date"))
    effective = parse_date(facts.get("effective_date"))
    printed_due = parse_date(facts.get("response_due_date"))
    auth = set()

    if not notice_date:
        r.flags.append(Flag("NO_NOTICE_DATE", "escalate", "No notice date could be read, so legal deadlines cannot be computed safely."))

    # ---- Deadlines -------------------------------------------------------
    if notice_date and ntype in ADVERSE:
        r.deadlines.append(_mk("HEARING_90", "Last day to request a State Hearing",
                               notice_date + timedelta(days=90), today,
                               "90 days from the notice date (counted conservatively from the date printed, not the date received).",
                               "MC-HEARING-90"))
        auth.add("MC-HEARING-90")
        if ntype != "denial":
            if effective:
                app_due = effective - timedelta(days=1)
                basis = "Request before the effective date printed on the notice."
            else:
                app_due = notice_date + timedelta(days=10)
                basis = "No effective date printed, so 10 days from the notice date."
            r.deadlines.append(_mk("AID_PAID_PENDING", "Request hearing to keep coverage during appeal (aid paid pending)",
                                   app_due, today, basis, "MC-AID-PENDING"))
            auth.add("MC-AID-PENDING")

    if ntype == "ce_noncompliance" and notice_date:
        r.deadlines.append(_mk("CE_RESPONSE_30", "Respond with proof of hours or an exemption",
                               notice_date + timedelta(days=30), today,
                               "30 days from the notice date. The law may allow a few extra days for mailing; Kalinga uses the earlier date.",
                               "MC-CE-NONCOMPLIANCE"))
        auth.update({"MC-CE-NONCOMPLIANCE", "MC-CE-RULE"})

    if ntype in {"request_for_information", "renewal"}:
        due = printed_due or (notice_date + timedelta(days=30) if notice_date else None)
        if due:
            r.deadlines.append(_mk("RFI_DUE", "Return requested documents or renewal form", due, today,
                                   "Due date printed on the notice." if printed_due else "No due date printed; federal rules give at least 30 days, so Kalinga assumes 30.",
                                   "MC-RENEWAL"))
        auth.add("MC-RENEWAL")
        if printed_due and notice_date and (printed_due - notice_date).days < 30:
            r.flags.append(Flag("SHORT_RFI_WINDOW", "warn",
                                f"The notice gives only {(printed_due - notice_date).days} days to respond. Federal rules require at least 30 days for renewal information.",
                                "MC-RENEWAL"))

    if ntype == "discontinuance" and (facts.get("reason_code") or "").lower() in {"missing_information", "renewal_not_returned"} and effective:
        r.deadlines.append(_mk("RECONSIDERATION_90", "Return the form to restore coverage without reapplying",
                               effective + timedelta(days=90), today,
                               "90 days after coverage ends for a missing renewal form.", "MC-RENEWAL"))
        auth.add("MC-RENEWAL")

    # ---- Notice defect checks ------------------------------------------
    if ntype in ADVERSE and notice_date and effective:
        gap = (effective - notice_date).days
        if gap < 10:
            r.flags.append(Flag("SHORT_ADVANCE_NOTICE", "escalate",
                                f"The action takes effect {gap} days after the notice date. Federal rules generally require at least 10 days of advance notice.",
                                "MC-ADVANCE-NOTICE"))
            auth.add("MC-ADVANCE-NOTICE")
    if ntype in ADVERSE:
        if not facts.get("reason_text"):
            r.flags.append(Flag("NO_REASON", "escalate", "The notice does not state a clear reason for the action.", "MC-NOTICE-CONTENT"))
            auth.add("MC-NOTICE-CONTENT")
        if not facts.get("regulations_cited"):
            r.flags.append(Flag("NO_REGULATION", "warn", "The notice does not cite the regulation that supports the action.", "MC-NOTICE-CONTENT"))
            auth.add("MC-NOTICE-CONTENT")

    pref = (client.get("preferred_language") or "English").lower()
    notice_lang = (facts.get("language") or "English").lower()
    if pref != notice_lang:
        r.flags.append(Flag("LANGUAGE_ACCESS", "info",
                            f"The client prefers {client.get('preferred_language')}, and the notice is in {facts.get('language') or 'English'}. Request translated notices and an interpreter.",
                            "LANG-ACCESS"))
        auth.add("LANG-ACCESS")

    # ---- Exemption screener (community engagement) ---------------------
    if ntype == "ce_noncompliance" or "community_engagement" in (facts.get("topics") or []):
        birth = parse_date(client.get("pregnancy_end_date"))
        ref = notice_date or today
        if client.get("pregnant"):
            r.exemptions.append({"code": "PREGNANT", "label": "Currently pregnant", "proof": "Clinician statement or pregnancy verification"})
        if birth and (ref - birth).days <= 365:
            r.exemptions.append({"code": "POSTPARTUM", "label": f"Postpartum (pregnancy ended {birth.isoformat()})", "proof": "Birth record or hospital discharge summary"})
        ages = client.get("children_ages") or []
        if any(a is not None and a <= 13 for a in ages):
            r.exemptions.append({"code": "CAREGIVER_13", "label": "Parent or caregiver of a child age 13 or younger", "proof": "Child's birth certificate or school record"})
        if client.get("disability_or_medically_frail"):
            r.exemptions.append({"code": "MEDICALLY_FRAIL", "label": "Disability or serious medical condition", "proof": "Clinician statement describing how the condition limits work"})
        if client.get("meets_calfresh_or_calworks_work_rules"):
            r.exemptions.append({"code": "SNAP_TANF", "label": "Already meets CalFresh or CalWORKs work rules", "proof": "CalFresh or CalWORKs case record"})
        if r.exemptions:
            auth.add("MC-CE-EXEMPT")
            r.flags.append(Flag("EXEMPTION_LIKELY", "warn",
                                f"{len(r.exemptions)} exemption(s) appear to apply, so this noncompliance notice may be in error.", "MC-CE-EXEMPT"))

    # ---- Health continuity --------------------------------------------
    birth = parse_date(client.get("pregnancy_end_date"))
    if client.get("pregnant"):
        auth.update({"MC-PREGNANCY", "US-EMTALA"})
        if ntype in ADVERSE:
            r.flags.append(Flag("PRENATAL_AT_RISK", "escalate", "The client is pregnant and faces a loss of coverage. Prenatal care continuity is at risk.", "MC-PREGNANCY"))
    if birth and ((notice_date or today) - birth).days <= 365:
        auth.update({"MC-POSTPARTUM-12", "US-ACA-PREVENTIVE"})
        if ntype in ADVERSE:
            r.flags.append(Flag("POSTPARTUM_PROTECTED", "warn", "The client is within 12 months postpartum, which carries continuous coverage protections.", "MC-POSTPARTUM-12"))

    # ---- Extraction confidence gate ------------------------------------
    low = [k for k, v in (facts.get("confidence") or {}).items() if isinstance(v, (int, float)) and v < 0.7]
    if low:
        r.flags.append(Flag("LOW_CONFIDENCE_FIELDS", "escalate", "Kalinga could not read these fields with confidence: " + ", ".join(low) + "."))
    if printed_due and notice_date and printed_due < notice_date:
        r.flags.append(Flag("DATE_CONFLICT", "escalate", "The response date printed on the notice is earlier than the notice date."))

    # ---- Triage and human review gate ----------------------------------
    min_left = min([d.days_left for d in r.deadlines], default=99)
    score = 0
    score += 50 if min_left <= 3 else 30 if min_left <= 10 else 10 if min_left <= 30 else 0
    score += 15 * sum(1 for f in r.flags if f.level == "escalate")
    score += 5 * sum(1 for f in r.flags if f.level == "warn")
    score += 10 if client.get("pregnant") else 0
    r.triage_score = min(score, 100)

    esc = [f for f in r.flags if f.level == "escalate"]
    if esc:
        r.review_status = "needs_human_expert"
        r.review_reasons = [f.message for f in esc]
    r.authority_ids = sorted(auth)
    return r
