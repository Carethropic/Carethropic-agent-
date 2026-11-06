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

# CalFresh (SNAP)
SNAP_ADVANCE_NOTICE_MIN_DAYS = 10  # 7 C.F.R. 273.13(a)(1)
SNAP_HEARING_WINDOW_DAYS = 90      # 7 C.F.R. 273.15(g)
SNAP_LATE_RECERT_DAYS = 30         # 7 C.F.R. 273.14(e)(3): still a recertification, benefits prorated
SNAP_TIMELY_RECERT_DAY = 15        # 7 C.F.R. 273.14(c)(2): file by the 15th of the last month

# IHSS and other county programs under the MPP
MPP_ADVANCE_NOTICE_MIN_DAYS = 10   # MPP 22-072.4
HEARING_GOOD_CAUSE_LIMIT_DAYS = 180  # Cal. W&I Code 10951(a)(2): late request only with good cause, never past 180 days

# Medi-Cal asset limit, reinstated January 1, 2026 (AB 116 (2025) sec. 59; ACWDL 25-14)
ASSET_LIMIT_FIRST_PERSON = 130_000
ASSET_LIMIT_EACH_ADDITIONAL = 65_000
ASSET_TRANSFER_SAFE_HARBOR = (date(2024, 1, 1), date(2025, 12, 31))  # AB 116 sec. 88: transfers in this window are not considered

PROGRAMS = {
    "discontinuance": "medi-cal", "work_rule_noncompliance": "medi-cal", "renewal_documents": "medi-cal",
    "annual_renewal": "medi-cal", "termination_no_renewal": "medi-cal",
    "calfresh_adverse_action": "calfresh", "calfresh_recertification": "calfresh",
    "ihss_reduction": "ihss", "ihss_termination": "ihss",
    "msp_discontinuance": "msp", "msp_renewal": "msp",
}


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


def _last_day_of_month(d: date) -> date:
    nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
    return nxt - timedelta(days=1)


def _first_of_next_month(d: date) -> date:
    return date(d.year + (d.month == 12), (d.month % 12) + 1, 1)


def asset_limit(household_size: int) -> int:
    """Reinstated Medi-Cal asset limit (AB 116 (2025); ACWDL 25-14): $130,000 plus $65,000 per additional person."""
    return ASSET_LIMIT_FIRST_PERSON + ASSET_LIMIT_EACH_ADDITIONAL * (max(int(household_size or 1), 1) - 1)


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


