# Batch Fetch Conventions — Verified Reality

## Canonical save directory

The authoritative store is `/opt/data/content/youtube-raw/`.  
Do not use `/opt/data/.hermes/content/youtube-raw/` — the latter path does not contain
any fetched artifacts in this environment and was a legacy reference that should be
silently replaced wherever the skill still points there.

Artifacts per video:
- `{id}_transcript.txt` — timestamped, `[MM:SS] text` per line
- `{id}_fulltext.txt` — plain fulltext joined into one file + newline
- `{id}_meta.json` — id, title, segments_count, duration_seconds

### Naming note

Video IDs in `yt-backlog.json.unique_videos` may include a leading hyphen or other
prefix vs the transcript filename. Always check filesystem existence by substring, not
exact match.

---

## Backlog JSON — required fields

```jsonc
{
  "unique_videos": ["VID1", "VID2", ...],
  "failed_videos": [
    {
      "video_id": "VID1",
      "note": "Free-text reason — used verbatim in the transcript filename as the _error.txt content.",
      "status": "confirmed_permanent" | "retryable"
    }
  ],
  "last_updated": "RFC3339 UTC string, e.g. 2026-05-25T12:00:00+00:00"
}
```

### `last_updated`

Update `last_updated` to UTC on every batch run — even runs that produced zero new fetches.
This prevents ambiguity about how stale the backlog state is.

---

## Source-reading precedence (unambiguous)

Parse in this order; every step is a hard filter applied before the next:

1. **Skipped-by-mark** — `playlist-new-ids.txt` lines ending `\tDONE` → skip permanently.  
2. **Conf-perm** — entries in `yt-backlog.json.failed_videos` with `"status": "confirmed_permanent"` → skip permanently.  
3. **Already-done** — IDs in `yt-backlog.json.unique_videos` → skip; these are already fetched.  
4. **File-on-disk** — `grep -q "{id}_transcript\\.txt$" ls /opt/data/content/youtube-raw/` → skip; idempotent save in place.  
5. **Fill-missing-requeue** — `yt-backlog.json.unique_videos` entries that lack both `{id}_fulltext.txt` and `{id}_meta.json` → do NOT re-fetch; reconstruct those two files from the existing transcript and add them to the list.

**Intersection rule**: "already-done from step 3" and "file-on-disk from step 4" can overlap;
a video in `unique_videos` may still be missing from the raw directory. Treat it as missing
only if the transcript file is absent on disk — do not skip filling in a missing artifact.