# Notice types the rules engine recognises

Each type lists the deadlines it computes (key → meaning) and the defects it checks. Authority IDs are the knowledge-base keys the tools return.

| Program | notice_type | Deadlines | Defects checked |
| --- | --- | --- | --- |
| Medi-Cal | `discontinuance` | `hearing_deadline` (90 days), `aid_paid_pending` (day before the effective date) | `short_advance_notice` (<10 days, fed-431-211), `missing_legal_basis` (fed-431-210) |
| Medi-Cal | `work_rule_noncompliance` | `work_rule_response` (30 days), `hearing_deadline` | `missing_legal_basis`; exemptions: pregnant, postpartum, caregiver of a child 13 or younger, age outside 19–64, medically frail (pl-119-21-71119) |
| Medi-Cal | `renewal_documents`, `annual_renewal` | `renewal_response` (printed due date or 30 days, whichever is earlier) | `short_renewal_window` (fed-435-916) |
| Medi-Cal | `termination_no_renewal` | `reconsideration` (90 days), `hearing_deadline` | `missing_legal_basis` |
| CalFresh | `calfresh_adverse_action` | `hearing_deadline` (90 days, fed-7-273-15), `continued_benefits` (day before the effective date) | `short_advance_notice` (<10 days, fed-7-273-13), `missing_legal_basis` (ca-mpp-22-001) |
| CalFresh | `calfresh_recertification` | `recert_timely` (printed due date or the 15th of the last month), `recert_late_window` (30 days after the period ends) | `late_expiration_notice` (sent inside the last month, fed-7-273-14) |
| IHSS | `ihss_reduction`, `ihss_termination` | `hearing_deadline` (90 days, ca-wic-10951), `aid_paid_pending` (ca-mpp-22-072), `hearing_good_cause_limit` (180 days) | `short_advance_notice` (<10 days), `missing_legal_basis`; termination of someone who lives alone escalates |
| Medicare Savings Programs | `msp_discontinuance` | `hearing_deadline`, `aid_paid_pending`, `asset_spend_down` (end of the month after the notice, when the reason is assets) | `short_advance_notice`, `missing_legal_basis`, `transfer_in_safe_harbor_window` (ca-ab-116-88); exemptions: under the asset limit, retirement account in payout, the home (ca-acwdl-25-14) |
| Medicare Savings Programs | `msp_renewal` | `renewal_response` | `short_renewal_window` |

Weekend and California holiday dates roll back to the prior business day (`rolled_back: true`).

## Fields the extractor returns

`notice_type`, `agency`, `case_number` (masked), `notice_date`, `effective_date`, `stated_due_date`, `certification_end_date` (CalFresh recertification), `hours_current` / `hours_new` (IHSS), `reason`, `legal_basis_cited`, `requested_documents`, `confidence` (0–1 per field).
