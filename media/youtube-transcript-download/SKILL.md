---
name: youtube-transcript-download
description: Download YouTube video transcripts/subtitles using yt-dlp. Reliable fallback when web_extract truncates, the timedtext API returns empty, or the youtube_transcript_api module is unavailable.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [youtube, transcript, subtitles, yt-dlp]
---

# YouTube Transcript Download

Download YouTube auto-generated or manual subtitles using yt-dlp. Use when you need the full transcript of a YouTube video.

## When to Use

- web_extract returns truncated content (~5000 char limit)
- YouTube timedtext API returns empty responses (needs cookies/auth)
- youtube_transcript_api module is not installed
- You need the full, complete transcript reliably

## Prerequisites

`yt-dlp` must be **installed and on `$PATH`**. If not available:

```bash
# Try quick check first
yt-dlp --version 2>/dev/null || echo "not found"

# If absent, install via uv (no pip needed in main venv):
uv venv /tmp/yt-venv && uv pip install --python /tmp/yt-venv/bin/python yt-dlp
# Binary lands at /tmp/yt-venv/bin/yt-dlp
```

**Verification:**
```bash
/tmp/yt-venv/bin/yt-dlp --version
```


## Quick Start

```bash
# Download English auto-subtitles as SRT (skip video download)
/opt/data/home/.local/bin/yt-dlp --write-auto-sub --sub-lang en --sub-format srt --skip-download -o "/opt/data/content/youtube-raw/VIDEO_ID" "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Output

- SRT file: `/opt/data/content/youtube-raw/VIDEO_ID.en.srt`
- Timestamped text with sequential numbering

## Convert SRT to Clean Transcript

```python
import re

with open('VIDEO_ID.en.srt') as f:
    content = f.read()

blocks = re.split(r'\n\n+', content.strip())
lines = []
for block in blocks:
    parts = block.split('\n')
    if len(parts) >= 3:
        timestamp = parts[1].split(' --> ')[0]
        text = ' '.join(parts[2:]).strip()
        h, m, s = timestamp.replace(',', '.').split(':')
        secs = int(h)*3600 + int(m)*60 + float(s)
        mm = int(secs // 60)
        ss = int(secs % 60)
        lines.append((mm, ss, text))

# Merge into ~1 minute chunks
paragraphs = []
current_chunk = []
current_min = 0
for mm, ss, text in lines:
    if mm != current_min and current_chunk:
        paragraphs.append((current_min, ' '.join(current_chunk)))
        current_chunk = []
        current_min = mm
    current_chunk.append(text)
if current_chunk:
    paragraphs.append((current_min, ' '.join(current_chunk)))

with open('VIDEO_ID_transcript.txt', 'w') as f:
    for mins, text in paragraphs:
        f.write(f'[{mins:02d}:00] {text}\n\n')
```

## Other Options

```bash
# List available subtitles
/opt/data/home/.local/bin/yt-dlp --list-subs "https://www.youtube.com/watch?v=VIDEO_ID"

# Download specific language
/opt/data/home/.local/bin/yt-dlp --write-auto-sub --sub-lang ja --sub-format srt --skip-download -o "OUTPUT" "URL"

# VTT format (includes positioning data)
/opt/data/home/.local/bin/yt-dlp --write-auto-sub --sub-lang en --sub-format vtt --skip-download -o "OUTPUT" "URL"

# Also download audio (for whisper transcription if no subs available)
/opt/data/home/.local/bin/yt-dlp -x --audio-format mp3 -o "/opt/data/content/youtube-raw/VIDEO_ID.%(ext)s" "URL"
```

## Pitfalls

- yt-dlp warning about missing JavaScript runtime is non-fatal — subs still download
- `en-orig` subtitle language exists for some videos (original language) vs `en` (translated)
- SRT file contains interleaved timestamp blocks — merge them for readable text
- Some videos genuinely have no subtitles (very rare for popular content)
- Save output to `/opt/data/content/youtube-raw/` to stay consistent with existing YouTube workflow
