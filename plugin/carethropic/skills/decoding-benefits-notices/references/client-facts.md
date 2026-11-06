# Client facts that change the result

Pass these in `client_facts` to `carethropic:decode_notice` only when the navigator stated them. Never infer them.

| Fact | Type | Used for |
| --- | --- | --- |
| `pregnant` | boolean | Work-rule exemption; escalation when coverage is at risk |
| `postpartum_months` | number | Work-rule exemption (12 months); escalation |
| `children_ages` | list of numbers | Work-rule exemption for a child 13 or younger |
| `age` | number | Work-rule exemption outside 19–64; elder guidance |
| `medically_frail` | boolean | Work-rule exemption |
| `lives_alone` | boolean | Escalation on IHSS termination; reminder to save deadlines to the record |
| `household_size` | number | Asset limit: $130,000 plus $65,000 per additional person |
| `countable_assets` | number (dollars) | Asset screening on Medi-Cal and MSP notices about assets |
| `retirement_account_in_distribution` | boolean | Exempt asset |
| `owns_home_lives_in` | boolean | Exempt asset |
| `asset_transfer_dates` | list of ISO dates | Defect when the county relies on a transfer made in 2024–2025 |
| `caregiver_for_parent` | boolean | Practical reminder to check the parent's coverage |

Example: `{"age": 71, "lives_alone": true, "household_size": 1, "countable_assets": 112000, "retirement_account_in_distribution": true, "asset_transfer_dates": ["2025-03-15"]}`
