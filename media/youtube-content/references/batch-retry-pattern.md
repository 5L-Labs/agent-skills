# Batch Retry Pattern

## Correct Approach: use the existing batch scripts

The repo contains multiple pre-built batch scripts. Use one rather than hand-rolling a fetch loop:

### `batch_fetch_retry.py` — retry videos with `_failed.txt` but no transcript

```bash
python3 /opt/data/content/batch_fetch_retry.py
```

- Collects candidates from `_failed.txt` entries with no matching `<VIDEO_ID>_transcript.txt`
- Only removes `_failed.txt` markers before retrying (does **not** delete existing transcript files)
- Parses and saves `_transcript.txt`, `_fulltext.txt`, `_meta.json` per video
- Writes `batch_results.json`

### `batch_reprocess.py` — re-segment from cached fulltext

When `batch_reprocess_transcripts.py` (or live fetch) fails, fulltext may already be cached.
This script resegments fulltext back into timestamped transcripts.

```bash
python3 /opt/data/content/batch_reprocess.py
```

### `batch_blocked_recheck.py` — full recheck from blocked pool

When all live fetch attempts return `SSLEOFError`, run the full recheck cycle:

```bash
python3 /opt/data/content/batch_blocked_recheck.py
```

It attempts live fetch; on failure falls back to fulltext recovery from `_fulltext.txt`.

## Incorrect pattern: clean-slate retry loop

```python
# WRONG — destroys existing recoverable data
for vid in candidates:
    for suffix in ("_transcript.txt", "_fulltext.txt", "_meta.json"):
        p = os.path.join(RAW, f"{vid}{suffix}")
        if os.path.exists(p):
            os.remove(p)  # DESTROYs any previously cached content
    # then re-fetch...
```

What goes wrong:
- If a prior run recovered a partial transcript (bytes on disk) and the new fetch fails with an IP block, that partial content is permanently lost.
- `_failed.txt` markers are useful provenance — deleting them loses the diagnostics.

Correct behaviour: inspect file size + contents first; only delete and re-fetch if the new return is demonstrably better.

## Recognizing cloud IP blocks

Three distinct error signals indicate the same thing — YouTube is blocking IPs from the current environment:

| Signal | Source | Meaning |
|---|---|---|
| Stderr: `SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING]')` | stderr via `fetch_transcript.py` or `yt-dlp` | YouTube terminates TLS at layer 3 |
| `yt-dlp`: `UNEXPECTED_EOF_WHILE_READING` TCP reset | stderr | Same block, no JSON wrapper |
| Bare JSON error in **stdout** with exit-rc 0 and **empty stderr** | stdout via `fetch_transcript.py --text-only --timestamps` | Script catches the SSL error and prints `{"error": "..."}`; exit code is 0; this can look like a successful fetch if you only check `rc` or stderr |

> **Silent error via `fetch_transcript.py`**: When YouTube blocks at the TLS layer, `fetch_transcript.py` with `--text-only --timestamps` can write `{"error": "Could not retrieve a transcript..."}` to **stdout** and exit 0 — no stderr, no nonzero exit code. The output looks like an unexpected payload. Always validate stdout: if it starts with `{"error"`, treat it as a real failure even if `rc` is 0. Do not save a "transcript" whose first 60 chars are `{"error":`.

When both `fetch_transcript.py` and `yt-dlp` fail with the same SSL error, the block is at the network level. Do not retry from the same environment.

## Session provenance

- `yt-backlog.json`: authoritative set of `unique_videos` (all known IDs)
- `playlist-new-ids.txt`: recent additions in `ID\tDONE` format
- `batch_fetch_retry.py candidates` = IDs with `_failed.txt` but no `_transcript.txt`
- `batch_reprocess.py CANDIDATES` = videos with `segs=-1` in `_meta.json` (largest fulltext first)
- `batch_blocked_recheck.py CANDIDATES` = videos with `_transcript.txt < 2 KB` and no home cache
