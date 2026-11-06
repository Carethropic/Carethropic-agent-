"""Deterministic legal core: deadlines, defects, exemptions, escalation.

The model never does date math. Every date in any Carethropic output comes from here.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

# California state holidays (observed) used for conservative roll-back.
CA_HOLIDAYS = {
    date(2026, 11, 11), date(2026, 11, 26), date(2026, 11, 27), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 31),
    date(2027, 5, 31), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 11),
    date(2027, 11, 25), date(2027, 11, 26), date(2027, 12, 24),
}

ADVANCE_NOTICE_MIN_DAYS = 10      # 42 C.F.R. 431.211
HEARING_WINDOW_DAYS = 90          # 42 C.F.R. 431.221(d); Cal. W&I Code 10951
WORK_RULE_RESPONSE_DAYS = 30      # P.L. 119-21 sec. 71119 noncompliance notice
RENEWAL_RESPONSE_MIN_DAYS = 30    # 42 C.F.R. 435.916
RECONSIDERATION_DAYS = 90         # 42 C.F.R. 435.916 reconsideration period
URGENT_DAYS = 3


def business_day_on_or_before(d: date) -> date:
    """Conservative act-by date: weekends and holidays roll BACK to the prior business day."""
    while d.weekday() >= 5 or d in CA_HOLIDAYS:
        d -= timedelta(days=1)
    return d


@dataclass
class Deadline:
    key: str
    label: str
    date: str
    days_left: int
    authority: str
    action: str
    rolled_back: bool = False


@dataclass
class Finding:
    kind: str          # defect | exemption | escalation
    code: str
    message: str
    authority: str | None = None


@dataclass
class RulesResult:
    deadlines: list[Deadline] = field(default_factory=list)
    defects: list[Finding] = field(default_factory=list)
    exemptions: list[Finding] = field(default_factory=list)
    escalations: list[Finding] = field(default_factory=list)
    authorities: list[str] = field(default_factory=list)
    route: str = "navigator"   # navigator | attorney
    urgent: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def deadline_map(self) -> dict[str, str]:
        return {d.key: d.date for d in self.deadlines}


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _mk(key, label, raw: date, today: date, authority, action) -> Deadline:
    adj = business_day_on_or_before(raw)
    return Deadline(key, label, adj.isoformat(), (adj - today).days, authority, action, adj != raw)


def screen_exemptions(client: dict, notice_type: str) -> list[Finding]:
    """Work rule exemptions (P.L. 119-21 sec. 71119)."""
    if notice_type != "work_rule_noncompliance":
        return []
    out = []
    if client.get("pregnant"):
        out.append(Finding("exemption", "pregnant", "Pregnant members are exempt from work reporting.", "pl-119-21-71119"))
    pp = client.get("postpartum_months")
    if pp is not None and pp <= 12:
        out.append(Finding("exemption", "postpartum", f"Postpartum ({pp} months) is within the exempt postpartum period.", "pl-119-21-71119"))
    ages = client.get("children_ages") or []
    if any(a <= 13 for a in ages):
        out.append(Finding("exemption", "caregiver_child_13", "Parent or caretaker of a child age 13 or younger is exempt.", "pl-119-21-71119"))
    age = client.get("age")
    if age is not None and (age < 19 or age > 64):
        out.append(Finding("exemption", "age_outside_19_64", "Work reporting applies only to adults age 19 to 64.", "pl-119-21-71119"))
    if client.get("medically_frail"):
        out.append(Finding("exemption", "medically_frail", "Medically frail members are exempt.", "pl-119-21-71119"))
    return out


def evaluate(notice: dict, client: dict, today: date) -> RulesResult:
    """notice: extracted fields (ISO date strings). client: screening facts."""
    r = RulesResult()
    t = notice["notice_type"]
    nd = _d(notice.get("notice_date"))
    eff = _d(notice.get("effective_date"))
    stated_due = _d(notice.get("stated_due_date"))
    conf = notice.get("confidence", {})

    low = [k for k, v in conf.items() if v < 0.7]
    if low:
        r.escalations.append(Finding("escalation", "low_confidence", f"Low confidence on: {', '.join(low)}. A human must confirm."))

    if nd is None:
        r.escalations.append(Finding("escalation", "missing_notice_date", "Notice date missing. No deadlines computed."))
        r.route = "attorney"
        return r

    if t == "discontinuance":
        r.deadlines.append(_mk("hearing_deadline", "Request a state hearing", nd + timedelta(days=HEARING_WINDOW_DAYS), today,
                               "ca-wic-10951", "File a hearing request"))
        if eff:
            r.deadlines.append(_mk("aid_paid_pending", "Keep coverage during appeal (aid paid pending)", eff - timedelta(days=1), today,
                                   "fed-431-230", "Request the hearing before coverage ends"))
            notice_days = (eff - nd).days
            if notice_days < ADVANCE_NOTICE_MIN_DAYS:
                r.defects.append(Finding("defect", "short_advance_notice",
                                         f"Notice gave {notice_days} days of advance notice. Federal rules require at least {ADVANCE_NOTICE_MIN_DAYS}.",
                                         "fed-431-211"))

    elif t == "work_rule_noncompliance":
        r.deadlines.append(_mk("work_rule_response", "Respond to work rule notice", nd + timedelta(days=WORK_RULE_RESPONSE_DAYS), today,
                               "pl-119-21-71119", "Send exemption proof or compliance proof"))
        r.deadlines.append(_mk("hearing_deadline", "Request a state hearing", nd + timedelta(days=HEARING_WINDOW_DAYS), today,
                               "ca-wic-10951", "File a hearing request if the county acts"))

    elif t in ("renewal_documents", "annual_renewal"):
        legal_due = nd + timedelta(days=RENEWAL_RESPONSE_MIN_DAYS)
        act_by = min(stated_due, legal_due) if stated_due else legal_due
        r.deadlines.append(_mk("renewal_response", "Return renewal form and documents", act_by, today,
                               "fed-435-916", "Return the form and the listed documents"))
        if stated_due and (stated_due - nd).days < RENEWAL_RESPONSE_MIN_DAYS:
            r.defects.append(Finding("defect", "short_renewal_window",
                                     f"Notice gives {(stated_due - nd).days} days. Federal rules require at least {RENEWAL_RESPONSE_MIN_DAYS}.",
                                     "fed-435-916"))

    elif t == "termination_no_renewal":
        term = eff or nd
        r.deadlines.append(_mk("reconsideration", "Return renewal form to restore coverage (reconsideration)",
                               term + timedelta(days=RECONSIDERATION_DAYS), today, "fed-435-916",
                               "Return the renewal form; coverage can restart without a new application"))
        r.deadlines.append(_mk("hearing_deadline", "Request a state hearing", nd + timedelta(days=HEARING_WINDOW_DAYS), today,
                               "ca-wic-10951", "File a hearing request"))
    else:
        r.escalations.append(Finding("escalation", "unknown_notice_type", f"Notice type '{t}' is outside the knowledge base."))

    if t in ("discontinuance", "termination_no_renewal", "work_rule_noncompliance") and not notice.get("legal_basis_cited", True):
        r.defects.append(Finding("defect", "missing_legal_basis", "Notice does not cite the law or rule behind the action.", "fed-431-210"))

    r.exemptions = screen_exemptions(client, t)

    # Escalation rules
    if r.defects:
        r.escalations.append(Finding("escalation", "notice_defect", "Notice defect found. Attorney review recommended."))
    loses_coverage = t in ("discontinuance", "termination_no_renewal")
    if loses_coverage and (client.get("pregnant") or (client.get("postpartum_months") is not None and client["postpartum_months"] <= 12)):
        r.escalations.append(Finding("escalation", "pregnancy_coverage_loss", "Pregnant or postpartum client facing loss of coverage."))
    soonest = min((d.days_left for d in r.deadlines), default=99)
    r.urgent = soonest <= URGENT_DAYS
    if r.urgent:
        r.escalations.append(Finding("escalation", "urgent_deadline", f"A deadline is {max(soonest, 0)} day(s) away."))
    if any(e.code in ("notice_defect", "pregnancy_coverage_loss", "low_confidence", "unknown_notice_type") for e in r.escalations):
        r.route = "attorney"

    auth = []
    for x in [*(d.authority for d in r.deadlines), *(f.authority for f in r.defects + r.exemptions)]:
        if x and x not in auth:
            auth.append(x)
    r.authorities = auth
    return r
