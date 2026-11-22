# Validation Spec: hn-brief-dataset + HN Brief daily email
# Last updated: 2026-11-22
# Change: new skill (dataset reader) + new daily email job (07:45 America/New_York)

## Positive Checks (MUST be present)

- [ ] Answers cite story title **and** article URL; HN discussion link present when the question is about discussion
- [ ] Story order matches `stories[]` rank order in the day JSON
- [ ] Dates come from `latest.json` / `archive.json`, never from file mtime
- [ ] Email subject is exactly `HN Brief — <date>` (em dash, date = dataset date)
- [ ] Email body ordering: header line → 20 headlines (title, points, comments, article URL, HN link) → separator → `DIGEST` → digest text
- [ ] Email is built from the dataset only; headline count matches `quality.storyCount` capped at 20
- [ ] Rendered email cached at `/opt/data/cache/hn-brief-email/<date>.txt`

## Negative Checks (MUST NOT be present)

- [ ] No invented stories, URLs, points, or HN item ids
- [ ] No content read from `runs/`
- [ ] No write attempted into `/opt/shared_space/hn-brief-data`
- [ ] No email sent when `latest.json.date` != today (America/New_York)
- [ ] No email sent when `quality.digestValid` is false
- [ ] No Discord delivery for anything in this pipeline

## Format-Specific Checks

- [ ] Plain text body (no HTML, no markdown tables)
- [ ] Stale-run warning appears in answers after 08:00 America/New_York when the latest date is not today
- [ ] Cron job carries `timezone: America/New_York` so 07:45 tracks DST
- [ ] Send failure exits non-zero so the failure notice fires instead of passing silently
