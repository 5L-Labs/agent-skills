---
name: youtube-batch-processing
description: Batch process YouTube video metadata and transcripts with rate limit handling. Cache metadata first via yt-dlp, then local-model tag with unified themes + jargon.
version: 2.0.0
author: Hermes Agent 01
triggers: ["batch youtube", "youtube playlist", "process youtube videos", "youtube transcripts bulk"]
---

# YouTube Batch Processing

Batch-fetch YouTube metadata and transcripts while avoiding IP rate limits.

## Strategy: Metadata First, Transcripts Second

**Never touch the transcript API until metadata is cached and organized.**
The transcript API is what gets rate-limited/blocked from cloud IPs. yt-dlp --dump-json (scrapes video page HTML) is far more resilient.

## Safe Pipeline (6 steps)

### Step 0: Playlist expansion (safe — no rate limits)
Extract video IDs + titles from playlists using yt-dlp flat mode.
This only scrapes the playlist HTML page, not individual videos.

```bash
yt-dlp --flat-playlist --print "%(id)s\t%(title)s" "https://www.youtube.com/playlist?list=PLAYLIST_ID" > playlist_raw.txt
```

Note: Output uses literal `\\t` (backslash-t), not actual tab. Parse with:
```python
parts = line.split('\\t')
vid = parts[0].strip()
title = parts[1].strip() if len(parts) > 1 else ''
```

### Step 1: Cache all metadata (safe with 2s delays)
Fetch titles, descriptions, durations, channels, tags via yt-dlp --dump-json.
Scrapes each video page individually — same as a browser visit, not the transcript API.
~2s per video = ~10 min for 300 videos.

```bash
mkdir -p /opt/data/content/playlists/cache
yt-dlp --batch-file video_urls.txt --dump-json \
  --sleep-interval 2 --max-sleep-interval 5 \
  --ignore-errors --no-download --no-warnings \
  > cache/video_metadata.json 2>/tmp/yt_meta_errors.log
```

**Always do this first.** Even if the transcript API gets blocked later, we still have titles, descriptions, tags, and durations for every video.

### Step 2: Theme + jargon tag from cache (uses local model, no API calls)
Once metadata is cached, use the `unified-digest-themes` and `jargon` skills to categorize each video from its title + description.
This is pure local processing — no YouTube requests, no token cost.

```python
import json

# Load cached metadata
with open('/opt/data/content/playlists/cache/video_metadata.json') as f:
    metadata = [json.loads(line) for line in f if line.strip()]

# Each entry has: id, title, description, duration, channel, tags, upload_date, categories, etc.
# Tag with unified-digest-themes taxonomy (7 categories):
# 1. AI & ML Research
# 2. Developer Tools & Infrastructure
# 3. Hardware & IoT
# 4. Security & Privacy
# 5. Industry & Business
# 6. Science & Technology
# 7. Community & Culture

# Decode jargon via jargon skill registry
# Save tagged index to cache/video_index.json
```

### Step 3: Surface to user (from cache, no YouTube needed)
Show the user what's available by theme, with descriptions.
Let them triage and prioritize before attempting any transcript fetches.

### Step 4: Fetch transcripts (rate-limited, gated)
Only attempt transcript fetching AFTER the user has reviewed and selected videos.
Use youtube_transcript_api with conservative delays.

```python
from youtube_transcript_api import YouTubeTranscriptApi
api = YouTubeTranscriptApi()

for vid in selected_videos:
    try:
        segments = api.fetch(vid)
        text = ' '.join(s.text for s in segments)
        # Save to youtube-raw/
        time.sleep(3)  # 3s between requests
    except Exception as e:
        log failure, continue
```

**Never process more than 10 transcripts per session.**
**Never process parallel transcripts.**
**If you get a 403/block, stop immediately and wait 24h.**

### Step 5: Summarize with local model
Use the cheapest available model (not frontier) to generate summaries from transcript text.
Local model preferences (least expensive first):
1. xiaomi/mimo-v2-pro (free via Nous)
2. qwen/qwen3.6-plus
3. deepseek/deepseek-v4-pro (only for signal-rich content)

### Step 6: Cron pipeline (daily, 10/day max)
```
Schedule: 0 12 * * * (daily at noon UTC)
Per-run: pick 10 unprocessed videos from cache/video_index.json
Process: fetch transcripts with 3s delays + summarize with local model
```

## Cache File Layout

```
/opt/data/content/playlists/
├── all_videos.txt              # VIDEO_ID\tTITLE (from flat playlist expand)
├── video_urls.txt              # https://... URLs (from all_videos.txt)
├── cache/
│   ├── video_ids.txt           # One ID per line
│   ├── video_metadata.json     # yt-dlp --dump-json output (one JSON object per line)
│   └── video_index.json        # Tagged with themes + jargon
└── latent_space.txt            # Per-playlist raw output (for reference)
```

## Pitfalls

1. **Cloud IP blocks are intermittent, not permanent** — YouTube does rolling bans (tested: 48h block April 14-15, lifted April 16).
2. **Never parallelize transcript fetches** — even 3 concurrent subagents triggered a 12-hour block historically.
3. **Don't retry after 429/block** — wait for block to fully lift (12-48h).
4. **yt-dlp tab delimiter** — uses literal `\\t` not actual tab, needs `split('\\t')`.
5. **yt-dlp --dump-json is NOT the transcript API** — it scrapes the video page HTML (title, description, channel, tags). It's the same type of request as --flat-playlist. Much lower risk of blocking.
6. **Always cache metadata first** before attempting transcripts. This way even if transcripts get blocked, we have titles + descriptions + tags to organize with.
7. **Use `web_extract` as fallback for partial descriptions** — if yt-dlp fails, web_extract on the video URL returns ~5K chars including title, description, and partial transcript.
8. **Paths depend on HERMES_HOME** — default is `~/.hermes`, current instance uses `/opt/data/`.
9. **Save playlists files to /opt/data/content/playlists/** — this path survives container rebuilds.
10. **Also sync skill updates to /opt/data/repos/agent-skills/** — the consumption dir picks these up, but the agent-skills repo is the source of truth.
