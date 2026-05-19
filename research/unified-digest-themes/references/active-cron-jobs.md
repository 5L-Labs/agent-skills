# Active Cron Jobs Using This Theme System

This document lists every active cron job that loads `unified-digest-themes`. When the theme taxonomy changes (add/rename/remove a theme), update these jobs' prompts to match.

## HN Brief Daily Digest

| Field | Value |
|-------|-------|
| Job ID | `37017ee4425f` |
| Name | hn-brief-daily-digest |
| Schedule | `0 22 * * *` (22:00 EST daily) |
| Skills | `hn-brief-digest`, `unified-digest-themes` |
| Deliver | `discord:1503214829509410887` |
| Model | `qwen/qwen3.6-plus` (Nous) |
| Toolsets | web, terminal, file, browser |

**Update instruction:** None needed for theme changes — the cron loads unified-digest-themes and the hn-brief-digest skill handles the rest. Theme changes in unified-digest-themes/SKILL.md are picked up automatically on next run.

## X-Digest / AI High Signal

| Field | Value |
|-------|-------|
| Job ID | `7c85dd238709` |
| Name | ai-high-signal-digest |
| Schedule | `0 9 * * *` (09:00 UTC daily) |
| Skills | `x-digest`, `unified-digest-themes` |
| Deliver | `discord:1492908666871877833` |
| Model | `qwen/qwen3.6-plus` (Nous) |
| Toolsets | terminal, file, web |

**Update instruction:** None needed for theme changes — the cron loads unified-digest-themes and the x-digest skill handles the rest.

## Weekly AI News (smol.ai)

| Field | Value |
|-------|-------|
| Job ID | `1ce742becd58` |
| Name | weekly-ai-news |
| Schedule | `0 9 * * 1` (Monday 09:00) |
| Skills | (none currently) |
| Deliver | `discord:1491665873021440093` |
| Script | `/opt/data/scripts/smol_news_weekly.py` → `smol_news_aggregator.py 7` |

**Note:** This job does NOT currently load unified-digest-themes. To add theming, update the cron to load this skill and give it a prompt that classifies RSS items into the 7 themes.

## Monthly AI News (smol.ai)

| Field | Value |
|-------|-------|
| Job ID | `c1892105f9cf` |
| Name | monthly-ai-news |
| Schedule | `0 10 1 * *` (1st of month 10:00) |
| Skills | (none currently) |
| Deliver | `discord:1491665948523106404` |
| Script | `/opt/data/scripts/smol_news_monthly.py` → `smol_news_aggregator.py 30` |

**Note:** Same as weekly — does not load unified-digest-themes yet.

## arXiv Daily Papers

| Field | Value |
|-------|-------|
| Job ID | `c8e5e9663900` |
| Name | arxiv-daily-papers |
| Schedule | `0 8 * * *` (08:00 UTC daily) |
| Skills | `arxiv` (does not load unified-digest-themes) |
| Deliver | `discord:1491680460563026050` |

**Note:** Does not use unified theme system yet — uses its own arxiv skill for categorization.

---

## Adding unified-digest-themes to a new cron job

```bash
hermes cron edit <job-id> --skills '["<primary-skill>","unified-digest-themes"]'
```

After adding, the cron prompt should say something like:
"Load the `unified-digest-themes` skill for the canonical 7-theme taxonomy. Group items under the appropriate theme."

---

*Last updated: 2026-05-18*
