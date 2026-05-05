---
name: YouTube Backlog Processor
category: media
description: Batch process YouTube videos from a backlog, fetch transcripts, generate Luna-style digests, and update backlogs with proper failure handling.
version: 1.0.0
---

# YouTube Backlog Processor

Batch processes YouTube videos from a backlog, fetching transcripts and generating Luna-style digests. Handles failures gracefully and updates backlogs.

## Workflow Steps

1. **Read backlog**: Parse video IDs from text list and/or JSON
2. **Select videos**: Pick N videos from the start of the backlog
3. **Fetch transcripts**: Use fetch_transcript.py with `--text-only --timestamps`
   - Expected failure modes:
     - "Transcripts are disabled for this video" → skip, keep in backlog
     - "Could not retrieve a transcript" (copyright/unavailable) → skip, keep in backlog
     - Cloud IP blocking → retry or skip
   - If first language fails, retry without `--language` flag
4. **Generate Luna digest**: Run generate_luna_digest.py on timestamped transcript
5. **Enhance digest**: Add video URL, descriptive title, thematic sections
6. **Save digest**: Write to `/opt/data/.hermes/content/youtube-raw/VIDEO_ID.txt`
7. **Update backlogs**: Remove processed IDs from BOTH files:
   - `yt-latent-space-backlog.txt` (renumber lines)
   - `yt-backlog.json` (maintain unique_videos array)
8. **Repeat** until N videos processed or backlog exhausted

## Key Failure Handling

- **Transcript unavailable**: Do NOT remove from backlog. User may want to retry later if subtitles become available.
- **Cloud IP blocking**: YouTube blocks cloud provider IPs. Workarounds:
  - Use residential proxy/VPN
  - Use cookies from logged-in session (`--cookies` flag if supported)
  - Pre-fetch transcripts from non-cloud machine
- **Empty transcripts**: Retry without language specification to get any available transcript
- **Malformed backlog files**: Preserve original formatting, log errors but continue

## File Formats

### Text Backlog (`yt-latent-space-backlog.txt`)
```
     1|VIDEO_ID_1
     2|VIDEO_ID_2
     ...
```

### JSON Backlog (`yt-backlog.json`)
```json
{
  "unique_videos": ["VIDEO_ID_1", "VIDEO_ID_2", ...]
}
```

### Output Digest (`youtube-raw/VIDEO_ID.txt`)
```
https://www.youtube.com/watch?v=VIDEO_ID
TITLE - Descriptive Subtitle

[CONTEXT] transcript (what matters):
    •    Core concept = ...
    ◦    Key point with detail
    •    Major takeaway
```

## Commands Used

```bash
# Fetch transcript with timestamps
cd /opt/hermes && .venv/bin/python /opt/data/skills/media/youtube-content/scripts/fetch_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --text-only --timestamps

# Generate Luna digest
cd /opt/hermes && .venv/bin/python /opt/data/skills/media/youtube-content/scripts/generate_luna_digest.py transcript.txt
```

## Lessons Learned\n\n1. **Always check transcript availability first** before removing videos from backlog\n2. **Some videos may have partial transcripts** - validate non-empty output\n3. **Cloud IP blocking is common** - have fallback strategies ready\n4. **Maintain both backlog formats in sync** - remove from both files atomically\n5. **Enhance digests with context** - raw Luna output benefits from titles and URLs\n6. **Numbering in text files** - renumber sequentially after removals, don't preserve original numbers\n7. **Digest generation script issues**: The provided generate_luna_digest.py has regex pattern errors (single vs double backslashes) that prevent it from working. Workaround: Create a custom digest function or fix the script's regex patterns.\n8. **Fallback digest approach**: When generate_luna_digest.py fails, implement a simple fallback: strip timestamps, extract sentences, format as Luna-style bullets with • for main points and ◦ for sub-points.\n9. **Validation is critical**: Always check that transcript fetch succeeded (not JSON error) and that digest generation produced non-empty output before considering a video processed.\n10. **Temporary file management**: Always clean up temporary files used for transcript storage during digest generation.\n
## Success Criteria

- [ ] Transcript fetched and validated (non-empty, not error JSON)
- [ ] Luna digest generated and enhanced
- [ ] Digest saved to youtube-raw/
- [ ] Video ID removed from both backlog files
- [ ] No data corruption in backlog files (proper formatting maintained)
