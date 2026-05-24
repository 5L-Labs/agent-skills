# Timestamp Format Notes

## Two valid formats

All saved `_transcript.txt` files can legitimately use either:

| Format | Example | Source |
|--------|---------|--------|
| Bare `MM:SS text` | `0:00 Introduction ...` | `fetch_transcript.py` via `youtube-transcript-api` |
| Bracketed `[HH:MM] text` | `[00:00] I entered venture ...` | VTT → converted by `yt-dlp`/legacy pipeline |

## Counting segments or detecting timestamps

Test both patterns — use `max(segs_bare, segs_brack)`:

```python
import re
n_bare  = len(re.findall(r'^\d{1,2}:\d{2}(?::\d{2})? ', text, re.MULTILINE))
n_brack = len(re.findall(r'^\[\d{1,2}:\d{2}(?::\d{2})?\] ', text, re.MULTILINE))
seg_count = max(n_bare, n_brack)
```

## Stripping timestamps (fallback digest)

```python
import re
def strip_ts(line):
    return re.sub(r'^(\[\d{1,2}:\d{2}(?::\d{2})?\]\s*|\d{1,2}:\d{2}(?::\d{2})?\s+)', '', line).strip()
```

Try bare first, then bracket pattern; if both fail treat as no timestamps.

## VTT → timestamped text conversion

VTT uses `HH:MM:SS.mmm --> HH:MM:SS.mmm` or `MM:SS.mmm --> MM:SS.mmm`.
When parsing, hours ≥ 10 are always `H:MM:SS`; otherwise `MM:SS`.

For details and known edge-cases, see `references/vtt-parsing.md` (if present in skill).
