---
name: hn-brief-dataset
description: "Query the local HN Brief dataset: today, history, search."
version: 1.0.0
author: Hermes Agent 01
license: MIT
metadata:
  hermes:
    tags: [hacker-news, hn, dataset, daily, research, local-data]
    related_skills: [hn-brief-digest, grounded-citations]
---

# HN Brief Dataset (local, read-only)

Answer HN questions from the machine-readable dataset a pipeline on lunarBeacon
writes daily at ~07:13 America/New_York. No scraping, no browser, no guessing.

## Data root

`/opt/shared_space/hn-brief-data` (read-only mount). Never write to it.

```
latest.json            {date, runId, path}      ← always start here
archive.json           [{date, path, runId, storyCount}, ...] newest first
daily/YYYY/MM/DD.json  full day: date, generatedAt, runId, source, model,
                       digest (long essay), quality{storyFailures, storyCount,
                       digestValid}, stories[] in rank order
daily/YYYY/MM/DD.md    ready-made Markdown of the same day
daily/YYYY/MM/DD-digest.md   Markdown digest only
runs/                  raw debugging traces — IGNORE, not the product
```

Story fields: `id`, `title`, `url`, `points`, `num_comments`, `postType`,
`summary` (the article), `discussion_summary` (the HN comments).
HN discussion link: `https://news.ycombinator.com/item?id=<id>`.

## Use the script, not manual parsing

```bash
python3 /opt/data/scripts/hn-brief-data.py latest          # today, all 20 stories
python3 /opt/data/scripts/hn-brief-data.py top 5           # top N of a day
python3 /opt/data/scripts/hn-brief-data.py top 5 --date 2026-11-18
python3 /opt/data/scripts/hn-brief-data.py search "rust" --days 7 --snippets
python3 /opt/data/scripts/hn-brief-data.py day 2026-11-21 --full
python3 /opt/data/scripts/hn-brief-data.py digest --date 2026-11-21
python3 /opt/data/scripts/hn-brief-data.py days            # published dates
```

Any subcommand accepts `--json` for machine-readable output. Prefer the script
over reading JSON inline: the daily file is ~60 KB and the digest alone is
~15 KB, which is easy to truncate or mis-parse by hand.

## Answering rules

1. **Cite every claim**: story title + article URL. Add the HN discussion link
   when the question is about the HN reaction. Never cite a title without its
   link.
2. **Rank is rank order** in `stories[]` — index 1 is the top story of that day.
3. **"This week"** = union of `archive.json` dates within the last 7 days;
   `search --days 7` does that. Say which dates you covered.
4. **Staleness check**: after 08:00 America/New_York, if `latest.json.date` is
   not today's NY date, say: "today's run may have failed (latest is <date>)".
   Do not present a stale day as today. The script prints this warning itself.
5. **Digest vs stories**: `digest` is one written essay over the day;
   `summary`/`discussion_summary` are per-story. Don't attribute an essay claim
   to a specific story unless that story's summary supports it.
6. **Missing data**: if the date isn't in the dataset, say so. Never invent a
   story, URL, points value, or id.

## Pitfalls

- `runs/` is not the product — ignore it.
- The mount is read-only: writes fail. Cache anything you generate under
  `/opt/data/cache/`.
- Dates are NY-local dates from the pipeline run; `date` in the JSON is the
  authoritative label, not the file's mtime.
- `daily/YYYY/MM/DD.md` mirrors the JSON; use it only when you need the
  pre-rendered Markdown, not as a parse source.
- The digest-email job (`scripts/hn-brief-email.py`, cron 07:45 America/New_York)
  reads the same dataset — if it stops arriving, check
  `/opt/data/logs/hn-brief-email.log` before touching the dataset.
- **This container has no email sender provisioned** (no `msmtp`/`himalaya`,
  Hermes email platform unconfigured, host `msmtp` not reachable from the
  container). The job logs `NOT SENT … no email channel configured` and exits 0
  until a sender exists: drop `EMAIL_ADDRESS` / `EMAIL_PASSWORD` /
  `EMAIL_SMTP_HOST` into `/opt/data/secrets/mail.env` (outbound
  `smtp.gmail.com:465/587` is reachable from here), or set
  `HN_MAIL_SSH_HOST` to reach the host's msmtp.

## References

- `references/validation-spec.md` — what a correct answer / email must contain.
