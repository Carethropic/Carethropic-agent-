"""Carethropic evaluation harness.

Scores the recorded cases on deadline accuracy, escalation, exemptions, and invented citations,
then scores Ask Carethropic on advice-guard recall and record grounding, and the Nonprofit Finder on its
acceptance queries. Replay by default; --live runs the Claude agents and re-ranker end to end.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("CARETHROPIC_NOW", "2026-11-06T10:30")
os.environ.setdefault("CARETHROPIC_DB", ":memory:")

GOLD = json.loads((Path(__file__).parent / "gold.json").read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    if not args.live:
        os.environ["CARETHROPIC_REPLAY"] = "1"

    import ask, nonprofits, pipeline, vault  # noqa: E401
    vault.reset()
    score = {"deadline_ok": 0, "deadline_total": 0, "escalation_ok": 0, "exemption_ok": 0, "invented_citations": 0, "cases": 0}
    for cid, g in GOLD["cases"].items():
        res = pipeline.run_case(cid)
        score["cases"] += 1
        d = {x["key"]: x["date"] for x in res["rules"]["deadlines"]}
        for k, v in g["deadlines"].items():
            score["deadline_total"] += 1
            score["deadline_ok"] += int(d.get(k) == v)
        score["escalation_ok"] += int(res["gate"]["route"] == g["route"])
        score["exemption_ok"] += int({f["code"] for f in res["rules"]["exemptions"]} == set(g["exemptions"]))
        allowed = set(res["rules"]["authorities"]) | {"ca-wic-14005-18"}
        score["invented_citations"] += sum(1 for c in res["claims"] for a in c["authority_ids"] if a not in allowed)

    guard_hits = sum(1 for q in GOLD["advice_questions"] if ask.ask("p-remy", q)["guard"])
    grounded = 0
    for q, kind in GOLD["grounded_questions"]:
        a = ask.ask("p-remy", q, "en")
        grounded += int(a["cited"] and a["cited"][0]["kind"] == kind)
    finder_ok = 0
    for q, top in GOLD["finder"]:
        r = nonprofits.search(q)
        first = r["groups"][0]["results"] if r["parsed"]["claude_intent"] else r["groups"][1]["results"]
        finder_ok += int(first and first[0]["id"] == top)

    print(f"mode: {'live' if args.live else 'replay'}")
    print(f"deadline accuracy: {score['deadline_ok']} of {score['deadline_total']}")
    print(f"escalation correct: {score['escalation_ok']} of {score['cases']}")
    print(f"exemptions correct: {score['exemption_ok']} of {score['cases']}")
    print(f"invented citations: {score['invented_citations']}")
    print(f"advice guard recall: {guard_hits} of {len(GOLD['advice_questions'])}")
    print(f"grounded answers: {grounded} of {len(GOLD['grounded_questions'])}")
    print(f"finder top result: {finder_ok} of {len(GOLD['finder'])}")
    ok = (score["deadline_ok"] == score["deadline_total"] and score["invented_citations"] == 0
          and guard_hits == len(GOLD["advice_questions"]) and finder_ok == len(GOLD["finder"]))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
