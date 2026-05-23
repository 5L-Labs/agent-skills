# VTT Subtitle Parsing Reference

## VTT Format Overview

WebVTT (`.vtt`) caption files returned by YouTube use this structure:
```
WEBVTT

00:01.000 --> 00:04.000
First line of subtitle text

00:05.000 --> 00:08.000
Second line of subtitle text
```

Optional metadata lines appear at the top: `NOTE`, `STYLE`, `REGION`.
The `WEBVTT` byte-order-mark BOM may appear as `\uFEFF` at byte 0.

## Timestamp Patterns to Match

| Pattern | Example |
|---------|---------|
| `MM:SS.mmm --> MM:SS.mmm` | `00:01.000 --> 00:04.000` |
| `H:MM:SS.mmm --> ...` | `1:02:03.456 --> ...` (10+ hour videos) |
| With space separator | `00:01.000-->00:04.000` (no space after `-->`) |

**Regex that matches both**:
```python
r"(\d{1,2}):(\d{2})\.(\d{3})\s*-->\s*(\d{1,2}):(\d{2})\.(\d{3})"
```
Groups 1–2 = start hour/minute; groups 4–5 = end hour/minute.

## Converting to [MM:SS] Display Format

YouTube transcripts use `MM:SS` (minutes:seconds, no milliseconds). Convert:

```python
def to_mm_ss(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"   # H:MM:SS for >60 min videos
    return f"{m}:{s:02d}"                # MM:SS for ≤59 min videos
```

For the VTT timestamp `HH:MM.mmm`: `seconds = HH * 60 + MM`. Discard the milliseconds.

## Extracting Text from VTT Cues

Each cue body may span multiple lines. Ignore VTT speaker tags (`<v Speaker>`) and
position tags (`<c...>` / `<b>` / `<i>` / `<u>` / `<ruby>`), which are cosmetic:

```python
import re

def extract_cue_text(cue_body: str) -> str:
    text = re.sub(r"<[^>]+>", "", cue_body)
    text = re.sub(r"\d{1,2}:\d{2}\.\d{3}\s*-->.*", "", text)
    return " ".join(l.strip() for l in text.splitlines() if l.strip())
```

## Common Gotchas

- **Empty/blank lines between cues** — VTT uses blank-line delimiters; don't treat them as missing text.
- **BOM at file start** — first line may be `\ufeffWEBVTT`; strip before parsing.
- **Duplicate segments** — only deduplicate if both timestamp AND text are identical.
- **Rate limiting (HTTP 429)** — YouTube punishes rapid VTT fetches. Sleep 3–5 seconds between subtitle downloads in batch pipelines. Re-fetch metadata before each batch (the `&ei=` tokens in subtitle URLs expire).
- **hermes-proxy / MITM SSL** — `youtube-transcript-api` can fail with `UNEXPECTED_EOF` even when `curl` works. Fix: `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`, or switch to `yt-dlp`.
- **execute_code subprocess inherits SSL_CERT_FILE** — `execute_code`'s Python env includes the host's `SSL_CERT_FILE` (e.g. `/usr/lib/ssl/cert.pem`, which is often the *system's own cert*, not a CA bundle). Any subprocess spawned from `execute_code` inheriting that variable will break SSL for yt-dlp. **Fix:** explicitly strip `SSL_CERT_FILE` from the subprocess env dict in `subprocess.run()`, or force-clean with `env={k:v for k,v in os.environ.items() if 'SSL' not in k.upper()}`. Bash scripts launched via `terminal` are unaffected because the terminal sets a working value — so prefer the assembly line `terminal` → `bash script` for batch runs.
- **`youtube-transcript-api` NOT installed in hermes venv** — `/opt/hermes/.venv/bin/python3` lacks the library and can't install it (site-packages is readonly). **Correct install pattern:** `uv venv /tmp/yt-venv && uv pip install --python /tmp/yt-venv/bin/python youtube-transcript-api`; then run scripts with `/tmp/yt-venv/bin/python SKILL_DIR/scripts/fetch_transcript.py …`.
- **YouTube `/api/timedtext` returns Google's "Sorry…" captcha page** — a direct curl/`requests` GET to `https://www.youtube.com/api/timedtext?...` is rate-limited or geoblocked and returns HTML, not VTT. Do not attempt to parse it. Always use `yt-dlp --write-auto-subs` or `fetch_transcript.py` instead.
- **yt-dlp `--write-auto-subs` caching** — silently skips download if a sub file with the same output name already exists. Use a **per-video sub-directory** (e.g. `/tmp/subs_ytbatch/{VIDEO_ID}/`) so the output path changes every run and yt-dlp cannot falsely conclude the file is already present.
- **yt-dlp 429 / 403 on subtitle downloads** — if `--write-auto-subs` returns empty stderr but no VTT file, it may be rate-limited. Add `--sleep-subtitles 3 --extractor-retries 3 --sleep-requests 1` and sleep 5 s between videos in batch scripts.
