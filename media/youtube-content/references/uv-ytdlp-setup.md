# Transcript Fetching: uv + yt-dlp Setup

This note captures what worked (and what broke) during transcript fetching
in the 2026-05-15 batch run.

## Situation diagnosed

Python's `youtube-transcript-api` failed with
`SSLError: UNEXPECTED_EOF_WHILE_READING`. The same error occurs in `urllib`,
`uv.pip.install`, and `yt-dlp`. It is a *cloud-provider IP block* against the
`api/youtubei/v1/player` and `api/timedtext` endpoints in particular.
Watch-page HTML (`curl https://www.youtube.com`) works; timedtext/caption
endpoints fail regardless of tool.

## What to use as fallback

**yt-dlp with browser cookies** bypasses the block because the request carries
your logged-in session cookie rather than an anonymous cloud IP.

### Single-shot install + fetch

```bash
# Install yt-dlp into a throwaway venv (no pip in the main venv)
uv venv /tmp/yt-venv && uv pip install --python /tmp/yt-venv/bin/python yt-dlp

# Check available subs (subtitle list returned even from blocked IPs
# if you carry cookies — adjust the browser path)
/tmp/yt-venv/bin/yt-dlp --cookies-from-browser chrome \
  --list-subs "https://www.youtube.com/watch?v=VIDEO_ID"

# Download auto-generated English subs as SRT, skip the video:
/tmp/yt-venv/bin/yt-dlp --cookies-from-browser chrome \
  --skip-download --write-auto-sub --sub-lang en --sub-format srt \
  --output "/opt/data/content/youtube-raw/VIDEO_ID.subs" \
  "https://www.youtube.com/watch?v=VIDEO_ID"

# Convert SRT → [MM:SS] timestamped transcript:
python3 -c "
import re, sys
with open('VIDEO_ID.en.srt') as f: content = f.read()
for blk in re.split(r'\n\n+', content.strip()):
    lines = blk.split('\n')
    if len(lines) >= 3:
        ts = lines[1].split(' --> ')[0].replace(',', '.')
        h, m, s = ts.split(':')
        secs = int(h)*3600 + int(m)*60 + float(s)
        mm, ss = int(secs//60), int(secs%60)
        print(f'[{mm:02d}:{ss:02d}] {\" \".join(lines[2:]).strip()}')
" > VIDEO_ID_transcript.txt
```

## Verification summary (2026-05-15)

| Method | Result |
|---|---|
| `curl https://www.youtube.com` | HTTP 200 ✅ |
| `curl api/youtubei/v1/player` | Blocked ❌ |
| Python `urllib` watch page request | Blocked ❌ |
| `/opt/hermes/.venv/bin/python` (youtube-transcript-api) | Blocked ❌ |
| `uv venv /tmp/yt-venv` + youtube-transcript-api | Blocked ❌ |
| `yt-dlp --write-auto-sub` (no cookies) | Blocked ❌ |
| `yt-dlp --cookies-from-browser` | Works when cookies available ✅ |
| `/opt/data/scripts/fetch_yt_transcripts.py` (page HTML) | Partially ✅ (HTML + metadata only; no timedtext) |
