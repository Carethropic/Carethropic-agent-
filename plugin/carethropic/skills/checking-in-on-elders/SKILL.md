---
name: checking-in-on-elders
description: Runs a navigator's morning triage of elders who live alone through the Carethropic connector: who missed a check-in, which medicines are unconfirmed, what is due this week, and what to say on the call. Use when a navigator asks who needs a call today, who missed a check-in, how a client is doing, or wants a client's daily briefing, record or emergency card.
---

# Checking in on elders

Check-in status is computed on the server from confirmation logs. Report it as recorded; never assume a medicine was taken because it usually is.

## Morning triage

1. Call `carethropic:navigator_console`. Rows carry `status.level` (`ok`, `late`, `missed`, `missed_2_days`, `none`) and `flags`.
2. List people in this order: `missed_2_days`, then `missed`, then anyone with an **Act today** or **Attorney review** flag, then `late`, then upcoming dates within 14 days. Skip `ok` unless asked.
3. For each person to call, call `carethropic:get_record` and give the navigator: last daily check-in, unconfirmed medicines with their scheduled times, the next appointment or deadline, the emergency contact, and the client's language and interpreter need.
4. Offer a short call script in plain words: confirm she is OK, ask about each unconfirmed medicine without telling her to take it, confirm the next date, ask if she wants her contact called.

Carethropic sends no calls or texts. The navigator decides.

## One person

- "How is Remy doing?" → `carethropic:get_record` plus `carethropic:daily_briefing` (the briefing is the spoken summary in her language; quote its `text`).
- "Did she take her pills?" → read `status.items` from the record. `taken` has a time; `late` or `missed` has none. Say "no confirmation" rather than "she didn't take it".
- "What are her medicines?" → from the record, with dose and times. Do not suggest changing any of them.
- Questions in the client's own voice ("Should I take two?") → `carethropic:ask_record`; relay the answer as given, including the advice guard when it fires.

## Recording a check-in or consent

Only when the navigator says the client confirmed it: `carethropic:record_checkin` with `type` `daily` or `med` (with the medication `item_id` from the record). The reply includes `spoken`, the confirmation in her language.

Emergency card: `carethropic:emergency_card` refuses without consent. Record consent with `carethropic:record_consent` only after the navigator says who gave it; the event is hashed into the audit chain.

## Rules

- Record IDs are the keys; two clients can share a name.
- Member IDs are masked; never ask for or repeat a full one.
- Dosing, skipping or combining medicines is for her pharmacist or doctor. Carethropic says so; so do you.
