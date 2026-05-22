# Home-Cache Recovery

## What it is

`/opt/data/home/.hermes/content/youtube-raw/` is the default fallback directory used by the `batch_blocked_recheck.py` script. It stores transcripts recovered from a previous home-IP / non-cloud fetch cycle, durably persisting across cloud-IP-blocked environments.

## Paths

| Scope | Path |
|---|---|
| Primary output dir | `/opt/data/.hermes/content/youtube-raw/` |
| **Home-cache recovery source** | `/opt/data/home/.hermes/content/youtube-raw/` |
| Legacy review dir | `/opt/data/content/youtube-raw/` |

## When to use it

- Cloud IP is blocking all live `fetch_transcript.py` requests (SSLEOFError / UNEXPECTED_EOF_WHILE_READING / JSON error in stdout with rc=0)
- `batch_blocked_recheck.py` was run previously and populated the home-cache, but the primary output dir has no transcript for this video
- You have pre-fetched transcripts from a machine not running on a cloud IP

## Recovery pattern (batch)

```python
# Check three locations in priority order
for dir in [
    "/opt/data/.hermes/content/youtube-raw/",
    "/opt/data/home/.hermes/content/youtube-raw/",
    "/opt/data/content/youtube-raw/",
]:
    tf = f"{dir}{vid}_transcript.txt"
    if os.path.exists(tf) and os.path.getsize(tf) > 500:
        with open(tf) as f:
            first = f.readline().strip()
        if re.match(r'^\[?\d{1,2}:\d{2}\]?\s', first):
            src = tf  # use this source
            break
```

## Recovering via batch_blocked_recheck.py

```bash
python3 /opt/data/content/batch_blocked_recheck.py
```

This script will populate the home-cache with newly recovered transcripts. After it runs, copy entries from the home-cache to the primary output dir so future batch runs don't need to find them again.

## Caveats

- The home-cache may contain entries already in `yt-backlog.json` `unique_videos` from a prior recovery. Always deduplicate against `unique_videos` before committing.
- The home-cache files are named `<VIDEO_ID>_transcript.txt` and use the same timestamped-line format as `fetch_transcript.py --text-only --timestamps`.
- If the home-cache file was produced by `yt-dlp` batch tooling, it may use a different timestamp format (hours column: `6:00 1:20:58`). The normalize function in `batch_reprocess.py` handles this; if reading manually, the regex `^\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*` will match both `MM:SS` and `HH:MM:SS` formats.
