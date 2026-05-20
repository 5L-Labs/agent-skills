# Inline Re-segmentation Fallback

Use this when `recover_stubs.py` is absent or hard-coded batch IDs are exhausted.
It re-segments cached `_transcript.txt` + `_fulltext.txt` into corrected `_meta.json`.

## Pre-conditions (one-liner check)

```python
import os
path=lambda vid,f: f"/opt/data/content/youtube-raw/{vid}_{f}"
ok=lambda v: (os.path.exists(path(v,"transcript.txt")) and
              os.path.exists(path(v,"fulltext.txt")) and
              os.path.getsize(path(v,"fulltext.txt")) >= 500)
```

## Full Re-segmentation Fragment

```python
import os, re, json
from datetime import datetime, timezone

RAW_DIR  = "/opt/data/content/youtube-raw"
BACKLOG  = "/opt/data/content/yt-backlog.json"
LATENT   = "/opt/data/.hermes/content/yt-latent-space-backlog.txt"

TOP10 = [ ... ]   # sorted by _fulltext.txt size, descending

def sec_to_mmss(secs):
    """Convert seconds → [MM:SS] or [HH:MM:SS] string."""
    if secs < 3600:
        return f"{int(secs)//60}:{int(secs)%60:02d}"
    h, rem = int(secs)//3600, int(secs)%3600
    return f"{h}:{rem//60:02d}:{rem%60:02d}"

def ts_to_sec(ts_str):
    """Parse M:SS / MM:SS / H:MM:SS string → int seconds.
    H > 24 → minutes-first (podcast notation e.g. 26:46 = 26 min).
    Pad-zero variants like 0:00 or 00:00 also handled."""
    parts = ts_str.split(":")
    if len(parts) == 2: return int(parts[0])*60 + int(parts[1])
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return m*60+s if h > 24 else h*3600+m*60+s

# ── Three-part timestamp detector ────────────────────────────────────────────
# Priority order on each line: [M:SS] → MM:SS:-N(noise) → MM:SS
#
#  Pattern 0: [MM:SS] Chapter Title            → ts_bracket_re
#  Pattern 1: MM:SS:-N Chapter Title  (tIVKgztDaYQ corrupted stub) → ts_corrupt_re
#  Pattern 2: MM:SS Chapter Title              → ts_unbracket
#
# CRITICAL: Do NOT use \b before ] or : when matching [MM:SS] or MM:SS.
# The \b between a digit and ]/: is ambiguous and can cause silent non-matches
# for lines like [0:00] Chapter Title — the \b after 0 before ] fails because
# `:` is not a word character, breaking the \b anchor. Use character-class
# alternation: (?:]|\s|:|$) instead of \b.
# ─────────────────────────────────────────────────────────────────────────────
ts_bracket   = re.compile(r'^\[?(\d{1,2}:\d{2}(?::\d{2})?)(?:]|\s|:|$)\s*(.+)$')
ts_corrupt   = re.compile(r'^(\d{1,2}:\d{2}):-\d+\s+(.+)$')   # tIVKgztDaYQ offset
ts_unbracket = re.compile(r'^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$')

def parse_ts_line(line):
    """Return (secs, text).
    Non-timestamp lines → (0, line_text).
    ⚠️  Always returns a tuple, never None — callers must check `if secs > 0:`
        NOT `if parsed:` because 0 seconds IS a valid timestamp (0:00 headings)."""
    for pat in (ts_bracket, ts_corrupt, ts_unbracket):
        m = pat.match(line)
        if m: return ts_to_sec(m.group(1)), m.group(2).strip()
    return 0, line   # bare text line

def compute_duration_with_wraps(timestamped_secs_list):
    """Correct duration for pad-zero MM:SS transcripts that loop every 60 min.
    
    When a video uses MM:SS formatting without hours, timestamps wrap from
    59:59 → 00:00 every hour. The naive formula `last_raw_secs + 30` undercounts
    by N×3600 seconds for each wrap detected.
    
    Returns corrected duration in seconds (last-seen absolute time + 30 s buffer)."""
    total_added_secs = 0
    for i in range(1, len(timestamped_secs_list)):
        if timestamped_secs_list[i] < timestamped_secs_list[i-1]:
            # Wrap detected: previous minute was higher, current is lower.
            # Calculate the difference as full hours added.
            # Use the gap at second resolution if available.
            total_added_secs += 3600  # one full hour-wraparound per wrap event
    return timestamped_secs_list[-1] + total_added_secs + 30

# ── RE-SEGMENT from _fulltext.txt (cache-first only) ─────────────────────────
# Source: _fulltext.txt — NOT _transcript.txt — because the former is the
# authoritatively cached plain-text copy. _transcript.txt may be 0 B or absent.
# Read fulltext, parse timestamped lines with parse_ts_line(),
# then write BOTH _transcript.txt and _fulltext.txt at the end.
# ─────────────────────────────────────────────────────────────────────────────
for vid in TOP10:
    ft_p   = f"{RAW_DIR}/{vid}_fulltext.txt"
    tx_p   = f"{RAW_DIR}/{vid}_transcript.txt"
    meta_p = f"{RAW_DIR}/{vid}_meta.json"
    ts_p  = f"{RAW_DIR}/{vid}_transcript.txt"
    ft_p  = f"{RAW_DIR}/{vid}_fulltext.txt"
    meta_p= f"{RAW_DIR}/{vid}_meta.json"

    with open(ts_p, errors="replace") as f: ts_lines = f.readlines()
    with open(ft_p, errors="replace") as f: ft_lines = f.readlines()

    seg_count, last_sec = 0, 0
    norm_ts, full_parts = [], []
    ts_secs_list = []   # raw seconds of each timestamped line (for wrap detection)

    for line in ts_lines:
        raw = line.rstrip("\n").strip()
        if not raw: continue
        m = ts_re.match(raw) or brack_re.match(raw)
        if m:
            ts_str = m.group(1)
            text   = m.group(3) if ts_re.match(raw) else m.group(2)
            norm_ts.append(f"[{ts_str}] {text}")
            seg_count += 1
            last_sec = max(last_sec, parse_ts_sec(ts_str))
            ts_secs_list.append(ts_to_sec(ts_str))
            full_parts.append(text)
        else:
            full_parts.append(raw)

    if seg_count == 0:
        print(f"  !! {vid}: no parseable timestamps"); continue

    # ⚠️  Do NOT use last_sec + N for duration when timestamps use MM:SS
    # without hour field — they will wrap at 60:00 and last_sec only captures
    # one lap. Use compute_duration_with_wraps() instead.
    duration = compute_duration_with_wraps(ts_secs_list)

    # write normalised transcript
    with open(ts_p, "w") as f:
        f.write("\n".join(norm_ts) + "\n")

    # write clean fulltext
    with open(ft_p, "w") as f:
        f.write("\n".join(full_parts) + "\n")

    # update meta
    meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    meta.update({
        "video_id": vid, "segments": seg_count, "duration": duration,
        "source": "COHERENT_FULLTEXT_RESEQUENCED",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })
    with open(meta_p, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # ── update queues ─────────────────────────────
    # (write raw files first, then queues — never reverse)
    queue = {v["video_id"]: i for i, v in enumerate(backlog.get("unique_videos", []))}
    ...
| IPC write-order | transcript → fulltext → meta.json → backlog → latent DONE |