def screen_assets(client: dict, notice: dict) -> tuple[list[Finding], list[Finding]]:
    """Asset-limit screening for Medicare Savings Program and other non-MAGI Medi-Cal notices.

    Returns (exemptions, defects). Only fires when the notice reason concerns assets or a transfer,
    or when the client gives countable assets. The rules engine never guesses asset values.
    """
    exemptions, defects = [], []
    reason = (notice.get("reason") or "").lower()
    about_assets = any(w in reason for w in ("asset", "resource", "property", "savings", "transfer"))
    assets = client.get("countable_assets")
    if assets is not None and about_assets:
        limit = asset_limit(client.get("household_size", 1))
        if assets <= limit:
            exemptions.append(Finding("exemption", "under_asset_limit",
                                      f"Countable assets of ${assets:,.0f} are at or under the ${limit:,.0f} limit for a household of {client.get('household_size', 1)}.",
                                      "ca-acwdl-25-14"))
    if client.get("retirement_account_in_distribution") and about_assets:
        exemptions.append(Finding("exemption", "retirement_account_exempt",
                                  "A retirement account from which regular distributions are taken is exempt; the distributions count as income instead.",
                                  "ca-acwdl-25-14"))
    if client.get("owns_home_lives_in") and about_assets and ("home" in reason or "house" in reason or "property" in reason):
        exemptions.append(Finding("exemption", "home_exempt", "The home she lives in is exempt from the asset limit.", "ca-acwdl-25-14"))
    lo, hi = ASSET_TRANSFER_SAFE_HARBOR
    transfers = [date.fromisoformat(t) for t in client.get("asset_transfer_dates") or []]
    if "transfer" in reason and any(lo <= t <= hi for t in transfers):
        defects.append(Finding("defect", "transfer_in_safe_harbor_window",
                               "The notice relies on an asset transfer made between January 1, 2024 and December 31, 2025. The county may not consider transfers made in that window.",
                               "ca-ab-116-88"))
    return exemptions, defects


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
    # ---------- CalFresh (SNAP): 7 C.F.R. part 273 ----------
    elif t == "calfresh_adverse_action":
        r.deadlines.append(_mk("hearing_deadline", "Request a state hearing", nd + timedelta(days=SNAP_HEARING_WINDOW_DAYS), today,
                               "fed-7-273-15", "File a hearing request"))
        if eff:
            r.deadlines.append(_mk("continued_benefits", "Keep CalFresh at the current amount during appeal (continued benefits)",
                                   eff - timedelta(days=1), today, "fed-7-273-15", "Request the hearing before the change takes effect"))
            notice_days = (eff - nd).days
            if notice_days < SNAP_ADVANCE_NOTICE_MIN_DAYS:
                r.defects.append(Finding("defect", "short_advance_notice",
                                         f"Notice gave {notice_days} days of advance notice. Federal SNAP rules require at least {SNAP_ADVANCE_NOTICE_MIN_DAYS}.",
                                         "fed-7-273-13"))

    elif t == "calfresh_recertification":
        cert_end = _d(notice.get("certification_end_date"))
        if cert_end:
            last_month_start = date(cert_end.year, cert_end.month, 1)
            timely = stated_due or date(cert_end.year, cert_end.month, SNAP_TIMELY_RECERT_DAY)
            r.deadlines.append(_mk("recert_timely", "File the CalFresh recertification to keep benefits uninterrupted", timely, today,
                                   "fed-7-273-14", "Submit the recertification (SAR 7 / CF 37) and complete the interview"))
            r.deadlines.append(_mk("recert_late_window", "Last day a late recertification still counts (benefits prorated from filing)",
                                   cert_end + timedelta(days=SNAP_LATE_RECERT_DAYS), today, "fed-7-273-14",
                                   "File even if late; after this day a brand-new application is needed"))
            if nd >= last_month_start:
                r.defects.append(Finding("defect", "late_expiration_notice",
                                         "The notice of expiration was sent in the last month of the certification period. It must be sent before the first day of that month.",
                                         "fed-7-273-14"))
        else:
            r.escalations.append(Finding("escalation", "missing_certification_end", "Certification end date missing. Recertification deadlines not computed."))

    # ---------- IHSS: MPP division 22 and W&I Code ----------
    elif t in ("ihss_reduction", "ihss_termination"):
        r.deadlines.append(_mk("hearing_deadline", "Request a state hearing", nd + timedelta(days=HEARING_WINDOW_DAYS), today,
                               "ca-wic-10951", "File a hearing request"))
        if eff:
            r.deadlines.append(_mk("aid_paid_pending", "Keep current IHSS hours during appeal (aid paid pending)", eff - timedelta(days=1), today,
                                   "ca-mpp-22-072", "Request the hearing before the new hours take effect"))
            notice_days = (eff - nd).days
            if notice_days < MPP_ADVANCE_NOTICE_MIN_DAYS:
                r.defects.append(Finding("defect", "short_advance_notice",
                                         f"Notice gave {notice_days} days of advance notice. California rules require at least {MPP_ADVANCE_NOTICE_MIN_DAYS}.",
                                         "ca-mpp-22-072"))
        r.deadlines.append(_mk("hearing_good_cause_limit", "Absolute last day for a late hearing request (good cause only)",
                               nd + timedelta(days=HEARING_GOOD_CAUSE_LIMIT_DAYS), today, "ca-wic-10951",
                               "Only if the 90-day deadline was missed for a reason beyond her control"))
        if t == "ihss_termination" and client.get("lives_alone"):
            r.escalations.append(Finding("escalation", "ihss_loss_lives_alone", "IHSS termination for a person who lives alone. Safety review and attorney review recommended."))

    # ---------- Medicare Savings Programs (QMB, SLMB, QI): Medi-Cal rules plus the 2026 asset limit ----------
    elif t == "msp_discontinuance":
        r.deadlines.append(_mk("hearing_deadline", "Request a state hearing", nd + timedelta(days=HEARING_WINDOW_DAYS), today,
                               "ca-wic-10951", "File a hearing request"))
        if eff:
            r.deadlines.append(_mk("aid_paid_pending", "Keep Medicare premium help during appeal (aid paid pending)", eff - timedelta(days=1), today,
                                   "fed-431-230", "Request the hearing before the program ends"))
            notice_days = (eff - nd).days
            if notice_days < ADVANCE_NOTICE_MIN_DAYS:
                r.defects.append(Finding("defect", "short_advance_notice",
                                         f"Notice gave {notice_days} days of advance notice. Federal rules require at least {ADVANCE_NOTICE_MIN_DAYS}.",
                                         "fed-431-211"))
        if any(w in (notice.get("reason") or "").lower() for w in ("asset", "resource", "savings")):
            r.deadlines.append(_mk("asset_spend_down", "Last day to bring countable assets under the limit and keep coverage",
                                   _last_day_of_month(_first_of_next_month(nd)), today, "ca-hca-asset-tip",
                                   "Pay bills, prepay funeral costs, or make exempt purchases; keep receipts"))

    elif t == "msp_renewal":
        legal_due = nd + timedelta(days=RENEWAL_RESPONSE_MIN_DAYS)
        act_by = min(stated_due, legal_due) if stated_due else legal_due
        r.deadlines.append(_mk("renewal_response", "Return the renewal form, income proof and asset statements", act_by, today,
                               "fed-435-916", "Return the form and the listed documents"))
        if stated_due and (stated_due - nd).days < RENEWAL_RESPONSE_MIN_DAYS:
            r.defects.append(Finding("defect", "short_renewal_window",
                                     f"Notice gives {(stated_due - nd).days} days. Federal rules require at least {RENEWAL_RESPONSE_MIN_DAYS}.",
                                     "fed-435-916"))

    else:
        r.escalations.append(Finding("escalation", "unknown_notice_type", f"Notice type '{t}' is outside the knowledge base."))

    if t in ("discontinuance", "termination_no_renewal", "work_rule_noncompliance", "msp_discontinuance") and not notice.get("legal_basis_cited", True):
        r.defects.append(Finding("defect", "missing_legal_basis", "Notice does not cite the law or rule behind the action.", "fed-431-210"))
    if t in ("calfresh_adverse_action", "ihss_reduction", "ihss_termination") and not notice.get("legal_basis_cited", True):
        r.defects.append(Finding("defect", "missing_legal_basis", "Notice does not cite the regulation behind the action, so it is not an adequate notice.", "ca-mpp-22-001"))

    r.exemptions = screen_exemptions(client, t)
    if t in ("msp_discontinuance", "msp_renewal", "discontinuance", "annual_renewal", "termination_no_renewal"):
        ex, df = screen_assets(client, notice)
        r.exemptions += ex
        r.defects += df

    # Escalation rules
    if r.defects:
        r.escalations.append(Finding("escalation", "notice_defect", "Notice defect found. Attorney review recommended."))
    loses_coverage = t in ("discontinuance", "termination_no_renewal", "msp_discontinuance", "ihss_termination", "calfresh_adverse_action")
    if loses_coverage and (client.get("pregnant") or (client.get("postpartum_months") is not None and client["postpartum_months"] <= 12)):
        r.escalations.append(Finding("escalation", "pregnancy_coverage_loss", "Pregnant or postpartum client facing loss of coverage."))
    soonest = min((d.days_left for d in r.deadlines), default=99)
    r.urgent = soonest <= URGENT_DAYS
    if r.urgent:
        r.escalations.append(Finding("escalation", "urgent_deadline", f"A deadline is {max(soonest, 0)} day(s) away."))
    if any(e.code in ("notice_defect", "pregnancy_coverage_loss", "low_confidence", "unknown_notice_type", "ihss_loss_lives_alone", "missing_certification_end") for e in r.escalations):
        r.route = "attorney"

    auth = []
    for x in [*(d.authority for d in r.deadlines), *(f.authority for f in r.defects + r.exemptions)]:
        if x and x not in auth:
            auth.append(x)
    r.authorities = auth
    return r
