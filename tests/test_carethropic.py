"""Carethropic test suite: rules, vault status, Ask Carethropic guard and verifier, emergency consent, nonprofit finder, API."""
import os
import sys
from datetime import date, datetime
from pathlib import Path

os.environ["CARETHROPIC_REPLAY"] = "1"
os.environ["CARETHROPIC_NOW"] = "2026-11-06T10:30"
os.environ["CARETHROPIC_DB"] = ":memory:"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import ask  # noqa: E402
import emergency  # noqa: E402
import nonprofits  # noqa: E402
import pipeline  # noqa: E402
import rules  # noqa: E402
import vault  # noqa: E402
from app import app  # noqa: E402
from common import TZ, AUDIT, scrub  # noqa: E402

TODAY = date(2026, 11, 6)


@pytest.fixture(autouse=True)
def fresh():
    vault.reset()
    pipeline.RESULTS.clear()
    yield


# ---------- rules ----------
def test_discontinuance_deadlines_and_short_notice_defect():
    r = rules.evaluate({"notice_type": "discontinuance", "notice_date": "2026-11-02", "effective_date": "2026-11-09",
                        "legal_basis_cited": True, "confidence": {"notice_date": 0.97}}, {"pregnant": True}, TODAY)
    d = r.deadline_map()
    assert d["hearing_deadline"] == "2027-01-29"          # 90 days = Sun Jan 31 → rolled back to Fri Jan 29
    assert d["aid_paid_pending"] == "2026-11-06"           # Nov 8 is a Sunday → Fri Nov 6
    assert any(f.code == "short_advance_notice" for f in r.defects)
    assert r.route == "attorney" and r.urgent


def test_weekend_and_holiday_rollback():
    assert rules.business_day_on_or_before(date(2026, 11, 28)).isoformat() == "2026-11-25"  # Sat → Fri 27 is a holiday → Wed 25
    assert rules.business_day_on_or_before(date(2026, 11, 11)).isoformat() == "2026-11-10"  # Veterans Day


def test_work_rule_exemptions_postpartum_and_child():
    r = rules.evaluate({"notice_type": "work_rule_noncompliance", "notice_date": "2027-02-01", "legal_basis_cited": True, "confidence": {}},
                       {"postpartum_months": 3, "age": 31, "children_ages": [0, 6]}, date(2027, 2, 3))
    codes = {f.code for f in r.exemptions}
    assert {"postpartum", "caregiver_child_13"} <= codes
    assert r.deadline_map()["work_rule_response"] == "2027-03-03"


def test_renewal_short_window_defect_and_min_due():
    r = rules.evaluate({"notice_type": "renewal_documents", "notice_date": "2026-11-04", "stated_due_date": "2026-11-25",
                        "legal_basis_cited": True, "confidence": {}}, {}, TODAY)
    assert any(f.code == "short_renewal_window" for f in r.defects)
    assert r.deadline_map()["renewal_response"] == "2026-11-25"  # stated due (a Wednesday) is earlier than the legal minimum, so it stands


def test_low_confidence_escalates():
    r = rules.evaluate({"notice_type": "termination_no_renewal", "notice_date": "2026-10-12", "effective_date": "2026-10-27",
                        "legal_basis_cited": False, "confidence": {"effective_date": 0.62}}, {"age": 74}, TODAY)
    assert r.route == "attorney"
    assert {e.code for e in r.escalations} >= {"low_confidence", "notice_defect"}


# ---------- pipeline + verifier ----------
def test_pipeline_replay_cases_have_zero_invented_citations():
    for cid in ("ligaya", "rosa", "carmen", "wai-ling", "hoa"):
        res = pipeline.run_case(cid)
        selected = res["rules"]["authorities"] + ["ca-wic-14005-18"]
        for c in res["claims"]:
            assert all(a in selected for a in c["authority_ids"])
            assert "{{deadline" not in c["text"]
    assert pipeline.RESULTS["ligaya"]["gate"]["route"] == "attorney"
    assert pipeline.RESULTS["rosa"]["rules"]["exemptions"]


def test_verifier_removes_bad_claims():
    kept, removed = pipeline.verify_claims([
        {"agent": "x", "kind": "legal", "text": "File by {{deadline:hearing_deadline}}.", "authority_ids": ["ca-wic-10951"]},
        {"agent": "x", "kind": "legal", "text": "File by 2026-12-01.", "authority_ids": ["ca-wic-10951"]},
        {"agent": "x", "kind": "legal", "text": "Made up rule.", "authority_ids": ["fed-999"]},
        {"agent": "x", "kind": "legal", "text": "No cite.", "authority_ids": []},
    ], ["ca-wic-10951"], ["hearing_deadline"])
    assert len(kept) == 1 and len(removed) == 3


