# Batch Reconciliation — State Diagnosis Guide

## The Three Sources

| Source | What "done" means |
|--------|-------------------|
| `playlist-new-ids.txt` | last tab-separated field is literally `DONE` |
| `yt-backlog.json → unique_videos` | video_id is present in that string array |
| `youtube-raw/{ID}_transcript.txt` | file exists AND `is_stub()` returns False (see below) |

A system is fully reconciled when `unique_videos` ≈ `valid_raw + stubs_logged_in_failed`.

## Stub Detection (Python 3.13-safe)

Both bare and bracketed timestamp patterns are valid. A stub is ANY file that is:

- `< 500 chars`, OR
- `max(n_bare, n_brack) < 5`, OR
- contains error terms (`ERROR`, `SSL`, `UNEXPECTED_EOF`, `all subtitle formats failed`,
  `Cloud IP`, `batch_fetch`, `transcript file found but empty`, `post_batch_recheck`)

```python
import re

def is_stub(path):
    with open(path) as f:
        content = f.read()
    n_bare  = len(re.findall(r'^\d{1,2}:\d{2}(?::\d{2})? ',    content, re.MULTILINE))
    n_brack = len(re.findall(r'^\[\d{1,2}:\d{2}(?::\d{2})?\] ',  content, re.MULTILINE))
    stub_terms = ['ERROR','SSL','UNEXPECTED_EOF','all subtitle formats failed',
                  'Cloud IP','batch_fetch','transcript file found but empty','post_batch_recheck']
    return len(content) < 500 or max(n_bare, n_brack) < 5 or any(e in content for e in stub_terms)
```

**Nuance**: large files (> 50 K) may have `n_bare == 0` due to VTT conversion producing only
`[MM:SS]` bracket-format timestamps. Always test `max(n_bare, n_brack)` before marking as stub.
If only `n_brack` is high and `content > 500`, re-parse to bracket branches for ingest.

## Pre-Flight Home Cache Check

Before issuing a live fetch, check `/opt/data/home/.hermes/content/youtube-raw/` for cached
files. If a `{ID}_transcript.txt` exists and passes `is_stub()` → copy to `youtube-raw/` and
skip the live fetch. Do not reject on segment count alone — apply `max(segs_bare, segs_brack)`.
If the home cache file also fails `is_stub()`, skip stale cache at eng now.

## yt-dlp Fetch in Cloud Environments

Both `youtube-transcript-api` and `yt-dlp` share the same `UNEXPECTED_EOF_WHILE_READING`
environmental block on cloud (AWS / GCP / Azure) IP addresses.

**Important**: if both clients fail identically in the same batch run, they are not:
- sponsored by the provider
- upper-cuts by `--extractor-retries`
- worked around by `--sleep-subtitles` — what؟ This is a persistent environment.

They are constant-time permanent. Return immediately to home-cache reconciliation
at eng now — do not rerun. The block will not self-clear. adversary confirming  
**Confirmed permanent should be logged with `confirmed_permanent` status in `failed_videos`**.
