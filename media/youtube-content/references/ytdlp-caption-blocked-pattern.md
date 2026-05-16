# yt-dlp Metadata-Only Fallback Pattern

**When**: Cloud IP fully blocks `youtube.com/api/timedtext` captions (all tools return Google
"Sorry" block page, but `youtube.com/watch` HTML page succeeds).

**Why it works**: yt-dlp extracts metadata and signed caption URLs from the watch page in a
single session. If captions *themselves* are blocked on the timedtext endpoint but the watch
page is reachable, the JSON dump will include chapter breakdowns and video metadata even when
no caption text can be fetched.

## Pattern

```bash
# Step 1: dump full metadata (write to file; --dump-json is truncated in terminal output)
/tmp/yt-venv/bin/yt-dlp --skip-download --dump-single-json --no-warnings --quiet \
  "https://www.youtube.com/watch?v=VIDEO_ID" > /tmp/yt-json/VIDEO_ID.json\

# Step 2: parse chapters from JSON, write placeholder transcript files
python3 -c "
import json
with open('/tmp/yt-json/VIDEO_ID.json') as f:
    data = json.load(f)
print(data['title'], data.get('duration'), data.get('chapters'))
"
```

## Key field types from yt-dlp JSON

| Field | Type | Note |
|---|---|---|
| `data['title']` | `str` | URL-decoded title |
| `data['duration']` | `int` (seconds) | Convert to `H:MM:SS` or `MM:SS` |
| `data['chapters']` | `list[dict]` or `None` | `None` → no chapters; guard with `chapters or []` |
| `data['automatic_captions']` | dict by lang code | Can confirm ENABLED caption status |
| `data['subtitles']` | dict by lang code | User-uploaded subtitles (less common) |
| `chapters[].start_time` | `float` | Chapter start in seconds |
| `chapters[].title` | `str` | Chapter title |

## Critical notes

- **`--dump-json` is NOT the same as `--dump-single-json > file`**: the first writes to stdout
  (truncated in terminal/execute_code), the second redirects to a real file (safe, no truncation)
- **Signed timedtext URLs expire within minutes** of the dump; captions must be fetched in the
  same shell sequence as the JSON dump, or via yt-dlp's `--write-auto-subs` in-band
- **`chapters` can be `None`** — always guard with `chapters or []` before `len()` or iteration
- **Cloud IP block scope**: The timedtext/caption endpoint (`youtube.com/api/timedtext`) is
  blocked separately from the watch page (`youtube.com/watch`). The watch page may return
  HTTP 200 fine while captions return the Google block page
- Writing placeholder files (chapter breakdown + note) is acceptable progress in a block
  scenario; these files count as "processed" in the batch system and won't trigger infinite
  retries on the next run

## When the metadata fallback still fails

If even `--dump-single-json > file` returns empty or fails, the block is on the *watch page*
itself. At this point:
- Do NOT add to `failed_videos` with `confirmed_permanent` (block may lift later)
- Leave latent backlog unmarked; system will retry via `_process_youtube_batch.py`
- Wait for residential/VPN access or pre-fetch from an unblocked network