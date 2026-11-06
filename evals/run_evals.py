"""Kalinga evaluation harness.

Scores the pipeline against labeled synthetic notices on what matters to a
navigator: deadline accuracy, escalation recall, exemption detection, and
citation integrity (zero tolerance for invented authorities or dates).

  python evals/run_evals.py            # replay mode (offline, deterministic)
  python evals/run_evals.py --live     # runs Claude on the notice images
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import pipeline  # noqa: E402
import samples  # noqa: E402

GOLD = json.loads((ROOT / "evals" / "gold.json").read_text())


async def run_case(sid: str, live: bool) -> dict:
    s = samples.SAMPLES[sid]
    case = {"case_id": f"eval-{sid}", "sample_id": sid, "as_of": s["as_of"], "client": s["client"],
            "file_bytes": (ROOT / s["image"]).read_bytes(), "media_type": "image/png", "force_replay": not live}
    result = None
    async for ev in pipeline.run(case):
        if ev["type"] == "result":
            result = ev["data"]
    return result


def score(sid: str, res: dict) -> dict:
    g = GOLD[sid]
    got = {d["rule"]: d["act_by"] for d in res["rules"]["deadlines"]}
    dl_hits = sum(1 for k, v in g["deadlines"].items() if got.get(k) == v)
    flags = {f["code"] for f in res["rules"]["flags"]}
    ex = {e["code"] for e in res["rules"]["exemptions"]}
    bad_cites = sum(1 for c in res["claims"] for a in c["authority_ids"] if a not in res["rules"]["authority_ids"])
    return {
        "case": sid,
        "deadline_accuracy": f"{dl_hits}/{len(g['deadlines'])}",
        "escalation_correct": res["rules"]["review_status"] == g["review_status"],
        "required_flags_found": sorted(set(g["flags"]) & flags) == sorted(g["flags"]),
        "exemptions_correct": ex == set(g["exemptions"]),
        "invented_citations": bad_cites,
        "claims_kept": len(res["claims"]),
        "claims_removed": len(res["dropped_claims"]),
    }


async def main():
    live = "--live" in sys.argv
    rows = [score(sid, await run_case(sid, live)) for sid in GOLD]
    print(json.dumps(rows, indent=2))
    ok = all(r["escalation_correct"] and r["required_flags_found"] and r["exemptions_correct"] and r["invented_citations"] == 0 for r in rows)
    print("\nPASS" if ok else "\nFAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
