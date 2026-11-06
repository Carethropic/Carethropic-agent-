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

**For navigators (the notice decoder).** Snap a photo of a Medi-Cal notice. Claude extracts the fields with confidence scores. A tested Python rules engine computes every deadline (hearing, aid paid pending, 30-day work rule response, 90-day reconsideration), finds notice defects, and screens for work rule exemptions. Two agents draft in parallel, a verifier removes any claim that cites outside the knowledge base or states a date the engine did not compute, and nothing leaves without a navigator's approval. New in v2: **Save to record** turns each deadline into a dated, cited entry in the person's Carethropic record, with titles in her language.

**For elders who live alone (new).** The **Carethropic record** holds her medicines, appointments and deadlines, coverage, and emergency information, in large type and in her language (Tagalog, Traditional Chinese, Vietnamese, Korean, Hindi, Spanish, English). She taps *I'm OK today* and taps each medicine as taken. **Ask Carethropic** answers questions like *Did I take my blood pressure pill?* only from her own record, cites the entry it used, and refuses to give dosing advice. Missed check-ins flag on the navigator console. A consented **emergency QR card** gives EMTs her allergies, medicines, language, and contacts, with no member IDs or addresses.

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
python -m pytest -q tests        # 31 tests: rules, rollback, exemptions, verifier, status, Ask Carethropic guard, consent, finder, API, env fallback, persistence
python evals/run_evals.py        # replay
python evals/run_evals.py --live # Claude agents and re-ranker end to end
```

Current replay results: deadline accuracy 8 of 8, escalation correct 5 of 5, exemptions correct 5 of 5, invented citations 0, advice guard recall 9 of 9, grounded answers 6 of 6, finder top result 5 of 5.

## Architecture

```
frontend/            static HTML, CSS, JS (no build step)
backend/app.py       FastAPI
  rules.py           deadlines, rollback, defects, exemptions, escalation
  pipeline.py        extract → rules → agents ∥ → verifier → drafts → human gate → save to record
  vault.py           Carethropic record, check-ins, status, consent
  store.py           SQLite persistence for records, case results and the audit chain
  ask.py             Ask Carethropic: guard → retrieval → Claude (forced schema) → verifier → template fallback
  nonprofits.py      finder: parser, scorer, grouping, Claude re-rank (closed world)
  emergency.py       consent-gated QR card
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

## Builder

Angelina Cayabyab: former air district permit engineer, JD candidate at Santa Clara Law (Tech Edge), Georgia Tech OMSCS (AI), and AI governance founder. Previously built GreenGuard at Cal Hacks.
Yitian Liu

## License

MIT
