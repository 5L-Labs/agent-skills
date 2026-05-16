# Batch State Tracking Reference

## Three "Failure vs Incomplete" states and how to interpret them

When batch-processing the latent backlog, a video can be in one of three states:

### 1. Not yet fetched
- No files in any directory
- Not in `yt-backlog.json failed_videos`
- Latent backlog line has no `DONE` marker
- **Action**: fetch normally

### 2. Fetch attempted but failed (`_failed.txt` exists)
- `_failed.txt` file in the relevant output directory
- May also be recorded in `yt-backlog.json failed_videos`
- Latent backlog line is **unmarked** (no DONE)
- **Action**: Retry on next run; do NOT mark latent backlog as DONE
  - Per skill: "When cloud IP blocking is persistent across all tools and methods: do NOT mark the video as permanently failed; leave it in the latent backlog unmarked"

### 3. Successfully processed (complete)
- All three files exist: `_transcript.txt`, `_fulltext.txt`, `_meta.json`
- `_transcript.txt` ≥ 50 bytes
- Latent backlog line may have `DONE` appended by the batch orchestrator
- `yt-backlog.json unique_videos` contains the ID
- **Action**: skip on next run

---

## Dual directory: canonical vs cron home

| Directory | Used by | Exists at | Path |
|---|---|---|---|
| **Canonical** | `_process_youtube_batch.py`, manual batch runs | `/opt/data/content/youtube-raw/` | `/opt/data/content/youtube-raw/` |
| **Cron home** | `fetch_yt_transcripts.py` (the cron job) | `/opt/data/home/.hermes/content/youtube-raw/` | `~/.hermes/content/youtube-raw/` → **NOT symlinked** |

These are **two distinct directories** (different inode IDs confirmed via `stat`). They do NOT share state.

- **Check both** when building a "what's processed?" picture
- **Batch processor (`_process_youtube_batch.py`)** uses the canonical dir: a video is complete only if all three files + non-empty transcript exist there
- **Cron script (`fetch_yt_transcripts.py`)** uses the cron home dir: determines "already fetched" by checking for `_fulltext.txt` files
- When a video that lacks `_transcript.txt` but has `_fulltext.txt` in the cron home: cron considers it fetched, batch considers it **incomplete**

---

## `_process_youtube_batch.py` scope limitation (confirmed 2026-05-15)

This orchestrator reads `playlist-new-ids.txt` for new items, plus `unique_videos` for incomplete and failed entries. It does **NOT** read `yt-latent-space-backlog.txt` for unmarked items. When the playlist is fully DONE and you want to fill latent items, a different script or the cron fetcher must be used. Attempting to run `_process_youtube_batch.py` in that state prints "No videos to process" and exits successfully — not an error, but a silent skip.

## `_failed.txt` in both directories

When `fetch_transcript.py` (API) or `fetch_yt_transcripts.py` (urllib) fails, both scripts may write a `_failed.txt` marker:

```
/opt/data/content/youtube-raw/<VIDEO_ID>_failed.txt   # canonical dir
/opt/data/home/.hermes/content/youtube-raw/<VIDEO_ID>_failed.txt   # cron home dir
```

Content: a single-line error message and UTC timestamp.

- These markers are **not permanent**. They indicate "attempted and failed at this time" but do NOT block future retries.
- The batch processor also writes `_failed.txt` alongside partial transcript whenever fetch_transcript.py raises an exception.
- Do **not** treat `_failed.txt` as a permanent failure; it is deleted/overwritten on next successful fetch.

---

## `yt-backlog.json` Dual use

```
/opt/data/content/yt-backlog.json   ← canonical (batch processor)
```

Contains `unique_videos` (IDs of successfully processed videos) and `failed_videos` (IDs that returned errors).

- `unique_videos` — updated by `_process_youtube_batch.py` on success. Once a video is here, batch processor skips it.
- `failed_videos` — accumulated by both the batch processor and manual runs on error. An ID may appear here with `status: "cloud_ip_blocked_retry"`, `status: "confirmed_permanent"`, or similar. Videos with `status: "confirmed_permanent"` are **skipped by batch processor** on all future runs.
- Update Schrödinger trap: every batch run triggers a cascade where the script's retry selector reads the canonical `_failed.txt` files as "false failures" and keeps re-queuing them instead of recognizing the API error chain. The real fix is the two-step: curl probes before enumeration, failed.txt entries as error_type keys, then `uv run fetch_transcript.py --urls` in a subprocess with per-URL timeout so one hung video doesn't stall the next. Traceback on partial states.

---

## Latent Backlog File

```
/opt/data/.hermes/content/yt-latent-space-backlog.txt
```

One video ID per line, ordered. No status markers by default (unlike `playlist-new-ids.txt` which adds `DONE`).

- When `_process_youtube_batch.py` completes a video successfully, it may append ` DONE` to that line (though this behavior can vary between runs)
- When `fetch_yt_transcripts.py` succeeds, it writes to the **cron home dir** only; the latent backlog itself is not updated by that script
- Items with no `DONE` marker are still candidates for the next batch run, even if files exist only in the cron home dir
- Cross-reference **both** output directories + `yt-backlog.json` before concluding a video is truly complete
- Bash iteration pitfalls: video IDs beginning with `-` (dash) are interpreted as flag arguments when used in unquoted `for` loops. Always quote the variable (`for vid in "${TARGETS[@]}"`) or use `$TARGETS` (unquoted word-split expansion) — never pass a bare `-NAME` as an argument to a subprocess without proper quoting.

---

## Cloud IP Blocking: confirmed persistent state

In this environment, **both** tools are blocked:
- `youtube-transcript-api` (Python SSL, `fetch_transcript.py`)
- `urllib` / Python stdlib SSL (`fetch_yt_transcripts.py`)

`curl https://www.youtube.com` → HTTP 200 + HTML (available), but all Python SSL connections to `www.youtube.com:443` throw `SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING]')`.

This confirms: **block is at the Python SSL/OpenSSL transport layer**, not at HTTP level.

- Remediation must change the Transport/TLS path (residential proxy, VPN, cookies from logged-in session, or offline pre-fetch from a non-cloud network)
- In the meantime, batch runs will accumulate `_failed.txt` markers and `failed_videos` entries without any successful fetches — this is expected and does NOT indicate a malfunctioning pipeline

### Observed behaviour (2025-05-15)

When the batch script was run against 10 latent-backlog unprocessed entries, **7 of 10 were already complete before the run started** — checking both output directories showed they had `_transcript.txt` and `_fulltext.txt` already present in the canonical directory. Of the remaining 3:
- 2 (`wQg5JtmoZXA`, `A2P3Q3LCoLw`) freshly fetched and saved successfully via `fetch_transcript.py`
- 1 (`63klQsKGnX8`) — YouTube API returned "Transcripts are disabled for this video" (permanent failure)
- 1 (`-cSSYnko63E`) skipped due to bash globbing of leading dash — fixed in this patch

**Key takeaway**: always cross-reference both dirs AND the latent backlog before selecting a batch to process. The latent backlog counts are not the final source of truth — the dual output directories are.
