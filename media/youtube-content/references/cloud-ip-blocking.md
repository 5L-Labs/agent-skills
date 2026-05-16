# Cloud IP Blocking — Detection & Workarounds

## Observed Error Patterns

When YouTube blocks requests from cloud IPs, the following errors occur:

**youtube-transcript-api / requests library:**
```
SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1029)'))
```
Or formatted as:
```
HTTPSConnectionPool(host='www.youtube.com', port=443): Max retries exceeded with url: /watch?v=VIDEO_ID (Caused by SSLError(SSLEOFError(...)))
```

**curl:**
```bash
curl https://www.youtube.com
# Exit code 35
# No output or incomplete output
```

**yt-dlp:**
```
WARNING: [youtube] [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1029)
```

**urllib (used by fetch_yt_transcripts.py):**
```
Error: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol>
```

## Detection Script

```bash
#!/bin/bash
# Quick test for YouTube connectivity from current host
curl -s --max-time 10 https://www.youtube.com > /dev/null 2>&1
if [ $? -eq 35 ]; then
  echo "BLOCKED: curl exit 35 (SSL error)"
else
  echo "OK: curl succeeded or different error code"
fi

# Or test with the herm python directly
/opt/hermes/.venv/bin/python3 -c "
from youtube_transcript_api import YouTubeTranscriptApi
try:
    result = YouTubeTranscriptApi().fetch('wjJG8ga63lQ')  # Known available video
    print('OK: fetched', len(result), 'segments')
except Exception as e:
    print('FAIL:', str(e))
"
```

## Workaround Priority

1. **Check local cache first** — `/opt/data/home/.hermes/content/youtube-raw/` may already contain the transcript from a previous non-blocked run
2. **Residential proxy or VPN** on the machine
3. **Exported cookies** from an active YouTube session (requires browser-side capture)
4. **Offline pre-fetch** from a different network location
5. **Wait and retry** — some cloud IP blocks are rate-based and may lift after cooldown (typically 1-24 hours)

## Blocked Directory Structure

```
/opt/data/home/.hermes/content/youtube-raw/
├── <VIDEO_ID>_fulltext.txt
├── <VIDEO_ID>_meta.json
└── <VIDEO_ID>_transcript.txt

/opt/data/content/youtube-raw/
├── <VIDEO_ID>_failed.txt   ← written on failures
├── <VIDEO_ID>_fulltext.txt
├── <VIDEO_ID>_meta.json
└── <VIDEO_ID>_transcript.txt
```

Note: The cron script `fetch_yt_transcripts.py` uses `~/.hermes/...` while the batch processor uses `/opt/data/content/...`. When a video is truly complete, files exist in the `/opt/data/content/youtube-raw/` directory.
