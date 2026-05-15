---
name: cron-job-delivery
description: Patterns for scheduled job output delivery to messaging platforms — silent runs, output filtering, state file management, and avoiding unwanted notifications.
tags: [cron, scheduling, delivery, patterns, discord, slack, telegram]
related_skills: []
---

# Cron Job Delivery Patterns

Use this skill when configuring scheduled jobs (Hermes cron, systemd timers, external schedulers) that deliver results to messaging platforms like Discord, Slack, or Telegram.

## The Zero-Output Rule

**If a scheduled job should produce NO output on quiet runs, it MUST write absolutely nothing to stdout/stderr — not even a placeholder line.**

Many messaging integrations (Hermes gateway, webhook bridges) deliver **any** output from the job to the target channel. A single line like `NO_ALERT` or `All clear` will still trigger a Discord message, which defeats the purpose of a silent pass.

### Wrong

```bash
echo "NO_ALERT"   # Triggers delivery — you'll see "NO_ALERT" in Discord
```

### Right

```bash
# Exit silently with no output at all
if [ -z "$new_items" ]; then
    exit 0   # No echo, no printf, no output of any kind
fi
```

In Hermes cron jobs, this means your prompt/template should conditionally produce no response at all when there's nothing to report — not even a "Nothing to report" line.

## State File Locations

Keep job state files (backlogs, processed IDs, caches) in the content directory that matches your HERMES_HOME:

| Default HERMES_HOME | State file location |
|---------------------|--------------------|
| `~/.hermes/`        | `~/.hermes/content/` |
| `/opt/data/` (custom) | `/opt/data/content/` |

When writing cron job prompts, **never hardcode** `/root/.hermes/` — use HERMES_HOME-relative paths or absolute paths that match the actual installation. A mismatch causes jobs to fail silently because they read non-existent files.

Check actual paths with:

```bash
hermes config path          # Shows config.yaml location
echo $HERMES_HOME           # Shows HERMES_HOME env var
ls -la $HERMES_HOME/content/   # Verify content directory exists
```

## Output Directory Structure

For jobs that save output locally AND deliver to chat:

```
$HERMES_HOME/cron/output/<job_id>/
  ├── 2026-04-16_12-01-20.md   # Markdown output (what was delivered)
  └── 2026-04-16_12-30-23.md
```

Inspect recent output:

```bash
ls -lt $HERMES_HOME/cron/output/<job_id>/
head -20 $HERMES_HOME/cron/output/<job_id>/$(ls -t | head -1)
```

If the job is running but producing no visible output, check these files — they may contain warnings or errors that weren't delivered to chat.

## Delivery Channels

Hermes cron jobs support multiple delivery targets via the `deliver` field:

| Value | Meaning |
|-------|---------|
| `discord:<channel_id>` | Post to Discord channel (channel ID from config or channel_directory.json) |
| `local` | Save to filesystem only, no chat delivery |
| `telegram:<chat_id>` | Telegram DM or group |
| `signal:+1234567890` | Signal user or group |
| `email:user@example.com` | Email |

When `deliver` is set to a specific platform, **any output at all** (including empty lines) may be sent. Use `local` during development/testing to avoid spamming channels.

## Playlist / Backlog Pattern

A common pattern: maintain a **playlist file** (one entry per line: `VIDEO_ID<TAB>TITLE`) and a **backlog JSON** with `unique_videos` (successfully processed) and `failed_videos` (permanently failed) arrays.

**Reconciliation check before processing:**

1. Read playlist → extract video IDs, skip lines containing `DONE`
2. Read backlog JSON → build `processed` set and `failed` set (note: `failed_videos` keys are inconsistent — some use `id`, others `video_id`)
3. List actual transcript files in `$HERMES_HOME/content/youtube-raw/*_transcript.txt`
4. Compute: `to_process = (playlist_ids - processed - failed) ∩ (ids_missing_transcript_files)`

The **ground truth** is actual file presence on disk, not the `DONE` marker or backlog entries — those can get out of sync after container rebuilds or manual cleanup.

Mark DONE after successful processing:

- Append `\tDONE` to the playlist line
- Add video ID to `backlog.json` → `unique_videos` array

## Common Pitfalls

### Silent output triggers delivery anyway
Even a single newline or debug print counts as output. Wrap all user-facing messages in conditionals that return early when there's nothing to report.

### Hardcoded paths in cron prompts
The cron job's prompt template often embeds paths like `/root/.hermes/content/playlist.txt`. These become stale when HERMES_HOME is customized. Always use paths that match the actual deployment (`/opt/data/content/` for this instance). Edit the cron prompt directly: `hermes cron edit <id>` → modify the `prompt` field.

### Stale RSS / upstream feeds
Aggregator jobs pulling from external RSS feeds (e.g., `news.smol.ai/rss.xml`) may go silent for days if the upstream feed stops updating. Add a freshness check (compare latest entry date to current date; if gap > N days, switch to an alternative source or alert).

### Confusing "last_status: ok" with actual work
The cron scheduler records `last_status: "ok"` even if the job produced zero output and did zero work. A job can report `ok` while actually being broken (reading empty playlists, hitting cached errors). Always check:
- `ls -lt $HERMES_HOME/cron/output/<job_id>/` for recent output files
- Playlist/backlog reconciliation to confirm new items were processed
- Job logs if available: `tail -50 $HERMES_HOME/logs/cron.log`

## Reference

- `references/silent-output.md` — minimal reproducible example of zero-output scripts
- `references/path-mappings.md` — common HERMES_HOME configurations and how to discover the correct content paths for your installation