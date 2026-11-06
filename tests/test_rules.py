import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from agents import deterministic_check  # noqa: E402
from rules import compute, prev_business_day  # noqa: E402
from samples import SAMPLES  # noqa: E402


def dl(r, rule):
    return next(d for d in r.deadlines if d.rule == rule)


def test_weekend_rolls_back_to_friday():
    assert prev_business_day(date(2026, 11, 8)) == date(2026, 11, 6)  # Sunday -> Friday
    assert prev_business_day(date(2026, 11, 9)) == date(2026, 11, 9)  # Monday stays


def test_ligaya_urgent_discontinuance():
    s = SAMPLES["ligaya"]
    r = compute(s["facts"], s["client"], date(2026, 11, 6))
    app = dl(r, "AID_PAID_PENDING")
    assert app.due == "2026-11-08" and app.act_by == "2026-11-06" and app.days_left == 0
    assert dl(r, "HEARING_90").due == "2027-01-31"
    assert dl(r, "RECONSIDERATION_90").due == "2027-02-07"
    codes = {f.code for f in r.flags}
    assert {"SHORT_ADVANCE_NOTICE", "NO_REGULATION", "PRENATAL_AT_RISK", "LANGUAGE_ACCESS"} <= codes
    assert r.review_status == "needs_human_expert"


def test_carmen_short_rfi_window_but_routine():
    s = SAMPLES["carmen"]
    r = compute(s["facts"], s["client"], date(2026, 11, 6))
    assert dl(r, "RFI_DUE").days_left == 17
    assert "SHORT_RFI_WINDOW" in {f.code for f in r.flags}
    assert r.review_status == "ready_for_navigator"


def test_rosa_two_exemptions():
    s = SAMPLES["rosa"]
    r = compute(s["facts"], s["client"], date(2027, 3, 6))
    assert {e["code"] for e in r.exemptions} == {"POSTPARTUM", "CAREGIVER_13"}
    assert dl(r, "CE_RESPONSE_30").act_by == "2027-04-02"
    assert "MC-CE-EXEMPT" in r.authority_ids


def test_no_exemption_for_older_children():
    s = SAMPLES["rosa"]
    client = {"preferred_language": "English", "children_ages": [15]}
    r = compute(s["facts"], client, date(2027, 3, 6))
    assert r.exemptions == []


def test_missing_notice_date_escalates():
    r = compute({"notice_type": "discontinuance", "reason_text": "x", "regulations_cited": ["y"]}, {}, date(2026, 11, 6))
    assert r.review_status == "needs_human_expert"


def test_low_confidence_escalates():
    s = SAMPLES["carmen"]
    facts = dict(s["facts"], confidence={"notice_date": 0.4})
    r = compute(facts, s["client"], date(2026, 11, 6))
    assert r.review_status == "needs_human_expert"


def test_verifier_blocks_invented_dates_and_citations():
    claims = [
        {"text": "File by 2026-11-06.", "authority_ids": ["MC-AID-PENDING"]},
        {"text": "File by December 25, 2026.", "authority_ids": ["MC-AID-PENDING"]},
        {"text": "You can sue for damages.", "authority_ids": ["MADE-UP-LAW"]},
        {"text": "Uncited advice.", "authority_ids": []},
    ]
    out = deterministic_check(claims, {"MC-AID-PENDING"}, {"2026-11-06"})
    assert [c["hard_check"] for c in out] == ["pass", "fail", "fail", "fail"]