def test_save_to_record_adds_deadline_once():
    pipeline.run_case("wai-ling")
    a = pipeline.save_to_record("wai-ling")
    b = pipeline.save_to_record("wai-ling")
    p = vault.get("p-wailing")
    assert len(a) == 1 and len(b) == 1
    assert len([e for e in p["events"] if e["type"] == "deadline"]) == 1
    assert p["events"][-1]["title_local"]["zh-Hant"]


# ---------- vault status ----------
def test_status_missed_two_days_and_missed_med():
    p = vault.get("p-remy")  # last daily check-in 2 days ago; amlodipine due 08:00, now 10:30 → missed
    st = vault.status(p, datetime(2026, 11, 6, 10, 30, tzinfo=TZ))
    assert st["level"] == "missed_2_days"
    assert any(i.get("item_id") == "med-remy-1" and i["state"] == "missed" for i in st["items"])
    vault.checkin("p-remy", "daily")
    vault.checkin("p-remy", "med", "med-remy-1")
    vault.checkin("p-remy", "med", "med-remy-2")
    st = vault.status(p, datetime(2026, 11, 6, 10, 30, tzinfo=TZ))
    assert st["level"] == "ok"


def test_status_late_inside_grace():
    p = vault.get("p-wailing")  # losartan 09:00, daily done today
    st = vault.status(p, datetime(2026, 11, 6, 9, 30, tzinfo=TZ))
    assert st["level"] == "ok"  # confirmed at 09:10
    p["checkins"] = [c for c in p["checkins"] if c["type"] != "med"]
    assert vault.status(p, datetime(2026, 11, 6, 9, 30, tzinfo=TZ))["level"] == "late"
    assert vault.status(p, datetime(2026, 11, 6, 12, 0, tzinfo=TZ))["level"] == "missed"


# ---------- Ask Carethropic ----------
@pytest.mark.parametrize("q", ["Should I take two pills since I forgot?", "Can I double my dose?", "Dapat ko bang inumin ang dalawa?",
                               "我可以吃兩粒嗎", "Tôi có nên uống hai viên không", "두 알 먹어도 돼요?", "क्या मैं दो गोली ले सकती हूँ", "¿Puedo tomar dos pastillas?"])
def test_advice_guard_recall(q):
    a = ask.ask("p-remy", q)
    assert a["guard"] is True and a["intent"] == "advice"
    assert "pharmacist" in a["answer"].lower() or "pharmac" in a["answer"].lower() or a["lang"] != "en"


def test_med_taken_is_honest_about_no_confirmation():
    a = ask.ask("p-remy", "Did I take my blood pressure pill today?", "en")
    assert "no check mark" in a["answer"] and "Amlodipine" in a["answer"]
    vault.checkin("p-remy", "med", "med-remy-1")
    a = ask.ask("p-remy", "Did I take my blood pressure pill today?", "en")
    assert a["answer"].startswith("Yes.") and "10:30" in a["answer"]


def test_ask_multilingual_intents():
    assert ask.classify("kailan ang deadline ng medi-cal ko") == "deadline"
    assert ask.classify("我的緊急聯絡人是誰") == "ice"
    assert ask.classify("lịch hẹn bác sĩ của tôi") == "appointment"
    assert ask.classify("내 알레르기") == "allergy"
    assert ask.classify("मेरी दवाइयाँ क्या हैं") == "med_list"
    assert ask.classify("¿cuál es mi seguro?") == "coverage"


def test_ask_deadline_after_save_in_her_language():
    pipeline.run_case("wai-ling"); pipeline.save_to_record("wai-ling")
    a = ask.ask("p-wailing", "When is my Medi-Cal deadline?")
    assert a["lang"] == "zh-Hant" and "2026-" in a["answer"] and a["cited"][0]["kind"] == "deadline"


def test_ask_not_found_and_verifier():
    a = ask.ask("p-rosa", "What is my blood type?", "en")
    assert a["intent"] == "unknown" and a["cited"] == [] and "not in your record" in a["answer"]
    ok, notes = ask.verify("Take it at 2026-12-25.", ["med-x"], {"med-remy-1": {"times": ["08:00"]}})
    assert not ok and len(notes) >= 2


