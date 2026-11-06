"""Emergency QR card. Generated only with recorded consent. No member IDs or addresses."""
from __future__ import annotations

import io

import qrcode
import qrcode.image.svg

import vault
from common import AUDIT


class ConsentRequired(Exception):
    pass


def card(pid: str) -> dict:
    p = vault.get(pid)
    if p is None:
        raise KeyError(pid)
    if not p.get("consent"):
        raise ConsentRequired("Record consent before printing an emergency card.")
    em = p["emergency"]
    meds = [f"{m['name']} {m['dose']} ({', '.join(m['times'])})" for m in p["medications"]]
    lines = [
        "CARETHROPIC EMERGENCY INFO",
        f"Name: {p['display_name']}",
        f"Language: {em.get('interpreter') or p['language']} (interpreter needed)",
        f"Allergies: {', '.join(em['allergies']) or 'None listed'}",
        f"Conditions: {', '.join(em['conditions_shared']) or 'None shared'}",
        f"Medicines: {'; '.join(meds) or 'None listed'}",
        *[f"ICE: {c['name']} {c['phone']}" for c in em["contacts"]],
        f"Navigator: {vault.ORG.get('name', '')} {vault.ORG.get('navigator_phone', '')}",
        f"Advance directive: {em.get('advance_directive_location') or 'Not on file'}",
    ]
    payload = "\n".join(lines)
    img = qrcode.make(payload, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    AUDIT.add("emergency_card_issued", {"pid": pid})
    return {"lines": lines, "payload": payload, "qr_svg": buf.getvalue().decode("utf-8"), "consent": p["consent"],
            "language": p["language"], "name": p["display_name"]}
