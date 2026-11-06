"""Voice briefing: a short spoken summary of one person's day, composed in code from her record.

Nothing here comes from a model. Every sentence is a fixed template in her language filled from
record items the vault selected, and the response lists the record IDs it drew on so the UI can
show (and a test can check) where each sentence came from. The frontend reads the text aloud
with the browser's speech synthesis; a pilot can swap in recorded prompts per language without
changing this module.
"""
from __future__ import annotations

import re
from datetime import datetime

import vault
from common import load, now

I18N = load("i18n.json")
BCP47 = {"tl": "fil-PH", "zh-Hant": "zh-HK", "vi": "vi-VN", "ko": "ko-KR", "hi": "hi-IN", "es": "es-US", "en": "en-US"}


def _join(items: list[str], lang: str) -> str:
    sep = I18N["voice"].get(lang, I18N["voice"]["en"])["list_sep"]
    return sep.join(items)


def compose(p: dict, lang: str, at: datetime | None = None) -> dict:
    at = at or now()
    V = I18N["voice"].get(lang, I18N["voice"]["en"])
    st = vault.status(p, at)
    d = at.date().isoformat()
    parts, cited = [], []

    given = re.sub(r"\s+[A-Z]\.$", "", p["display_name"].split(" (")[0])   # "Wai Ling C." -> "Wai Ling"
    parts.append(V["greeting"].format(name=given, date=d))
    tracked = st["level"] != "none"          # check-ins and medicine confirmations are set up only for people who live alone
    if tracked:
        parts.append(V["status_" + st["level"]])
        due = [i for i in st["items"] if i["kind"] == "med" and i["state"] in ("late", "missed")]
        taken = [i for i in st["items"] if i["kind"] == "med" and i["state"] == "taken"]
        if due:
            names = [f"{i['name']} ({i['due']})" for i in due]
            parts.append(V["meds_due"].format(n=len(due), list=_join(names, lang)))
            cited += sorted({i["item_id"] for i in due})
        elif p["medications"]:
            parts.append(V["meds_clear"])
            cited += sorted({i["item_id"] for i in taken})

    upcoming = sorted((e for e in p["events"] if e["date"] >= d), key=lambda e: (e["date"], e.get("time", "")))
    if upcoming:
        e = upcoming[0]
        title = (e.get("title_local") or {}).get(lang) or e["title"]
        key = "deadline" if e["type"] == "deadline" else "appointment"
        parts.append(V[key].format(title=title, date=e["date"], time=e.get("time", "")).replace("  ", " ").strip())
        cited.append(e["id"])

    parts.append(V["prompt_ok"] if tracked else V["prompt_ask"])
    return {"lang": lang, "bcp47": BCP47.get(lang, "en-US"), "text": V.get("sentence_sep", " ").join(parts), "sentences": parts,
            "cited_record_ids": cited, "status": st["level"], "as_of": at.isoformat(timespec="minutes")}


def feedback(kind: str, lang: str, **kw) -> str:
    """Short spoken confirmation after a tap: 'Noted. Metformin taken at 8:05.'"""
    V = I18N["voice"].get(lang, I18N["voice"]["en"])
    return V["fb_" + kind].format(**kw)
