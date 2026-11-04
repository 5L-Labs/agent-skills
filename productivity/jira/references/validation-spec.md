# Validation Spec: jira
# Last updated: 2026-11-04
# Change: New skill — Jira/Atlassian MCP on terraalpha; HOMEWORK queue drives the Daily Open Work Reminder cron.

## Positive Checks (MUST be present)

- [ ] Reminder opens with a date line like "Wednesday, November 04, 2026 - Work Queue"
- [ ] Issues grouped by tier: HIGH PRIORITY / MEDIUM / LOW (empty tiers omitted)
- [ ] Each issue line: KEY + summary + (type, status) — e.g. "HOMEWORK-1: Car Shopping / Negotiation - Toyota Grand Highlander quotes (Task, To Do)"
- [ ] Footer present: "To stop or manage this job, send me a new message."
- [ ] Queue query returns ALL open issues (status not in Done/Closed/Canceled) — none dropped
- [ ] "N open issues" note line reflects the true count

## Negative Checks (MUST NOT be present)

- [ ] No markdown headers, bold/italics, or emoji (plain text for Signal)
- [ ] No fabricated or hallucinated issues — anything in the message must exist in Jira
- [ ] No invented URLs or issue keys

## Format-Specific Checks

- [ ] Phone-width: each line short enough to read on mobile without wrapping badly
