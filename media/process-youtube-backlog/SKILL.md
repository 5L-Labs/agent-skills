---
name: process-youtube-backlog
description: >
  Process YouTube videos from a backlog by fetching transcripts, generating Luna-style digests,
  and updating backlog files. Designed for cron job execution to process multiple videos
  sequentially, handling failures gracefully.
---
# YouTube Backlog Processor

Process YouTube videos from backlog files by fetching transcripts, generating structured digests,
and updating both text and JSON backlog files to remove successfully processed videos.

## Workflow

1. **Read backlog**: Get first N video IDs from `/opt/data/.hermes/content/yt-latent-space-backlog.txt`
2. **For each video ID**:
   - Fetch transcript using `fetch_transcript.py` with `--text-only --timestamps`
   - If fetch fails (returns JSON error), skip video and continue to next (do NOT remove from backlog)
   - If fetch succeeds:
     - Save timestamped transcript to temporary file
     - Generate Luna digest using `generate_luna_digest.py`
     - Save digest to `/opt/data/.hermes/content/youtube-raw/VIDEO_ID.txt`
     - Remove video ID from both backlog files:
      - TXT backlog: Remove line ending with `|VIDEO_ID` using Python (not awk/sed — see Lessons Learned)
      - JSON backlog: Remove `VIDEO_ID` from `unique_videos` array using Python
3. **Report**: Output the full digests for successfully processed videos

## Error Handling\n\n- **Transcript fetch failure** (JSON error, disabled transcripts, etc.):\n  - Log error but continue processing other videos\n  - Do NOT remove failed video from backlog (allows retry later)\n- **Digest generation failure**:
  - Log error but continue processing other videos.
  - Do NOT remove video from backlog.
  - **Fallback**: If `generate_luna_digest.py` fails (sparse/no output), use Python to strip `M:SS` timestamps from the `_timestamped.txt` file, concatenate text into sentences, filter for length > 20 chars, and format as Luna-style bullets (•/◦).
\n- **Backlog update failure**:\n  - Log error but continue (video may be processed again, but digest file exists)\n  - **Text backlog update**: Use `awk -F'|' '!($NF ~ /VIDEO_ID/)'` to filter out processed IDs and renumber sequentially\n  - **JSON backlog update**: Use Python's json module to parse, modify `unique_videos` array, and rewrite file (since `jq` may not be available)\n\n## Lessons Learned\n\\n1. **Always check transcript availability first** before removing videos from backlog\\n2. **Some videos may have partial transcripts** - validate non-empty output\\n3. **Cloud IP blocking is common** - have fallback strategies ready\\n4. **Maintain both backlog formats in sync** - remove from both files atomically\\n5. **Enhance digests with context** - raw Luna output benefits from titles and URLs\\n6. **Numbering in text files** - renumber sequentially after removals, don't preserve original numbers\\n7. **Digest generation script issues**: The provided generate_luna_digest.py has regex pattern errors (single vs double backslashes) that prevent it from working. Workaround: Create a custom digest function or fix the script's regex patterns.\\n8. **Fallback digest approach**: When generate_luna_digest.py fails, implement a simple fallback: strip timestamps, extract sentences, format as Luna-style bullets with • for main points and ◦ for sub-points.\\n9. **Validation is critical**: Always check that transcript fetch succeeded (not JSON error) and that digest generation produced non-empty output before considering a video processed.\\n10. **Temporary file management**: Always clean up temporary files used for transcript storage during digest generation.\\n11. **Pre-existing digests**: Check if digests already exist in the output directory before reprocessing to save time and avoid rate limits

## Scripts Used

- `/opt/data/skills/media/youtube-content/scripts/fetch_transcript.py`
- `/opt/data/skills/media/youtube-content/scripts/generate_luna_digest.py`

## Environment

Designed to run in Hermes environment with:
- Python virtual environment at `/opt/hermes/.venv`
- Backlog files in `/opt/data/.hermes/content/`
- Output directory: `/opt/data/.hermes/content/youtube-raw/`

## Usage in Cron Job

This skill is intended to be used as part of a cron job prompt that specifies:
- Number of videos to process (e.g., first 2)
- Backlog file paths
- Output directory for digests

See the cron job prompt that invokes this skill for exact parameter usage.