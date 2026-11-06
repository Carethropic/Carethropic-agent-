# Carethropic

**Care that remembers.** One trusted care record for the Asian American women and elders that Bay Area nonprofit navigators serve, so a confusing Medi-Cal notice or a forgotten pill never costs someone her coverage or her safety.

Carethropic (from *kalinga*, Tagalog for care) was built for **Code with Claude: Women in AI Hackathon** (Women's Health track), with a planned pilot at Filipino Advocates for Justice in the Bay Area. Full product spec: [SPEC.md](SPEC.md).

## The problem, in numbers

Computed from DHCS Medi-Cal open data for October 2026 (nine Bay Area counties):

| | |
| --- | --- |
| **361,443** | Asian Medi-Cal members in the Bay Area, about 19% of all members here |
| **125,706** | of them are 65 or older (35%); in San Francisco it is 42% |
| **60%** | of Bay Area Medi-Cal members 65+ are women |
| **183,000** | members whose primary language is Chinese, Vietnamese, Tagalog, Korean, Hindi, or Punjabi |

Starting January 1, 2027, new federal work reporting rules and six-month renewals will send these members more notices than ever, in English first. Statewide, only 30% of Korean American elders and 57% of Chinese American elders say they get the social and emotional support they need (UCLA, 2018 CHIS). The **Why Carethropic** page in the app lists every source.

## What Carethropic does

**For navigators (the notice decoder).** Snap a photo of a Medi-Cal, CalFresh, IHSS, or Medicare Savings Program notice. Claude extracts the fields with confidence scores. A tested Python rules engine computes every deadline (hearing, aid paid pending, 30-day work rule response, 90-day reconsideration), finds notice defects, and screens for work rule exemptions. Two agents draft in parallel, a verifier removes any claim that cites outside the knowledge base or states a date the engine did not compute, and nothing leaves without a navigator's approval. New in v2: **Save to record** turns each deadline into a dated, cited entry in the person's Carethropic record, with titles in her language.

**For elders who live alone (new).** The **Carethropic record** holds her medicines, appointments and deadlines, coverage, and emergency information, in large type and in her language (Tagalog, Traditional Chinese, Vietnamese, Korean, Hindi, Spanish, English). She taps *I'm OK today* and taps each medicine as taken. With **voice on**, Carethropic reads her a short daily briefing in her language (composed in code from her record, with the record items it used), confirms every tap aloud, and she can ask by voice with one large button; the preference sticks to her tablet. **Ask Carethropic** answers questions like *Did I take my blood pressure pill?* only from her own record, cites the entry it used, and refuses to give dosing advice. Missed check-ins flag on the navigator console. A consented **emergency QR card** gives EMTs her allergies, medicines, language, and contacts, with no member IDs or addresses.

**For nonprofits (new).** The **Nonprofit finder** searches a curated, versioned directory of Claude for Nonprofits partners and Bay Area organizations serving Asian American women and elders. Code parses the place and intent; Claude only re-ranks and explains fit within the candidate set.

## Why it is hard to replicate

| Layer | What makes it different |
| --- | --- |
| Deterministic core | Deadlines, check-in status, and search filters are computed in tested Python. The model never does date math. |
| Closed-world everything | Agents cite only authority IDs the rules engine selected. Ask Carethropic cites only record IDs the retriever selected. The finder re-ranks only directory IDs. |
| Two-stage verification | Hard checks in code (citations, dates, times, IDs), then a template fallback when the model answer fails. Removed claims are shown, never hidden. |
| Medical advice guard | Dose-change questions in seven languages never reach the model. |
| Honest memory | "Did I take it?" is answered only from her confirmation log. No confirmation means Carethropic says so and points to the pharmacist. |
| Consent and privacy | Emergency cards print only after recorded consent. IDs are masked. Pasted text is scrubbed. The audit chain stores hashes only. |
| Replay mode | Every feature runs without an API key through the same verifiers, so the demo never depends on the network. |
| Voice without a model | The daily briefing and every spoken confirmation are fixed templates filled from her record, so what she hears is exactly what her record says. Browser speech only; nothing spoken reaches a model. |
| Durable records | Records, check-ins, consents, decoded notices and the audit chain live in SQLite and survive a restart. *Reset demo* reseeds from JSON. |
| Evaluation harness | Labeled cases scored on deadline accuracy, escalation, exemptions, invented citations, advice-guard recall, grounding, and finder accuracy. |

## Quick start

```bash
pip install -r requirements.txt
cd backend
export ANTHROPIC_API_KEY=sk-ant-...   # optional; without it, everything runs in replay mode
uvicorn app:app --port 8000
# open http://localhost:8000
```

Optional: `CARETHROPIC_MODEL` (default `claude-sonnet-4-5`), `CARETHROPIC_FAST_MODEL` for the re-ranker and verifier, `CARETHROPIC_NOW=2026-11-06T10:30` to pin the clock for rehearsals, `CARETHROPIC_REPLAY=1` to force replay mode, `CARETHROPIC_DB` to choose the SQLite file (default `backend/carethropic.db`; `:memory:` for tests). The older `KALINGA_*` names still work.

Docker: `docker build -t carethropic . && docker run -p 8000:8000 -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY carethropic`

## Tests and evals

```bash
python -m pytest -q tests        # 40 tests: rules for four programs, rollback, exemptions, verifier, status, Ask Carethropic guard, consent, finder, API, env fallback, persistence, voice briefing
python evals/run_evals.py        # replay
python evals/run_evals.py --live # Claude agents and re-ranker end to end
```

Current replay results: deadline accuracy 16 of 16, escalation correct 8 of 8, exemptions correct 8 of 8, invented citations 0, advice guard recall 9 of 9, grounded answers 6 of 6, finder top result 5 of 5.

## Demo cases (synthetic)

| Person | Track | What Carethropic catches |
| --- | --- | --- |
| Ligaya R., 24 weeks pregnant, Tagalog | Discontinuance | Coverage ends in 3 days. Act today. 7-day advance notice defect. Attorney review. |
| Rosa D., 3 months postpartum, Tagalog | 2027 work rule notice | Exempt twice over (postpartum, child under 14). Draft claims both. |
| Carmen F., caregiver, Spanish | Renewal documents | Notice gives 21 days; federal rules require 30. |
| Wai Ling C., 82, lives alone, Cantonese | Annual renewal (Medi-Medi) | Deadline saved to her record; she can ask Carethropic for it in Chinese. |
| Hoa N., 74, lives alone, Vietnamese | Medi-Cal ended | 90-day reconsideration window, missing legal basis, low-confidence date. Attorney review. |
| Lola Remy, 78, lives alone, Tagalog | Daily check-ins | Two days without a check-in. Ask Carethropic: "take two pills?" gets the advice guard. |
| Kamala P., 76, lives alone, Hindi | Daily check-ins | All medicines confirmed. Emergency QR card after consent. |
| Mei F., 68, lives alone, Cantonese | CalFresh recertification | File by the 15th of the last month; a late filing still counts for 30 days. |
| Tomas B., 81, lives alone, Tagalog | IHSS hours cut 92 → 61 | Aid paid pending if the hearing is requested before Dec 1; 180-day good-cause limit. |
| Thanh L., 71, lives alone, Vietnamese | Medicare Savings Program ending for assets | Under the reinstated 2026 asset limit once the IRA in payout is excluded; the 2025 transfer may not be counted. Attorney review. |

All names, agencies, phone numbers, and case numbers are fictional.

## Demo script (3 minutes)

1. **Hook (15s).** "One Bay Area navigator serves a pregnant mother on Medi-Cal and an 82-year-old grandmother who lives alone. Both can lose care to one missed date."
2. **Ligaya (40s).** Decode her discontinuance notice. Show Act today, the 7-day defect, attorney routing. Hover a citation.
3. **Wai Ling (45s).** Decode her renewal, click *Save deadlines to Carethropic record*. Open her record in Traditional Chinese. Ask "When is my Medi-Cal deadline?" and show the cited date.
4. **Lola Remy (40s).** Console shows her missed check-in. Open her record in Tagalog. Ask "Should I take two pills since I forgot?" Carethropic answers kindly, cites her medicine entry, and points to the pharmacist. Record consent and print her emergency card.
5. **Finder (20s).** Search "Claude nonprofit sponsors in San Francisco." Tipping Point and Taproot appear first, then Self-Help for the Elderly, Kimochi, and API Legal Outreach.
6. **Close (10s).** "Carethropic: every deadline caught, every answer cited, every record kept with care."

## Architecture

```
frontend/            static HTML, CSS, JS (no build step); voice.js wraps browser speech
backend/app.py       FastAPI
  rules.py           deadlines, rollback, defects, exemptions, escalation
  pipeline.py        extract → rules → agents ∥ → verifier → drafts → human gate → save to record
  vault.py           Carethropic record, check-ins, status, consent
  store.py           SQLite persistence for records, case results and the audit chain
  ask.py             Ask Carethropic: guard → retrieval → Claude (forced schema) → verifier → template fallback
  nonprofits.py      finder: parser, scorer, grouping, Claude re-rank (closed world)
  emergency.py       consent-gated QR card
  briefing.py        spoken daily briefing and tap confirmations, composed in code per language
  llm.py             Claude client with forced tool schemas and replay fallback
  common.py          clock, env, scrubbing, masking, SHA-256 audit chain
  data/              kb.json, cases.json, people.json, nonprofits.json, i18n.json, insights.json
tests/               pytest suite
evals/               gold labels and harness
.github/workflows/   CI: tests and evals on every push
```

## Privacy and safety

- Built for trained navigators, with a human approving every output. Carethropic provides legal and health information, which is different from legal or medical advice.
- Demo data is synthetic. Records are stored in a local SQLite file; production would encrypt it at rest on a nonprofit-controlled account. Anthropic does not train on nonprofit customer data by default.
- Translations are drafts for the hackathon and will be reviewed by community members before the pilot.

## Programs covered

| Program | Notice types | Rules encoded |
| --- | --- | --- |
| Medi-Cal | discontinuance, work rule noncompliance, renewal documents, annual renewal, termination for no renewal | 10-day advance notice, 90-day hearing, aid paid pending, 30-day renewal window, 90-day reconsideration, 2027 work rule exemptions |
| CalFresh | adverse action, recertification | 10-day advance notice, 90-day hearing, continued benefits, notice of expiration timing, timely (15th) and late (30-day) recertification |
| IHSS | reduction, termination | 10-day timely notice, adequate notice, 90-day hearing with 180-day good-cause limit, aid paid pending, annual reassessment |
| Medicare Savings Programs (QMB, SLMB, QI) | discontinuance, renewal | Medi-Cal notice rules plus the asset limit reinstated January 1, 2026 ($130,000 + $65,000 per additional person), exempt assets, and the 2024–2025 transfer safe harbor |

## Roadmap

1. Pilot with Filipino Advocates for Justice, then Self-Help for the Elderly, AACI, and HICAP programs.
2. CalWORKs and SSI/SSP notices.
3. Recorded prompts per language to replace browser speech synthesis in voice mode.
4. Optional, consented family digest.
5. Package Carethropic as a Claude for Nonprofits plugin so partner organizations can install it directly.

## Builder

Angelina Cayabyab: former air district permit engineer, JD candidate at Santa Clara Law (Tech Edge), Georgia Tech OMSCS (AI), and AI governance founder. Previously built GreenGuard at Cal Hacks.

## License

MIT
