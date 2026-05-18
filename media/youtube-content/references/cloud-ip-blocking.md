# Cloud IP Blocking — YouTube Transcript Fetch

## Failure Taxonomy

| Layer | Error Pattern | Behaviour |
|-------|--------------|-----------|
| `youtube_transcript_api` | `SSL: UNEXPECTED_EOF_WHILE_READING` in `_ssl.c:1029` | TCP handshake completes but TLS read fails mid-stream — dropped/blackholed by Google's edge |
| `yt-dlp` query | Silent failure / empty stdout | Google's /next endpoint is also DoS-protected from cloud IP ranges |
| `urllib` direct watch-page fetch | Same `SSL: UNEXPECTED_EOF_WHILE_READING` | Network-level block; no client library can bypass this from the same IP |

**All three layers fail identically from the same host.** This is an IP-range block, not a library bug.

## Blocked Path (Do NOT retry)

On this machine at the time of last run:
- `python3 fetch_transcript.py "URL"` → SSL error (youtube-transcript-api call blocked)
- `yt-dlp --dump-single-json URL` → empty/timed out
- `urllib.request.urlopen("https://youtube.com/watch?v=VIDEO_ID")` → same SSL error

Do not create temporary venvs, retry different Python versions, or use urllib as a bypass — the network path itself is blocked from this IP range.

## What IS Available Locally

The git repo at `/opt/data` contains all 3-file sets for already-processed videos in `/opt/data/content/youtube-raw/`. These were fetched before the block was applied or from a different network path. The full set exists for every video in `yt-backlog.json` `unique_videos`.

## Override Attempt — VTT Caption URL (usually also blocked)

One possible circumvention strategy (not reliably achievable from blocked IPs):

1. Fetch watch-page HTML via `urllib` → parse `captionTracks` JSON array from page source
2. Extract the VTT URL from the `baseUrl` field
3. Download the VTT directly from that CDN URL with `urllib` (the CDN host may be on a different IP block)

**Caveat**: Step 1 fails with the same SSL error from blocked IPs. Only works if you have a non-cloud/proxy IP available for the HTML fetch.

## Fallback: Chapter Outline (most reliable under IP block)

When both transcript fetch and VTT attempt fail gracefully, extract chapter data from `yt-dlp` metadata (when available):

```bash
/opt/data/home/.local/bin/yt-dlp --dump-json --skip-download "https://youtube.com/watch?v=VIDEO_ID" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps({'title':d.get('title'),'duration':d.get('duration'),'segments':d.get('chapters',[])}, indent=2))"
```

Use chapter titles + timestamps as a surrogate transcript (`_transcript.txt` and `_meta.json`). Save with `note: "chapter_outline_ip_blocked"` so future runs know captions are surrogates, skip re-fetch, and re-present honestly.

## Confirmed-Permanent vs Transient — how to mark in yt-backlog.json

| Status | Use when | Retry next run? |
|--------|----------|-----------------|
| `"confirmed_permanent"` | "Transcripts are disabled for this video", "No auto-generated subtitles available", forced IP blacklist | No |
| `"transient_block"` | transient network error, empty yt-dlp response, timeouts, class-3/4 VTT fetches that bypassed metadata | Yes |

Record the **received error message verbatim** in the `note` field. Update `last_updated` on every cron run to detect stuck crons.

## Detection and Pre-scan logic for batch scripts

Older batch scripts with hardcoded `VIDEOS` arrays skip any video where all 3 files exist and `note` is NOT `chapter_outline_ip_blocked`. If a 3-file set exists with `chapter_outline_ip_blocked` in its meta, report honestly but still skip re-fetch.

Orphan 3-file sets (exist in `youtube-raw/` but absent from `unique_videos`) should be added to `unique_videos` silently — crontab restarts or crashes in prior runs can cause a file-save + backlog-append race condition.
