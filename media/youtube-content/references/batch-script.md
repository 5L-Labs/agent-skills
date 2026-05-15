# Batch Processing Script: `_process_youtube_batch.py`

**Purpose:** Implements the full YouTube transcript batch processing workflow described in the skill's "Batch Processing & State Reconciliation" section.

## Location

`$HERMES_HOME/content/_process_youtube_batch.py`
(e.g., `/opt/data/content/_process_youtube_batch.py`)

## Invocation

```bash
# Run directly
python3 /opt/data/content/_process_youtube_batch.py
```

The script reads from:
- Playlist: `$HERMES_HOME/content/playlist-new-ids.txt`
- Backlog: `$HERMES_HOME/content/yt-backlog.json`
- Raw directory: `$HERMES_HOME/content/youtube-raw/`

And uses:
- Python interpreter: `/opt/hermes/.venv/bin/python`
- Fetch script: `/opt/hermes/skills/media/youtube-content/scripts/fetch_transcript.py`

## Behavior

- Processes up to 10 videos per run
- Prioritizes retries: previously failed → incomplete → new playlist entries
- For each video: fetches transcript via `fetch_transcript.py`, saves transcript (`_transcript.txt`, timestamped, `[MM:SS]` format), full text (`_fulltext.txt`), and metadata (`_meta.json`) to raw dir
- On success: appends video_id to `yt-backlog.json` unique_videos and marks playlist line with "DONE"
- On failure (including network blocks): writes `_failed.txt` marker; video remains unprocessed and will be retried next run
- Prints a summary at exit with success/failure counts and processed IDs

## Caveats

- **No pre-flight connectivity check:** The script does not automatically check for cloud IP blocks. If the environment is blocked, all fetches will fail individually, creating many `_failed.txt` markers. Recommended: run `SKILL_DIR/scripts/test_youtube_connectivity.py` first; if blocked, skip running this script entirely and re-queue for ~48h.
- **Hardcoded paths:** The script contains hardcoded absolute paths tailored to the standard Hermes installation (`/opt/data/`, `/opt/hermes/.venv`). If your HERMES_HOME differs, edit the script variables at the top.
- **Data format expectations:** Parses `fetch_transcript.py` output as JSON with keys `video_id`, `segment_count`, `duration`, `timestamped_text`, `full_text`. If output format changes (e.g., flag changes), parsing will fail.
- **No large-transcript chunking:** For transcripts >50K characters, the script saves the entire output; it does not chunk or summarize.