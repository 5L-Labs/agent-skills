# YouTube Batch Processing Session - 2026-04-16

This session processed 10 YouTube videos from the backlog. Key steps, discoveries, and troubleshooting are documented here for future reference.

## Session Overview

- **Goal**: Process 10 videos from the backlog as a cron job
- **Outcome**: 9/10 videos successfully fetched and digested, 1 skipped (already existed)
- **Backlog reduced**: 204 → 194 videos
- **Duration**: ~28 seconds

## Detailed Workflow

### 1. Initial Setup Discovery
- Found that `/usr/bin/python3` already had `youtube-transcript-api` installed
- This avoided the need to create a temporary venv
- **Lesson**: Always check system Python first before attempting venv creation

### 2. Script Location
- Primary script: `/opt/data/.hermes/skills/media/youtube-content/scripts/fetch_transcript.py`
- Digest script: `/opt/data/skills/media/youtube-content/scripts/generate_luna_digest.py`
- **Tip**: Use `find /opt/data -name "fetch_transcript.py" -type f` if scripts aren't where expected

### 3. Processing Steps
For each video:
1. Check if transcript already exists in `/opt/data/.hermes/content/youtube-raw/`
2. Fetch with `--text-only --timestamps`
3. Save raw transcript
4. Generate Luna digest
5. Append to summary file
6. Update backlog JSON

### 4. Backlog Update Logic
- File: `/opt/data/.hermes/content/yt-backlog.json`
- Structure: `{"unique_videos": [video_id1, video_id2, ...]}`
- After processing, remove video IDs from the `unique_videos` array
- This reduces the backlog for future runs

## Troubleshooting & Discoveries

### A. Python Environment Issues
**Problem**: `/opt/hermes/.venv/bin/python3` lacked `youtube-transcript-api` and had no `pip`.
**Solution**: Used `/usr/bin/python3` which already had the package installed.

### B. Script Location Variability
**Problem**: `generate_luna_digest.py` not found at expected path.
**Solution**: Searched multiple possible locations; found at `/opt/data/skills/media/youtube-content/scripts/generate_luna_digest.py`.

### C. Naming Mismatch in Backlog
**Discovery**: Video IDs in backlog JSON (e.g., `b80by3Xk_A8`) may not exactly match transcript filenames due to prefixes/suffixes.
**Workaround**: Check for substring existence when verifying if a transcript already exists.

### D. Existing Transcript Detection
**Problem**: The script initially tried to fetch `b80by3Xk_A8` even though a transcript already existed.
**Fix**: Added explicit check before fetching: if `/opt/data/.hermes/content/youtube-raw/<name>.txt` exists, skip fetching.

### E. Digest Script Fallback
**Edge case**: If `generate_luna_digest.py` completely fails (not just empty output), create a basic fallback digest:
```python
with open(transcript_file, 'r') as f:
    lines = f.readlines()
text = ' '.join([line.split(' ', 1)[-1] for line in lines if line.strip()])
digest = f"• Core concept: {text[:100]}...\n• Key points extracted from transcript.\n"
```

## Key Learnings

1. **Always check system Python first** for `youtube-transcript-api` before creating venvs.
2. **Check for existing transcripts** before fetching to avoid duplicates and save API calls.
3. **Update the backlog JSON** after each successful fetch to keep it current.
4. **Handle script location variability** by knowing the multiple possible install paths.
5. **Implement complete fallback** for digest generation if the script is unavailable.

## Commands Reference

```bash
# Check if youtube-transcript-api is available
python3 -c "import youtube_transcript_api; print('OK')"

# Find fetch_transcript.py
find /opt/data -name "fetch_transcript.py" -type f

# Process a single video (manual)
python3 /path/to/fetch_transcript.py "URL" --text-only --timestamps
python3 /path/to/generate_luna_digest.py "transcript.txt"

# Update backlog (remove processed IDs)
# Read JSON, filter out processed IDs, write back
```

## Error Messages Encountered

- "youtube-transcript-api not installed" → Use system Python or install package
- Permission errors during venv creation → Use existing system Python if possible
- Script not found errors → Search alternative locations

---
Last updated: 2026-04-16 by Hermes Agent during batch processing