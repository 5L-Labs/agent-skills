# Batch Fetch Conventions (youtube-content)

## Source files

| File | Purpose |
|------|---------|
| `/opt/data/content/playlist-new-ids.txt` | Master video ID list. Lines have leading spaces for tabular alignment (from numbered export). **Actual format**: `{COUNTING_NUM}\|{VIDEO_ID}\t{DONE}` (e.g. `    1|-gE1cesJF9M\tDONE`). New entries appear without `\tDONE`. Parse by splitting on the first tab character; the text before the tab is the video ID (strip any leading digits and `|` prefix before storing). |
| `/opt/data/content/yt-backlog.json` | JSON backlog. Fields: `unique_videos` (array of strings), `failed_videos` (array of `{video_id, status, note}`), `last_updated`. |
| `/opt/data/content/youtube-raw/` | Output directory. Files: `{id}_transcript.txt`, `{id}_fulltext.txt`, `{id}_meta.json`. |

## Pick strategy (next batch)

1. Parse `playlist-new-ids.txt`. Collect video IDs where `\tDONE` is NOT present.
2. Cross-check against `yt-backlog.json.unique_videos` — skip any already there.
3. Cross-check against `yt-backlog.json.failed_videos` — skip any with `confirmed_permanent`.
4. Check filesystem: if `{id}_transcript.txt` exists, skip (idempotent).
5. Take up to N (default 10) remaining items.
6. Proceed to fetch.

## Update after fetch

- Write `{id}_transcript.txt` (timestamped, `[MM:SS] text`)
- Write `{id}_fulltext.txt` (plain text, joined)
- Write `{id}_meta.json` (id, title, segments, duration, source, fetched_utc)
- Append `\tDONE` to the line in `playlist-new-ids.txt`
- Add `id` to `yt-backlog.json.unique_videos`
- Increment `yt-backlog.json.last_updated` to `UTC now`

## Recovering previously-failed videos

Move IDs from `failed_videos` → `unique_videos` when a previously-blocked video now fetches successfully (e.g. `yt-dlp` IP unblocked between runs). Do NOT delete `failed_videos` entries; leave updated `note` fields so future sessions know the history.