# ---------- emergency ----------
def test_emergency_card_requires_consent_and_hides_ids():
    with pytest.raises(emergency.ConsentRequired):
        emergency.card("p-remy")
    vault.set_consent("p-remy", True, "self", "nav")
    c = emergency.card("p-remy")
    assert "<svg" in c["qr_svg"] and "Penicillin" in c["payload"] and "9XQ47731852" not in c["payload"]
    vault.set_consent("p-remy", False, "self", "nav")
    with pytest.raises(emergency.ConsentRequired):
        emergency.card("p-remy")


# ---------- privacy + audit ----------
def test_scrub_and_audit_chain():
    assert "123-45-6789" not in scrub("SSN 123-45-6789 call (510) 555-0100 me@x.org")
    n = len(AUDIT.entries)
    AUDIT.add("test", {"a": 1})
    assert AUDIT.verify() and len(AUDIT.entries) == n + 1


# ---------- nonprofit finder ----------
def test_acceptance_query_claude_sponsors_sf():
    r = nonprofits.search("Claude Non-profit sponsors in san francisco")
    assert r["parsed"]["claude_intent"] and r["parsed"]["place"]["label"] == "San Francisco"
    claude = r["groups"][0]["results"]
    bay = r["groups"][1]["results"]
    assert [c["id"] for c in claude[:2]] == ["tipping-point", "taproot"]
    assert all(c["local"] for c in claude[:2])
    ids = {b["id"] for b in bay}
    assert {"self-help-elderly", "kimochi", "apilo"} <= ids
    assert all("San Francisco" in b["cities"] for b in bay)


def test_finder_typos_aliases_and_languages():
    r = nonprofits.search("claude sponsers SF")
    assert r["parsed"]["place"]["label"] == "San Francisco"
    r = nonprofits.search("Vietnamese senior services San Jose")
    assert r["groups"][1]["results"][0]["id"] in ("aaci", "sourcewise")
    assert r["parsed"]["languages"] == ["vi"]
    r = nonprofits.search("Hindi speaking women support South Bay")
    assert any(x["id"] in ("maitri", "icc") for x in r["groups"][1]["results"][:2])
    r = nonprofits.search("elder care in Fresno")
    assert r["note"] and r["groups"][1]["results"]


# ---------- API ----------
def test_api_end_to_end():
    c = TestClient(app)
    assert c.get("/api/meta").json()["mode"] == "replay"
    assert c.get("/").status_code == 200
    rows = c.get("/api/console").json()["rows"]
    assert any("missed_checkin" in [f["kind"] for f in r["flags"]] for r in rows)
    res = c.post("/api/cases/ligaya/run").json()
    assert res["gate"]["route"] == "attorney"
    assert c.post("/api/cases/ligaya/approve", json={"navigator": "Ana"}).json()["approved"]
    assert c.post("/api/cases/ligaya/save").json()["saved"]
    a = c.post("/api/people/p-remy/ask", json={"question": "Who is my emergency contact?"}).json()
    assert "Joy" in a["answer"]
    assert c.get("/api/people/p-remy/emergency-card").status_code == 403
    assert c.post("/api/people/p-remy/consent", json={"granted": True, "recorded_by": "Ana"}).status_code == 200
    assert c.get("/api/people/p-remy/emergency-card").status_code == 200
    s = c.get("/api/nonprofits/search", params={"q": "Claude Non-profit sponsors in san francisco"}).json()
    assert s["groups"][0]["results"][0]["id"] == "tipping-point"
    assert c.get("/api/nonprofits/search", params={"q": ""}).status_code == 400
    assert c.get("/api/people/p-remy").json()["coverage"][0]["member_id"].endswith("852")
    assert c.get("/api/audit").json()["valid"]
    d = c.post("/api/decode", data={"person_id": "p-hoa", "text": "NOTICE OF ACTION 10/20/2026. Your Medi-Cal will stop on 11/15/2026. SSN 123-45-6789."}).json()
    assert d["notice"]["notice_type"] == "discontinuance" and d["rules"]["deadlines"]


# ---------- env names ----------
def test_env_prefers_carethropic_and_falls_back_to_kalinga(monkeypatch):
    from common import env
    monkeypatch.delenv("CARETHROPIC_MODEL", raising=False)
    monkeypatch.setenv("KALINGA_MODEL", "legacy-model")
    assert env("MODEL") == "legacy-model"
    monkeypatch.setenv("CARETHROPIC_MODEL", "new-model")
    assert env("MODEL") == "new-model"
    assert env("DOES_NOT_EXIST", "dflt") == "dflt"


