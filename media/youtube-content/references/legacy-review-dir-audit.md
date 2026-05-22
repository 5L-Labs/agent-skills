# Legacy Review Dir Audit Pattern

## What it is

`/opt/data/content/youtube-raw/` is the **pre-`.hermes` batch output directory**. Many videos from older runs were written here before the primary path `/opt/data/.hermes/content/youtube-raw/` was adopted.

**Do not treat it as a low-priority fallback.** In practice it is the richest single source of untransferred transcript data. A video that is absent from primary and home-cache often has a complete, valid transcript sitting in the review dir.

## When to hit it

During a batch run, after checking:
1. `/opt/data/.hermes/content/youtube-raw/` (primary — this run's current output)
2. `/opt/data/home/.hermes/content/youtube-raw/` (home-cache — pre-fetched from home-IP)

If neither has a valid transcript (existence + >500 B + valid timestamped first line), **check the review dir before doing a live fetch**. A valid transcript here is as authoritative as one from primary.

## Detection

```python
REVIEW = Path("/opt/data/content/youtube-raw")
r_t = REVIEW / f"{vid}_transcript.txt"
if r_t.exists() and r_t.stat().st_size > 500:
    first_line = r_t.open("rb").read(120).decode("utf-8", errors="replace")
    if re.match(r'^[\[0-9]', first_line.strip(), re.UNICODE):
        # Valid transcript — use it
```

## Transfer protocol (all three files)

When a review dir transcript is used:

1. Copy `*_transcript.txt` to primary dir
2. Strip timestamps → write `*_fulltext.txt` to primary dir
3. Generate proper meta with canonical keys → write `*_meta.json` to primary dir
4. **Sync home-cache** — redefine `<VIDEO_ID>.txt`, `<VIDEO_ID>_fulltext.txt`, `<VIDEO_ID>_meta.json` using home-cache naming convention

This turns a review dir artifact into a proper primary + home-cache entry, preventing re-fetch on future runs.

## Naming convention

Review dir uses `{VIDEO_ID}_transcript.txt` (with underscore). Home cache uses `{VIDEO_ID}.txt` (no underscore prefix). Both must be kept in sync.
