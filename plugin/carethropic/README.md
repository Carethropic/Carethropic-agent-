# Carethropic plugin

Lets a navigator work the Carethropic caseload from Claude: decode Medi-Cal, CalFresh, IHSS and Medicare Savings Program notices, review computed deadlines and defects, run morning check-in triage, ask about a client's record, and find Bay Area nonprofits.

## What is inside

| Component | Purpose |
| --- | --- |
| `skills/decoding-benefits-notices` | Run a notice through the pipeline and read back deadlines, findings and the draft reply |
| `skills/checking-in-on-elders` | Morning triage of elders who live alone; one-person questions; check-ins and consent |
| `.mcp.json` | The Carethropic connector (Streamable HTTP) |

## Setup

1. Run the Carethropic backend somewhere Claude can reach over HTTPS (see the repository README, "Connector"). Note the URL, which ends in `/mcp`, and the bearer token you set with `CARETHROPIC_MCP_TOKEN`.
2. Set `CARETHROPIC_MCP_URL` and `CARETHROPIC_MCP_TOKEN` in the environment where the plugin runs, or edit `.mcp.json`.
3. Install the plugin. In claude.ai you can instead add the same URL as a custom connector under Customize → Connectors and upload the two skills under Settings → Capabilities → Skills.

## Boundaries

Every deadline, exemption, check-in status and nonprofit ranking is computed by the backend in tested code; the skills tell Claude to report those results and never to add a date or rule of its own. Nothing is sent to a county or a client; the navigator approves every letter. Demo data is synthetic.
