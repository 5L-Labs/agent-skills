# Batch Script Guard Behaviour (2026-05-19 session)

## `batch_fetch.py` — resume vs normal mode

| Mode | `known_unique` source | Dedup guard active? |
|---|---|---|
| `--resume` | Loaded from `yt-backlog.json` (unique_videos ∪ failed_videos) | ✅ Yes |
| default (no flag) | `set()` — empty | ❌ No |

`known_unique` is checked in the `video_id in known_unique` guard before each
fetch attempt. In resume mode a failed-video entry in `failed_videos` will also
suppress re-fetch; in normal mode those entries do not suppress anything.

**Decision point at call time**: pass `--resume` when the batch run should
respect every entry already in `yt-backlog.json`. Inline re-segmentation always
respects both buckets regardless of mode.

## `_meta.json` dual field pitfall

Older stubs (chapter-outline partial writes, `source: chapter_outline_ip_blocked`)
store segment count in `segment_count`, not `segments`. `segments` is `null`.

When building the candidate list inline:
```
meta.get("segments")          # preferred — primary field
meta.get("segment_count")     # fallback when segments is null
```
If `segment_count > 0` the stub already has real segment data even if `segments`
is null. Do not re-segment such a stub unless `_fulltext.txt` changed and
`segments` must be normalised to the standard format.

## `batch_fetch_candidates.py` — hard-coded ID exhaustion (2026-05-19)

The 4 baked-in IDs (`TZGVB6L_2Eo`, `yYZBd25rl4Q`, `-gE1cesJF9M`,
`-uiF1txQxV8`) returned SSHLEOFError / IP-block within <1 s every call.
They are present as `failed_videos` entries in `yt-backlog.json` (status:
`blocked_recheck` or `confirmed_permission`) but were never removed from
`CANDIDATES`. Expected output: "Candidates processed: 0" with 4 ✗ lines.

Do not patch or deprecate `batch_fetch_candidates.py`; just fall through to
inline cache-first scan (Pipeline Steps §5) when it returns 0.