# ---------- persistence ----------
def test_store_round_trips_people_results_and_audit_across_reopen(tmp_path):
    from common import AuditChain
    from store import Store

    path = tmp_path / "carethropic.db"
    s1 = Store(path)
    chain = AuditChain()
    chain.attach(s1)
    s1.save_person({"id": "p-x", "display_name": "X", "medications": [], "events": [], "coverage": [], "checkins": [], "consent": None})
    s1.save_result("case-x", {"gate": {"route": "approve"}, "saved_to_record": False})
    s1.set_meta("seeded_on", "2026-11-06")
    chain.add("checkin", {"pid": "p-x"})
    chain.add("consent_granted", {"pid": "p-x"})
    s1.close()

    s2 = Store(path)
    assert s2.load_people()["p-x"]["display_name"] == "X"
    assert s2.load_results()["case-x"]["gate"]["route"] == "approve"
    assert s2.get_meta("seeded_on") == "2026-11-06"
    chain2 = AuditChain()
    chain2.attach(s2)
    assert [e["kind"] for e in chain2.entries] == ["checkin", "consent_granted"]
    assert chain2.verify()
    chain2.add("ask", {"pid": "p-x"})          # the chain continues from the stored tail
    assert chain2.entries[-1]["prev"] == chain2.entries[-2]["hash"]
    assert chain2.verify()
    s2.close()


def test_checkin_and_consent_are_written_through_to_the_store():
    from store import STORE
    vault.checkin("p-remy", "daily")
    vault.set_consent("p-remy", True, "self", "A. Navigator")
    saved = STORE.load_people()["p-remy"]
    assert saved["checkins"][-1]["type"] == "daily"
    assert saved["consent"]["given_by"] == "self"
    vault.reset()
    assert STORE.load_people()["p-remy"]["consent"] is None


def test_reset_endpoint_clears_persisted_results():
    from store import STORE
    c = TestClient(app)
    assert c.post("/api/cases/ligaya/run").status_code == 200
    assert "ligaya" in STORE.load_results()
    assert c.post("/api/reset").json()["ok"]
    assert STORE.load_results() == {}
    assert c.get("/api/meta").json()["seeded_on"] == "2026-11-06"


# ---------- CalFresh, IHSS, Medicare Savings Program rules ----------
def test_calfresh_adverse_action_continued_benefits_and_short_notice():
    r = rules.evaluate({"notice_type": "calfresh_adverse_action", "notice_date": "2026-11-02", "effective_date": "2026-11-09",
                        "legal_basis_cited": True, "confidence": {}}, {"age": 68}, TODAY)
    d = r.deadline_map()
    assert d["continued_benefits"] == "2026-11-06"     # Nov 8 is a Sunday → Fri Nov 6
    assert d["hearing_deadline"] == "2027-01-29"       # 90 days = Sun Jan 31 → Fri Jan 29
    assert {f.code for f in r.defects} == {"short_advance_notice"}
    assert next(f for f in r.defects if f.code == "short_advance_notice").authority == "fed-7-273-13"
    assert r.route == "attorney" and r.urgent


def test_calfresh_recertification_timely_and_late_windows():
    r = rules.evaluate({"notice_type": "calfresh_recertification", "notice_date": "2026-11-04", "certification_end_date": "2026-12-31",
                        "legal_basis_cited": True, "confidence": {}}, {"age": 68}, TODAY)
    d = r.deadline_map()
    assert d["recert_timely"] == "2026-12-15"          # 15th of the last month
    assert d["recert_late_window"] == "2027-01-29"     # Dec 31 + 30 = Sat Jan 30 → Fri Jan 29
    assert not r.defects and r.route == "navigator"
    # Notice of expiration sent inside the last month is a defect
    r2 = rules.evaluate({"notice_type": "calfresh_recertification", "notice_date": "2026-12-03", "certification_end_date": "2026-12-31",
                         "legal_basis_cited": True, "confidence": {}}, {}, TODAY)
    assert [f.code for f in r2.defects] == ["late_expiration_notice"] and r2.route == "attorney"
    # A printed due date earlier than the 15th wins
    r3 = rules.evaluate({"notice_type": "calfresh_recertification", "notice_date": "2026-11-04", "certification_end_date": "2026-12-31",
                         "stated_due_date": "2026-12-05", "legal_basis_cited": True, "confidence": {}}, {}, TODAY)
    assert r3.deadline_map()["recert_timely"] == "2026-12-04"   # Dec 5 is a Saturday


