# 2026-05-16 Batch Run: Latent Backlog Deep-Dive

## Environment state at run start

- Playlist (`playlist-new-ids.txt`): all 10 items DONE — no new entries
- `yt-backlog.json`: 90 unique_videos, 18 failed_videos
- Latent backlog (`~/.hermes/content/yt-latent-space-backlog.txt`): 99 lines, 63 DONE, 36 unmarked
- Canonical raw dir (`/opt/data/content/youtube-raw/`): 94 `_meta.json` files present

## Candidates selected

10 unmarked, non-permanent-failed IDs from latent backlog:

```
7UGjf080qag  IYrO9h4KYZc  XquVJ-v0ML4  _IlTcWciEC4  djIKPkw0gYY
Y0Hlizumgpw  2fDBeMu6xjk  8UDj3-JDfYY  HQucglw-4t8  XLGESVZQA2o
```

`8UDj3-JDfYY` and `HQucglw-4t8` were **already** in `failed_videos` (confirmed_permanent) — should have been excluded before fetch attempts.

`XLGESVZQA2o`: `yt-dlp` returned null/empty JSON — private/deleted → confirmed_permanent.

## Root cause: timedtext block confirmed on all remaining candidates

All 8 remaining video IDs:
- Return valid metadata via `yt-dlp --dump-single-json` ✓ (terminal() network)
- Have `automatic_captions["en"]` in the JSON ✓
- Have **zero** chapters
- All signed `api/timedtext` URLs return Google "Sorry…" CAPTCHA block page (every format: json3, srv1-3, ttml, vtt, srt)
- `yt-dlp --write-auto-subs` silently writes zero VTT files
- This is the **hermes-proxy MITM**: proxy allows watch page (HTTP 200) but injects block page on `api/timedtext` requests

## Script landscape found

| Script | Location | Status |
|---|---|---|
| `SKILL_DIR/scripts/fetch_transcript.py` | skill script | Already patched to `.fetch()` ✓ |
| `SKILL_DIR/scripts/_fetch_latent_videos.py` | skill script | Working, uses `automatic_captions` directly |
| `SKILL_DIR/scripts/chapter_fallback_batch.py` | skill script | Works for post-fetch chapter processing |
| `scripts/fetch_remaining_v3.py` | `/opt/data/content/scripts/` | Project-specific copy; had `requested_subtitles` list bug |

**Key difference**: `fetch_remaining_v3.py` iterates `subtitles.items()` — fails when value is a `list`. Skill's `_fetch_latent_videos.py` avoids this by using `automatic_captions` directly, no `requested_subtitles` loop.

## Pitfalls encountered

### 1. `requested_subtitles` can be a `list` → `AttributeError`

`yt-dlp` returns `data["requested_subtitles"]` as a **list** (not dict) in some version/video combos. Fixed in `fetch_remaining_v3.py` with type guard. Documented in SKILL.md pitfalls.

### 2. `execute_code` subprocess network failure

All `execute_code`-spawned Python subprocess calls to YouTube returned `exit=1` with empty/null stdout. `terminal()` same commands worked. **Key rule: rewrite as terminal()-invoked script**.

### 3. Chapter fallback count discrepancy

`_fetch_latent_videos.py` calls `fmt_ts(ch.get("start_time", 0))`. For a ~29-minute vid, `int(29*60+14) = 1754`; `h=1754//3600=0` → `m=29, s=14` → `29:14` (MM:SS). Correct behavior confirmed — `chapters` fallback times are MM:SS format.
