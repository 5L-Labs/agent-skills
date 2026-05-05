---
name: data-persistence-pattern
title: Data Persistence Pattern for Fetch Scripts
description: Add --save-dir option to data-fetching scripts to persist raw results for offline processing and re-formatting without re-fetching.
category: devops
created: 2026-04-25
updated: 2026-04-25
---

# Data Persistence Pattern

**Purpose**: Add automatic raw data persistence to data-fetching scripts, enabling offline processing and multiple output formats without re-fetching from the source.

## Pattern Overview

When a script fetches data from an external API or service (YouTube, Twitter, RSS, etc.), it often needs multiple output formats (digest, summary, Q&A, thread, etc.). Each format change typically requires re-fetching, which:
- Hits rate limits
- Risks IP blocking
- Loses data if the fetch fails
- Wastes time and API quota

**Solution**: Save raw fetched data alongside formatted outputs. Re-format from raw data instead of re-fetching.

## Implementation Pattern

### 1. Modify the Fetch Script

Add a `--save-dir` option that persists raw data:

```python
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-dir", "-s", help="Directory to save raw data files")
    parser.add_argument("--no-save", action="store_true", help="Explicitly disable saving")
    # ... other args ...
    
    args = parser.parse_args()
    
    # Fetch data from API
    data = fetch_from_api(...)
    
    # Save raw data if requested
    if not args.no_save:
        save_dir = args.save_dir or os.environ.get("SAVE_DIR")
        if save_dir:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Save full raw data (typically as JSON)
            json_path = save_dir / f"{identifier}.json"
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Save processed text version if applicable
            txt_path = save_dir / f"{identifier}_processed.txt"
            txt_path.write_text(process_to_text(data))
            
            print(f"[Saved: {json_path}, {txt_path}]", file=sys.stderr)
    
    # Output formatted result
    print(format_output(data))
```

### 2. Create Formatter Scripts

Separate scripts for each output format that read from raw files:

```python
#!/usr/bin/env python3
"""Generate [FORMAT] from raw data file."""
import sys
import json
from pathlib import Path

def main():
    raw_file = Path(sys.argv[1])
    data = json.loads(raw_file.read_text())
    
    # Generate specific format
    output = generate_format(data)
    print(output)
```

### 3. Update Documentation

Document the `--save-dir` option in the skill's SKILL.md:

```markdown
### Raw Data Storage

Use `--save-dir DIR` to persist raw data:

```bash
script.py "URL" --save-dir /path/to/raw-data
```

This saves:
- `{id}.json` - Full raw data (all fields, structured)
- `{id}_processed.txt` - Plain text version

Raw files enable re-formatting without re-fetching:
```bash
python3 generate_format.py existing_file.json
```
```

## File Structure

```
project/
├── scripts/
│   ├── fetch_data.py          # Main fetch script with --save-dir
│   ├── generate_format_a.py    # Reads raw JSON, outputs format A
│   ├── generate_format_b.py    # Reads raw JSON, outputs format B
│   └── generate_format_c.py
├── data/
│   ├── raw/                    # Saved by --save-dir
│   │   ├── item1.json
│   │   ├── item1_processed.txt
│   │   ├── item2.json
│   └── item2_processed.txt
└── skills/
    └── SKILL.md                   # Documents --save-dir option
```

## Benefits

1. **No Re-fetching**: Multiple formats from same raw data
2. **Rate Limit Safe**: One fetch, many outputs
3. **Offline Processing**: Raw data available without API access
4. **Version Control**: Raw JSON files can be committed to git
5. **Error Recovery**: Failed formatting doesn't lose fetched data
6. **Debugging**: Inspect raw data to diagnose formatting issues
7. **Incremental Processing**: Add new formats without re-fetching backlog
8. **Collaboration**: Share raw data files instead of re-fetching

## Example Use Cases

### YouTube Transcripts
```bash
# Fetch and save raw
python3 fetch_transcript.py "VIDEO_URL" --save-dir ./transcripts/raw

# Generate Luna digest
python3 generate_luna_digest.py ./transcripts/raw/VIDEO_ID_timestamped.txt

# Later: generate Q&A without re-fetching
python3 generate_qa.py ./transcripts/raw/VIDEO_ID.json
```

### Twitter/X Posts
```bash
# Fetch and save raw
python3 fetch_tweets.py "USER" --save-dir ./tweets/raw

# Generate digest
python3 generate_digest.py ./tweets/raw/USER_TIMESTAMP.json

# Later: generate thread format
python3 generate_thread.py ./tweets/raw/USER_TIMESTAMP.json
```

### RSS/Blog Posts
```bash
# Fetch and save raw
python3 fetch_feed.py "RSS_URL" --save-dir ./posts/raw

# Generate summary
python3 generate_summary.py ./posts/raw/POST_ID.json
```

{'Script**': 'opt/data/skills/media/youtube-batch-processor/scripts/generate_luna_digest.py`\n- Generates Luna-style digests from existing timestamped transcript files\n- Enables re-formatting without re-fetching from YouTube\n\n**Storage Directories**:\n- Raw JSON transcripts: `/opt/data/.hermes/content/yt-raw-transcripts/`\n- Luna-style digests: `/opt/data/.hermes/content/youtube-raw/`\n\n**Usage**:\n```bash\n# Fetch and save raw transcript data\npython3 fetch_transcript.py', 'https': 'youtube.com/watch?v=VIDEO_ID', 'Later': 'create different format without re-fetching\n# (example: generate Q&A from raw JSON)\npython3 generate_qa.py /opt/data/.hermes/content/yt-raw-transcripts/VIDEO_ID.json\n```\n\n**Benefits for YouTube Processing**:\n- No re-fetching needed when changing output formats (digest → summary → Q&A → chapters)\n- Immune to YouTube API rate limits and temporary blocks\n- Transcripts available for processing even if YouTube API is inaccessible\n- Raw JSON files preserve full segment-level data for advanced processing\n- Enables historical comparisons and iterative format improvements'}

## Error Handling

Handle these cases gracefully:

1. **Save directory not writable**: Warn but continue with output
2. **Disk full**: Warn, continue with output
3. **Invalid data**: Save error state for debugging
4. **Partial fetch**: Save what was retrieved with error marker

## Testing

Test with:
- No `--save-dir` (should work as before)
- With `--save-dir` (should save + output)
- With `--no-save` (should never save)
- Non-existent directory (should create it)
- Read-only directory (should warn but continue)

## Migration Path

For existing scripts without `--save-dir`:

1. Add the option (backward compatible)
2. Run once with `--save-dir` to populate raw data
3. Create formatter scripts for needed outputs
4. Update cron jobs to include `--save-dir`
5. Remove old re-fetching logic

## Key Insight

**Raw data is the source of truth. Formats are just views.**

By persisting raw data, you decouple data collection from data presentation, enabling:
- Rapid iteration on formats
- Multiple simultaneous outputs
- Offline processing
- Historical comparisons
- Easier debugging