def test_ihss_reduction_deadlines_good_cause_limit_and_termination_escalation():
    r = rules.evaluate({"notice_type": "ihss_reduction", "notice_date": "2026-11-03", "effective_date": "2026-12-01",
                        "legal_basis_cited": True, "confidence": {}}, {"age": 81, "lives_alone": True}, TODAY)
    d = r.deadline_map()
    assert d["aid_paid_pending"] == "2026-11-30"
    assert d["hearing_deadline"] == "2027-02-01"
    assert d["hearing_good_cause_limit"] == "2027-04-30"   # 180 days = Sun May 2 → Fri Apr 30
    assert r.route == "navigator" and not r.defects
    t = rules.evaluate({"notice_type": "ihss_termination", "notice_date": "2026-11-03", "effective_date": "2026-11-10",
                        "legal_basis_cited": False, "confidence": {}}, {"age": 81, "lives_alone": True}, TODAY)
    codes = {f.code for f in t.defects}
    assert codes == {"short_advance_notice", "missing_legal_basis"}
    assert next(f for f in t.defects if f.code == "missing_legal_basis").authority == "ca-mpp-22-001"
    assert any(e.code == "ihss_loss_lives_alone" for e in t.escalations) and t.route == "attorney"


def test_asset_limit_and_msp_screening():
    assert rules.asset_limit(1) == 130_000
    assert rules.asset_limit(2) == 195_000
    assert rules.asset_limit(0) == 130_000
    notice = {"notice_type": "msp_discontinuance", "notice_date": "2026-11-01", "effective_date": "2026-12-01",
              "reason": "Assets over the limit; includes a transfer to a family member in March 2025.", "legal_basis_cited": True, "confidence": {}}
    client = {"age": 71, "household_size": 1, "countable_assets": 112_000, "retirement_account_in_distribution": True,
              "asset_transfer_dates": ["2025-03-15"]}
    r = rules.evaluate(notice, client, TODAY)
    d = r.deadline_map()
    assert d["aid_paid_pending"] == "2026-11-30" and d["hearing_deadline"] == "2027-01-29"
    assert d["asset_spend_down"] == "2026-12-31"       # end of the month after the notice
    assert {f.code for f in r.exemptions} == {"under_asset_limit", "retirement_account_exempt"}
    assert [f.code for f in r.defects] == ["transfer_in_safe_harbor_window"] and r.route == "attorney"
    # Over the limit, transfer outside the window: no exemption, no defect
    r2 = rules.evaluate(notice, {"household_size": 1, "countable_assets": 150_000, "asset_transfer_dates": ["2026-02-01"]}, TODAY)
    assert not r2.exemptions and not r2.defects and r2.route == "navigator"
    # A notice about income never triggers asset screening
    r3 = rules.evaluate({**notice, "reason": "Income over the limit."}, client, TODAY)
    assert not r3.exemptions and not r3.defects


def test_msp_renewal_short_window_defect():
    r = rules.evaluate({"notice_type": "msp_renewal", "notice_date": "2026-11-04", "stated_due_date": "2026-11-20",
                        "legal_basis_cited": True, "confidence": {}}, {"age": 71}, TODAY)
    assert r.deadline_map()["renewal_response"] == "2026-11-20"
    assert [f.code for f in r.defects] == ["short_renewal_window"]


def test_new_program_cases_run_in_replay_with_no_removed_claims_and_cited_authorities():
    for cid in ("mei", "tomas", "thanh"):
        res = pipeline.run_case(cid)
        assert res["claims"] and not res["removed_claims"], cid
        for c in res["claims"]:
            for a in c["authority_ids"]:
                assert a in pipeline.KB["authorities"], (cid, a)
        assert "{{deadline" not in res["drafts"]["letter"]
    assert "61" in pipeline.RESULTS["tomas"]["drafts"]["letter"] or any("92" in c["text"] for c in pipeline.RESULTS["tomas"]["claims"])


def test_regex_extraction_recognises_the_new_programs():
    assert pipeline._regex_extract("Your IHSS hours change from 92 to 61 effective 2026-12-01")["notice_type"] == "ihss_reduction"
    assert pipeline._regex_extract("NOTICE OF EXPIRATION: your CalFresh certification period ends 12/31/2026")["notice_type"] == "calfresh_recertification"
    assert pipeline._regex_extract("Your CalFresh benefits will be reduced effective 12/01/2026")["notice_type"] == "calfresh_adverse_action"
    assert pipeline._regex_extract("Your Qualified Medicare Beneficiary (QMB) coverage will stop")["notice_type"] == "msp_discontinuance"
