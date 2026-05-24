# Batch audit state check (corrected)

`reconcile_batch_state.py` can report `valid=0, stubs=0` due to a glob bug on its line 49
(`f'{RAW_DIR}*_transcript.txt'` instead of `os.path.join(RAW_DIR, '*_transcript.txt')`).
When that happens, run this script to get the real numbers before re-processing.

## Usage

```bash
python3 SKILL_DIR/scripts/audit_raw_state.py
```

## Expected output shape

```
=== CORRECTED Fast-Audit Table ===
Source                                  Count  What done means
----------------------------------------------------------------------
playlist-new-ids.txt                       N    last field == DONE
yt-backlog.json unique_videos              N    video_id in array
youtube-raw/ (valid, non-stub)             V    pass is_stub()
youtube-raw/ (stub files)                  S    fail is_stub()

Raw transcript files detected: V + S
Playlist DONE entries:                    N
Backlog unique_videos:                    N

Three-way agree (playlist=backlog=raw+cp+cp-no-raw): True/False
  → proceed with backlog processing / nothing to do
```

A fully-reconciled healthy state shows `playlist=backlog=valid+stubs+cp_no_file`.

## Canonical raw-state partition (stable across runs)

Every `bl_vids` ID falls into exactly one of these buckets:

| Bucket | Meaning | Action |
|--------|---------|--------|
| `valid_raw` (V) | `_transcript.txt` file exists and passes `is_stub()` | DONE in batch; skip |
| `stub_raw ∩ fail_vids` (S) | File exists but is a stub; logged as `confirmed_permanent` in `failed_videos` | DONE; skip |
| `cp_no_file` (C) | In `fail_vids` as `confirmed_permanent` but no `_transcript.txt` file on disk at all | DONE; skip |
| `not_in_fail_vids` (U) | Not in `unique_videos` at all or not yet attempted | Fetch if unprocessed |

If `V + S + C + U == len(bl_vids)` and `U == 0` the batch is fully reconciled.
