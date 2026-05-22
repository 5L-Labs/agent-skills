# Meta JSON Schema

## Canonical keys (use these for all new writes)

```json
{
  "video_id": "abc123XYZ",
  "segments_count": 42,
  "duration_seconds": 1847
}
```

| Key | Type | Description |
|---|---|---|
| `video_id` | string | YouTube video ID |
| `segments_count` | int | Number of timestamped transcript lines/segments |
| `duration_seconds` | int | Duration in wall-clock seconds (max timestamp in the transcript) |

## Legacy keys seen in existing files (do not use in new writes)

| Legacy key | Replaced by | Seen in |
|---|---|---|
| `segments` | `segments_count` | Partial recovery files from early 2026 runs |
| `duration` | `duration_seconds` | Same early recovery files |

When reading legacy files, normalise keys:
```python
segments = meta.get("segments_count") or meta.get("segments", 0)
duration = meta.get("duration_seconds") or meta.get("duration", 0)
```

## Duration computation (write_meta pattern)

Duration is the wall-clock time of the last segment, **not** the count × segment-size. It should be calculated from actual timestamp values:

```python
duration = 0
for line in transcript_lines:
    m = re.match(r'^\[?(\d+):(\d{2})(?::(\d{2}))?\]?\s*(.*)', line)
    if m:
        hrs  = int(m.group(3)) if m.group(3) else 0
        mins = int(m.group(1))
        secs = int(m.group(2))
        ts   = hrs * 3600 + mins * 60 + secs
        duration = max(duration, ts)
```

For hour-column timestamps (e.g., `6:00 1:20:58`) the regex anchor must allow three-digit hour groups. The pattern used in `batch_reprocess.py` handles this; the write helper regex used in this skill does not yet match `H:MM:SS` without brackets — see `batch_reprocess.py` for the full pattern.
