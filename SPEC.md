# Carethropic: Product Spec

Version 2.2 · November 6, 2026 · Code with Claude: Women in AI Hackathon (Women's Health track)

Kalinga is Tagalog for care. Version 1 (Kalinga) decoded Medi-Cal notices for navigators. Version 2 keeps that core and extends it to a second group the same navigators already serve: Asian American elders in the Bay Area, especially women who live alone.

**Name.** The product is **Carethropic**: care, built with Anthropic's Claude, for the people nonprofits serve. During the hackathon the elder features were prototyped under the working name *Kin*; that name is retired. *Kalinga* remains the name of the deterministic notice engine (`backend/rules.py`). Tagline: *care that remembers.*

## 1. One sentence

Carethropic gives Bay Area nonprofit navigators one trusted care record for the Asian American women and elders they serve, so a confusing notice or a forgotten pill never costs someone her coverage or her safety.

## 2. Why these two groups belong in one product

I found five points of common ground between the original users (Asian American women on Medi-Cal, many pregnant or postpartum) and the new users (Asian American elders living alone).

| Shared need | Women on Medi-Cal | Elders living alone |
| --- | --- | --- |
| Same coverage risk | Renewal and 2027 work rule notices | Medi-Cal renewals, Medi-Medi (Medicare plus Medi-Cal) notices |
| Same language gap | Tagalog, Chinese, Vietnamese, Korean, Hindi, Spanish | Same languages, often lower English literacy |
| Same helpers | Community navigators at AAPI nonprofits | The same navigators, plus HICAP counselors |
| Same family structure | Women manage coverage for kids and aging parents | Elders rely on a daughter or niece who may live far away |
| Same failure mode | One missed date ends prenatal or postpartum care | One forgotten record (meds, ICE, deadline) causes a crisis |

The product insight: a decoded notice and a medication list are both pieces of a person's care record. Carethropic turns every decoded notice into a dated entry in that record, and the record answers questions when memory fails.

**Evidence (DHCS Medi-Cal open data, October 2026, nine Bay Area counties, computed by Carethropic).** 361,443 Asian Medi-Cal members (about 19% of the region's 1.86 million, double the statewide API share of 9.3%); 125,706 of them are 65+ (35%; 42% in San Francisco); women are 60% of Bay Area members 65+; about 183,000 members list Chinese, Vietnamese, Tagalog, Korean, Hindi, or Punjabi as their primary language. Statewide, 30% of Korean American and 57% of Chinese American elders say they get the social and emotional support they need (UCLA, 2018 CHIS). The **Why Carethropic** page in the app cites every figure.

## 3. Customer and users

**Customer (who adopts and pays).** Bay Area nonprofits and existing Claude for Nonprofits partners. Launch pilot is Filipino Advocates for Justice. Expansion targets include Self-Help for the Elderly, On Lok, Asian Health Services, AACI, Kimochi, India Community Center, and HICAP programs. Claude for Nonprofits discounts (up to 75 percent on Team and Enterprise) make the model cost workable for small organizations.

**Primary users.**

1. **Navigator.** Trained staff at a nonprofit. Sets up the record with the client, decodes notices, reviews flags, approves every output.
2. **Elder or client.** Uses a large-text, language-first view on a tablet during visits or on her own phone. Asks Carethropic questions about her own record.
3. **Trusted contact.** A niece, daughter, or neighbor listed as ICE. Receives nothing automatically in the demo. Escalation stays with the navigator.

## 4. Product surfaces

### 4.1 Navigator Console (home)

A caseload view for one nonprofit. Each row shows a person, language, city, the next computed deadline, and flags.

Flags, in priority order:

1. **Act today.** A computed deadline is today or past, or coverage ends within 3 days.
2. **Attorney review.** Notice defect, low-confidence extraction, or pregnancy plus loss of coverage.
3. **Missed check-in.** An elder living alone has not confirmed a daily check-in or a scheduled medication within the grace window.
4. **Upcoming.** A deadline or appointment within 14 days.

### 4.2 Notice Decoder (existing, kept)

Pipeline per notice: extract (Claude vision or pasted text) → rules engine (deadlines, defects, exemptions) → Rights Agent and Health Navigator in parallel → Citation Verifier → plain-language explanation and draft reply → human gate. Version 2 adds one step at the end: **Save to record**, which writes each computed deadline into the person's vault as a dated, cited entry.

### 4.3 Carethropic Record (new)

The record holds four sections, each item with an ID, a source, and an updated date.

- **Medications.** Name, dose, schedule times, prescriber, pharmacy, refill date, purpose in plain words.
- **Appointments and deadlines.** Doctor visits plus deadlines saved from decoded notices.
- **Coverage.** Medi-Cal, Medicare, Medi-Medi status, plan name, masked member ID.
- **Emergency (ICE).** Contacts, allergies, conditions as she states them, preferred language, interpreter need, where her advance directive is kept.

Elder view rules: base font 22px, one action per screen area, icons plus words, full UI in the selected language (English, Tagalog, Traditional Chinese, Vietnamese, Korean, Hindi, Spanish), browser voice input and read-aloud, and a single "Call my navigator" button that is always visible.

### 4.4 Ask Carethropic (new)

The elder or navigator asks a question by typing or with the browser microphone. Examples: "Did I take my blood pressure pill today?", "When is my Medi-Cal deadline?", "Who is my emergency contact?"

How it stays safe:

1. **Closed-world retrieval in code.** The server selects candidate record items by keyword and synonym match across all seven languages. The model only sees those items.
2. **Forced tool schema.** Claude must return `answer`, `cited_record_ids`, `category`, and `needs_human`.
3. **Verifier.** Any cited ID outside the candidate set, or any date that does not appear in a cited record, removes the claim. If nothing survives, the answer becomes the safe fallback.
4. **Medical advice guard.** Questions about changing, doubling, skipping, or mixing doses, in any of the seven languages, get a fixed, kind reply that points to the pharmacist and navigator, plus the facts from her record. Carethropic never says whether to take a dose.
5. **Check-in honesty.** "Did I take it?" is answered only from her confirmation log. If there is no confirmation, Carethropic says it has no record of it and suggests calling the pharmacist before taking another dose.
6. **Replay mode.** Without an API key, the same retrieval, guard, and verifier run, and a template answer is built from the cited records. The demo never depends on network access.

### 4.5 Daily check-in and missed check-in flag (new)

The elder taps "I'm OK today" and taps each scheduled medication as taken. The server computes a status per person:

- `ok` when the daily check-in and all due meds are confirmed.
- `late` when something is due but still inside the grace window (default 2 hours).
- `missed` when the grace window has passed. The navigator console raises a flag.
- `missed_2_days` when no daily check-in for two calendar days. Escalates to "Act today" with a suggested call script to her ICE contact.

The demo sends no SMS or calls. The navigator decides.

### 4.6 Emergency QR card (new)

A printable wallet card in English plus her language. The QR code encodes a short plain-text summary (name, language, allergies, conditions she chose to share, medications, ICE contacts). Rules:

- The card is generated only after the consent box is checked and the navigator records who gave consent and when.
- Member IDs and addresses never go on the card.
- The consent event is hashed into the audit chain.
- Revoking consent blocks the card endpoint.

### 4.7 Nonprofit Finder (new)

A search over a curated, versioned directory of two lists:

1. **Claude for Nonprofits partners.** Organizations named by Anthropic as platform partners, training partners, pilot partners, design partners, or Claude Corps partners. Each entry stores its role and the source URL.
2. **Bay Area nonprofits** serving Asian American women, families, and elders (Filipino, Chinese, Vietnamese, Korean, South Asian). Each entry stores city, counties served, languages, services, and populations.

Search behavior:

1. Parse the query in code: detect a place (city, county, or "Bay Area"), detect Claude partner intent ("claude", "anthropic", "sponsor", "partner"), detect service and language terms.
2. Filter and score in code. Place match, intent match, and keyword match each add points.
3. Results come back in two groups: **Claude for Nonprofits partners** that match, then **Bay Area nonprofits** that continue the search for the same place. If the first group is empty for a city, the second group still answers.
4. With an API key, Claude re-ranks the candidates and writes one "why this fits" line each. It may only reference candidate IDs. Without a key, a template line is used.
5. Every result shows its source link and the directory version date.

Acceptance test: the query **"Claude nonprofit sponsors in San Francisco"** must return San Francisco Claude partners first (Tipping Point Community, Taproot Foundation), then nationwide Claude partners, then San Francisco nonprofits serving AAPI women and elders (Self-Help for the Elderly, On Lok, API Legal Outreach, Kimochi, and more). Verified in pytest, in the eval harness, and in a browser run.

## 5. Architecture

```
frontend/ (static HTML, CSS, JS, no build step)
   │
backend/app.py (FastAPI)
   ├── rules.py        deadlines, weekend rollback, defects, exemptions
   ├── pipeline.py     notice pipeline, agents, human gate, save to record
   ├── vault.py        Carethropic Record store, check-ins, status
   ├── ask.py          retrieval, advice guard, Claude call, verifier (Ask Carethropic)
   ├── nonprofits.py   query parser, scorer, grouping, re-rank
   ├── emergency.py    consent and QR card
   ├── audit.py        SHA-256 hash chain, hashes only
   ├── llm.py          Claude client with forced tool schemas, replay fallback
   ├── privacy.py      scrubbing and masking
   └── data/           kb.json, cases.json, people.json, nonprofits.json, i18n.json, insights.json
```

Every Claude call uses a forced tool schema. Date math, deadline logic, status computation, and search filtering live in tested Python.

## 6. Data model (abridged)

```json
{
  "person": {"id": "p-remy", "display_name": "Remedios S.", "language": "tl", "city": "Daly City", "lives_alone": true, "segment": "elder"},
  "medication": {"id": "med-1", "name": "Amlodipine", "dose": "5 mg", "times": ["08:00"], "purpose": "blood pressure", "source": "Pharmacy label, verified by navigator"},
  "event": {"id": "evt-1", "type": "deadline", "date": "2026-11-20", "title": "Return Medi-Cal renewal form", "source": "case:wai-ling", "authority": "fed-435-916"},
  "checkin": {"person_id": "p-remy", "date": "2026-11-06", "type": "med", "item_id": "med-1", "time": "08:12"},
  "consent": {"person_id": "p-remy", "scope": "emergency_card", "given_by": "self", "recorded_by": "navigator", "at": "2026-11-06T10:00:00"}
}
```

## 7. Edge cases and how Carethropic handles them

| Case | Handling |
| --- | --- |
| Deadline lands on a weekend or holiday | Roll back to the prior business day (Friday). Holidays from a fixed California list. |
| Notice date missing or unreadable | Confidence below 0.7 marks the field, blocks auto-deadlines, and routes to attorney review. |
| Elder asks about a dose change | Advice guard reply, record facts only, pharmacist and navigator prompt. |
| Elder asks something not in her record | "I don't see that in your record yet. Your navigator can add it." No model guess. |
| Question in mixed language (Taglish, Hinglish, Chinese plus English) | Synonym table covers each language; retrieval matches any. |
| Duplicate medication entries | Vault warns on same name with different dose and asks the navigator to confirm. |
| Two elders share a name | IDs drive everything; display names are never used as keys. |
| Clock skew or late-night check-in | Server time in America/Los_Angeles decides status. |
| Consent withdrawn | Card endpoint returns 403 and the UI explains how to renew consent. |
| ICE contact missing | Card still generates with "Ask for interpreter" and the nonprofit's number. |
| Nonprofit search with no place | Rank across all Bay Area entries and Claude partners. |
| Nonprofit search with a city outside the directory (Fresno, Los Angeles) | Return the Bay Area list with a note that the directory is still growing. |
| Query with typos ("san fransisco", "non-profit") | Normalization and alias table. |
| No API key or network outage | Replay mode for every feature, same verifier. |
| Prompt injection inside a notice, a question, or a directory entry | Text is data. Tool schemas cannot call actions. Verifier blocks unknown IDs. |
| Missing legal basis on a termination or work rule notice | Flagged as a defect (42 C.F.R. § 431.210) and routed to attorney review, the same as a discontinuance. |

## 8. Privacy and safety

- Synthetic data only in the demo. Production would encrypt the record at rest and run on a nonprofit-controlled account.
- Member and case IDs are masked in every output. Pasted text is scrubbed for SSNs, phone numbers, and emails before the model sees it.
- The audit chain stores hashes only. Approvals, consents, and check-ins are chained.
- Carethropic provides legal and health information, which is different from legal or medical advice. Every output passes a human gate.
- Translations of fixed UI strings are marked for community review before the pilot.

## 9. Tradeoffs I chose

| Decision | Chosen | Alternative | Why |
| --- | --- | --- | --- |
| Where truth lives | Code computes dates, status, and search filters | Let the model reason | Judges and navigators can audit code; zero invented dates |
| Nonprofit search | Curated directory plus Claude re-rank | Live web search | Reliable in a live demo, no invented organizations, cites sources |
| Q&A scope | Closed-world over her own record | General health chatbot | Safer for elders, clear value, easy to verify |
| Alerts | Navigator flag only | Automatic SMS to family | Respects autonomy, avoids false alarms, fits human gate |
| Storage | SQLite document store seeded from JSON | Hosted database | Survives restarts with zero setup; one file to encrypt or back up; swap later without changing the API |
| Frontend | Static files, no build | React app | Runs anywhere with one command |

## 10. Evaluation

| Metric | Target |
| --- | --- |
| Deadline accuracy on labeled notices | 100 percent (current: 16 of 16 across Medi-Cal, CalFresh, IHSS, MSP) |
| Escalation recall | 100 percent (current: 8 of 8) |
| Exemption detection | 100 percent (current: 8 of 8) |
| Invented citations or record IDs | 0 (current: 0) |
| Ask Carethropic advice-guard recall on dose-change questions in seven languages | 100 percent (current: 9 of 9) |
| Grounded answers cite the right record kind | 100 percent (current: 6 of 6) |
| Nonprofit search acceptance query | Top 2 are SF Claude partners; AAPI SF orgs follow (current: 5 of 5 finder queries) |

## 11. Demo script (3 minutes)

1. **Hook (15s).** "One Bay Area navigator serves a pregnant mother on Medi-Cal and an 82-year-old grandmother who lives alone. Both can lose care to one missed date."
2. **Ligaya (40s).** Decode her discontinuance notice. Show Act today, the 7-day notice defect, attorney escalation.
3. **Wai Ling (45s).** Decode her renewal notice, tap Save to record. Switch to her record in Traditional Chinese. She asks "When is my Medi-Cal deadline?" and gets the cited date.
4. **Remy (40s).** Console shows a missed check-in flag. Open her record in Tagalog. She asks "Should I take two pills since I forgot?" Carethropic answers kindly, cites her med entry, and points to the pharmacist. Print her Emergency QR card after recording consent.
5. **Finder (20s).** Search "Claude Non-profit sponsors in san francisco." SF Claude partners appear first, then SF AAPI elder and women's organizations.
6. **Close (10s).** "Carethropic: every deadline caught, every answer cited, every record kept with care."

## 12. Roadmap

1. Pilot with Filipino Advocates for Justice, then Self-Help for the Elderly, AACI, and HICAP programs.
2. CalWORKs and SSI/SSP notices (CalFresh, IHSS and Medicare Savings Program notices shipped in 2.2).
3. Voice-first elder mode with recorded prompts in each language.
4. Optional, consented family digest.
5. Claude for Nonprofits plugin packaging so partner organizations can install Carethropic skills directly.
