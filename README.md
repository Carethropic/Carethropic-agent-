# Carethropic

**Care that remembers.** One trusted care record for the Asian American women and elders that Bay Area nonprofit navigators serve, so a confusing Medi-Cal notice or a forgotten pill never costs someone her coverage or her safety.

Kalinga is Tagalog for care. Built for **Code with Claude: Women in AI Hackathon** (Women's Health track), with a planned pilot at Filipino Advocates for Justice in the Bay Area. Full product spec: [SPEC.md](SPEC.md).

## The problem, in numbers

Computed from DHCS Medi-Cal open data for October 2026 (nine Bay Area counties):

| | |
| --- | --- |
| **361,443** | Asian Medi-Cal members in the Bay Area, about 19% of all members here |
| **125,706** | of them are 65 or older (35%); in San Francisco it is 42% |
| **60%** | of Bay Area Medi-Cal members 65+ are women |
| **183,000** | members whose primary language is Chinese, Vietnamese, Tagalog, Korean, Hindi, or Punjabi |

Starting January 1, 2027, new federal work reporting rules and six-month renewals will send these members more notices than ever, in English first. Statewide, only 30% of Korean American elders and 57% of Chinese American elders say they get the social and emotional support they need (UCLA, 2018 CHIS). The **Why Kin** page in the app lists every source.

## What Kin does

**For navigators (the existing Kalinga decoder, kept and extended).** Snap a photo of a Medi-Cal notice. Claude extracts the fields with confidence scores. A tested Python rules engine computes every deadline (hearing, aid paid pending, 30-day work rule response, 90-day reconsideration), finds notice defects, and screens for work rule exemptions. Two agents draft in parallel, a verifier removes any claim that cites outside the knowledge base or states a date the engine did not compute, and nothing leaves without a navigator's approval. New in v2: **Save to record** turns each deadline into a dated, cited entry in the person's Kin record, with titles in her language.

**For elders who live alone (new).** The **Kin record** holds her medicines, appointments and deadlines, coverage, and emergency information, in large type and in her language (Tagalog, Traditional Chinese, Vietnamese, Korean, Hindi, Spanish, English). She taps *I'm OK today* and taps each medicine as taken. **Ask Kin** answers questions like *Did I take my blood pressure pill?* only from her own record, cites the entry it used, and refuses to give dosing advice. Missed check-ins flag on the navigator console. A consented **emergency QR card** gives EMTs her allergies, medicines, language, and contacts, with no member IDs or addresses.

**For nonprofits (new).** The **Nonprofit finder** searches a curated, versioned directory of Claude for Nonprofits partners and Bay Area organizations serving Asian American women and elders. Code parses the place and intent; Claude only re-ranks and explains fit within the candidate set.

## Why it is hard to replicate

| Layer | What makes it different |
| --- | --- |
| Deterministic core | Deadlines, check-in status, and search filters are computed in tested Python. The model never does date math. |
| Closed-world everything | Agents cite only authority IDs the rules engine selected. Ask Kin cites only record IDs the retriever selected. The finder re-ranks only directory IDs. |
| Two-stage verification | Hard checks in code (citations, dates, times, IDs), then a template fallback when the model answer fails. Removed claims are shown, never hidden. |
| Medical advice guard | Dose-change questions in seven languages never reach the model. |
| Honest memory | "Did I take it?" is answered only from her confirmation log. No confirmation means Kin says so and points to the pharmacist. |
| Consent and privacy | Emergency cards print only after recorded consent. IDs are masked. Pasted text is scrubbed. The audit chain stores hashes only. |
| Replay mode | Every feature runs without an API key through the same verifiers, so the demo never depends on the network. |
| Evaluation harness | Labeled cases scored on deadline accuracy, escalation, exemptions, invented citations, advice-guard recall, grounding, and finder accuracy. |

## Quick start

```bash
pip install -r requirements.txt
cd backend
export ANTHROPIC_API_KEY=sk-ant-...   # optional; without it, everything runs in replay mode
uvicorn app:app --port 8000
# open http://localhost:8000
```

Optional: `KALINGA_MODEL` (default `claude-sonnet-4-5`), `KALINGA_FAST_MODEL` for the re-ranker and verifier, `KALINGA_NOW=2026-11-06T10:30` to pin the clock for rehearsals, `KALINGA_REPLAY=1` to force replay mode.

Docker: `docker build -t kin . && docker run -p 8000:8000 -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY kin`

## Tests and evals

```bash
python -m pytest -q tests        # 27 tests: rules, rollback, exemptions, verifier, status, Ask Kin guard, consent, finder, API
python evals/run_evals.py        # replay
python evals/run_evals.py --live # Claude agents and re-ranker end to end
```

Current replay results: deadline accuracy 8 of 8, escalation correct 5 of 5, exemptions correct 5 of 5, invented citations 0, advice guard recall 9 of 9, grounded answers 6 of 6, finder top result 5 of 5.

## Demo cases (synthetic)

| Person | Track | What Kin catches |
| --- | --- | --- |
| Ligaya R., 24 weeks pregnant, Tagalog | Discontinuance | Coverage ends in 3 days. Act today. 7-day advance notice defect. Attorney review. |
| Rosa D., 3 months postpartum, Tagalog | 2027 work rule notice | Exempt twice over (postpartum, child under 14). Draft claims both. |
| Carmen F., caregiver, Spanish | Renewal documents | Notice gives 21 days; federal rules require 30. |
| Wai Ling C., 82, lives alone, Cantonese | Annual renewal (Medi-Medi) | Deadline saved to her record; she can ask Kin for it in Chinese. |
| Hoa N., 74, lives alone, Vietnamese | Medi-Cal ended | 90-day reconsideration window, missing legal basis, low-confidence date. Attorney review. |
| Lola Remy, 78, lives alone, Tagalog | Daily check-ins | Two days without a check-in. Ask Kin: "take two pills?" gets the advice guard. |
| Kamala P., 76, lives alone, Hindi | Daily check-ins | All medicines confirmed. Emergency QR card after consent. |

All names, agencies, phone numbers, and case numbers are fictional.

## Demo script (3 minutes)

1. **Hook (15s).** "One Bay Area navigator serves a pregnant mother on Medi-Cal and an 82-year-old grandmother who lives alone. Both can lose care to one missed date."
2. **Ligaya (40s).** Decode her discontinuance notice. Show Act today, the 7-day defect, attorney routing. Hover a citation.
3. **Wai Ling (45s).** Decode her renewal, click *Save deadlines to Kin record*. Open her record in Traditional Chinese. Ask "When is my Medi-Cal deadline?" and show the cited date.
4. **Lola Remy (40s).** Console shows her missed check-in. Open her record in Tagalog. Ask "Should I take two pills since I forgot?" Kin answers kindly, cites her medicine entry, and points to the pharmacist. Record consent and print her emergency card.
5. **Finder (20s).** Search "Claude Non-profit sponsors in san francisco." Tipping Point and Taproot appear first, then Self-Help for the Elderly, Kimochi, and API Legal Outreach.
6. **Close (10s).** "Kin: every deadline caught, every answer cited, every record kept with care."

## Architecture

```
frontend/            static HTML, CSS, JS (no build step)
backend/app.py       FastAPI
  rules.py           deadlines, rollback, defects, exemptions, escalation
  pipeline.py        extract → rules → agents ∥ → verifier → drafts → human gate → save to record
  vault.py           Kin record, check-ins, status, consent
  ask.py             Ask Kin: guard → retrieval → Claude (forced schema) → verifier → template fallback
  nonprofits.py      finder: parser, scorer, grouping, Claude re-rank (closed world)
  emergency.py       consent-gated QR card
  llm.py             Claude client with forced tool schemas and replay fallback
  common.py          clock, scrubbing, masking, SHA-256 audit chain
  data/              kb.json, cases.json, people.json, nonprofits.json, i18n.json, insights.json
tests/               pytest suite
evals/               gold labels and harness
```

## Privacy and safety

- Built for trained navigators, with a human approving every output. Kin provides legal and health information, which is different from legal or medical advice.
- Demo data is synthetic. Production would encrypt records at rest on a nonprofit-controlled account. Anthropic does not train on nonprofit customer data by default.
- Translations are drafts for the hackathon and will be reviewed by community members before the pilot.

## Roadmap

1. Pilot with Filipino Advocates for Justice, then Self-Help for the Elderly, AACI, and HICAP programs.
2. Add CalFresh, IHSS, and Medicare Savings Program notices.
3. Voice-first elder mode with recorded prompts in each language.
4. Optional, consented family digest.
5. Package Kin as a Claude for Nonprofits plugin so partner organizations can install it directly.

## Builder

Angelina Cayabyab: former air district permit engineer, JD candidate at Santa Clara Law (Tech Edge), Georgia Tech OMSCS (AI), and AI governance founder. Previously built GreenGuard at Cal Hacks.

## License

MIT
