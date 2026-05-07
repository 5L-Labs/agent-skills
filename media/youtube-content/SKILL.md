---
name: youtube-content
description: >
  Fetch YouTube video transcripts and transform them into structured content
  (chapters, summaries, threads, blog posts). Use when the user shares a YouTube
  URL or video link, asks to summarize a video, requests a transcript, or wants
  to extract and reformat content from any YouTube video.
---

# YouTube Content Tool

Extract transcripts from YouTube videos and convert them into useful formats.

## Setup

```bash
pip install youtube-transcript-api
```

## Helper Scripts

`SKILL_DIR` is the directory containing this SKILL.md file.

1. `fetch_transcript.py`: Fetches transcript from YouTube video
2. `generate_luna_digest.py`: Generates Luna-style digest from timestamped transcript

### Fetch Transcript Script

```bash
# JSON output with metadata
python3 SKILL_DIR/scripts/fetch_transcript.py "https://youtube.com/watch?v=VIDEO_ID"

# Plain text (good for piping into further processing)
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --text-only

# With timestamps
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --timestamps

# Specific language with fallback chain
python3 SKILL_DIR/scripts/fetch_transcript.py "URL" --language tr,en
```

### Raw Transcript Storage

Use `--save-dir DIR` (or set `SAVE_DIR` environment variable) to persist raw transcript JSON + timestamped text files:

```bash
SKILL_DIR/scripts/fetch_transcript.py "URL" --save-dir /path/to/transcripts
```
Saves: `{DIR}/{VIDEO_ID}.json` (full transcript data) and `{DIR}/{VIDEO_ID}_timestamped.txt` (readable format).

### Generate Luna Digest Script

```bash
# Generate Luna digest from timestamped transcript file
python3 SKILL_DIR/scripts/generate_luna_digest.py "timestamped_transcript.txt"`
```

> **Note**: The provided `generate_luna_digest.py` script may not work reliably with all transcript formats or may produce no output. In automated workflows, be prepared to immediately use the fallback method if the script fails or produces no output.
\n\n> **Fallback method**: When the standard script fails or produces no output:\n> 1. Strip timestamps from transcript lines (remove patterns like `0:05 `, `12:34 `, or `1:05:23 ` using regex `^\\d+:\\d{2}(?:\\:\\d{2})?\\s+`)\n> 2. Join remaining text and split into sentences\n> 3. Filter to keep only meaningful sentences (length > 20 characters)\n> 4. Group sentences into thematic sections (prospects/benefits, key applications, challenges/risks, philosophical considerations)\n> 5. Format as Luna-style bullet points with `•` for main points and `◦` for sub-points\n> 6. Bold key terms on first mention\n> 7. This ensures batch processing can continue even when the standard script fails.

## Output Formats

After fetching the transcript, format it based on what the user asks for:

- **Chapters**: Group by topic shifts, output timestamped chapter list
- **Summary**: Concise 5-10 sentence overview of the entire video
- **Chapter summaries**: Chapters with a short paragraph summary for each
- **Thread**: Twitter/X thread format — numbered posts, each under 280 chars
- **Blog post**: Full article with title, sections, and key takeaways
- **Quotes**: Notable quotes with timestamps
- **Luna digest** (default): Structured bullet-point digest — not prose paragraphs

### Example — Chapters Output

```
00:00 Introduction — host opens with the problem statement
03:45 Background — prior work and why existing solutions fall short
12:20 Core method — walkthrough of the proposed approach
24:10 Results — benchmark comparisons and key takeaways
31:55 Q&A — audience questions on scalability and next steps
```

### Example — Luna Digest Output

```
[Video Title] transcript (what matters):
    •    Core concept = definition.
    Short explanation.
    •    Second concept:
    ◦    Detail or example.
    ◦    Another detail.
    •    Key distinction between X and Y:
    ◦    X = this
    ◦    Y = that
    •    Practical relevance:
    ◦    Use case 1.
    ◦    Use case 2.
    •    Big insight: main takeaway in one line.
            
    •    Caveats or open questions:
    ◦    Limitation or note.
        [Optional: next-action offer]
```

## Luna Digest Format (default)

When no format is specified, use the **Luna** style. This is a structured bullet-point digest — not prose paragraphs.

Style rules:
- Open with a short title and context line (speaker, source, length)
- Use thematic sections with a bold label and a short intro sentence
- Bullet points for main ideas, `◦` sub-bullets for details/examples
- Bold key terms on first mention
- No markdown headers, no emoji dividers
- Concise — each bullet should be one or two lines max
- End with a "next step" or question if natural

## Workflow

1. **Fetch** the transcript using the fetch_transcript.py helper script with `--text-only --timestamps`.
2. **Validate**: check if output is a JSON error (indicating transcripts disabled, private video, etc.). If error JSON:
   - For batch processing: skip this video and continue with next one (do NOT remove from backlog)
   - For single video: inform user and suggest checking if subtitles are available on video page
   If not error JSON, confirm output is non-empty and in expected language. If empty, retry without `--language` to get any available transcript. If still empty, treat as transcript disabled.
3. **Check for existing transcript** before fetching: if `/opt/data/.hermes/content/youtube-raw/<name>.txt` already exists, skip fetching to avoid duplicates.
4. **Chunk if needed**: if the transcript exceeds ~50K characters, split into overlapping chunks (~40K with 2K overlap) and summarize each chunk before merging.
5. **Transform** into the requested output format:
   - For Luna digest: first try running the generate_luna_digest.py script on the timestamped transcript
   - If the script produces no output or encounters an error, immediately use the fallback method: strip timestamps, join text, split into meaningful sentences (length > 20 chars), and create a structured digest with thematic sections following the Luna format guidelines
   - For other formats: follow the specific formatting guidelines in the Output Formats section
6. **Verify**: re-read the transformed output to check for coherence, correct timestamps, and completeness before presenting.
7. **Save** raw transcript to `/opt/data/.hermes/content/youtube-raw/<name>.txt`
8. **Update backlog**: after successful processing, remove the video ID from the backlog JSON (`/opt/data/.hermes/content/yt-backlog.json` -> `unique_videos` array).

## Advanced Fetching Options

For environments with cloud IP restrictions (which block standard API access), use the dedicated cookie-aware fetch script:

```bash
# With cookie file
python SKILL_DIR/scripts/cookie_fetch.py VIDEO_ID --cookie-file /path/to/cookies.txt

# With default cookie location
python SKILL_DIR/scripts/cookie_fetch.py VIDEO_ID

# With language fallback
python SKILL_DIR/scripts/cookie_fetch.py VIDEO_ID --language en,tr

# Save to directory
python SKILL_DIR/scripts/cookie_fetch.py VIDEO_ID --save-dir /opt/data/.hermes/content/youtube-raw
```

This script bypasses IP blocks by using YouTube login cookies. See `references/cookie-setup.md` for detailed setup instructions.

## Proxy Support

To use a residential proxy, set the standard environment variables before running any fetch command:

```bash
export HTTP_PROXY=http://proxy-user:proxy-pass@proxy-ip:proxy-port
export HTTPS_PROXY=http://proxy-user:proxy-pass@proxy-ip:proxy-port
python SKILL_DIR/scripts/fetch_transcript.py VIDEO_ID
```

## Choosing the Right Method

| Situation | Recommended Method |
|-----------|-------------------|
| Video already in cache | Use cached transcript (no fetch needed) |
| Non-cloud IP (home network) | Standard `fetch_transcript.py` |
| Cloud IP with access to YouTube cookies | `cookie_fetch.py` with cookies |
| Cloud IP with residential proxy | Set `HTTP(S)_PROXY` environment variables |
| Batch processing from non-cloud machine | Pre-fetch and cache all transcripts |

## Error Detection and Recovery

When processing batches, implement this logic:

1. Check cache first — if transcript exists, use it.
2. If not, attempt fetch with standard script.
3. If IP_BLOCKED error occurs:
   - Log the video ID and error.
   - If cookies are configured, retry with `cookie_fetch.py`.
   - If proxy is configured, ensure it's set correctly.
   - If neither, skip the video and continue.
4. After processing, generate a report of skipped videos with recommendations.

This approach maximizes successful processing while working around IP restrictions.
The scripts require `youtube-transcript-api`. Before creating temporary venvs, check if the package is already available in a system Python:

```bash
python3 -c "import youtube_transcript_api; print('OK')"
```

If available, use that Python interpreter to run the scripts. Common locations:
- `/usr/bin/python3` (often has the package pre-installed)
- `/opt/hermes/.venv/bin/python3` (check if the agent's venv has it)

**If not available**, use the temporary venv workaround from the Pitfalls section.

## Locating Scripts

The skill scripts may be installed in multiple locations. Check these paths in order:

```bash
/opt/data/.hermes/skills/media/youtube-content/scripts/
/opt/data/skills/media/youtube-content/scripts/
/opt/data/hermes-agent/skills/media/youtube-content/scripts/
/opt/data/repos/agent-skills/media/youtube-content/scripts/
/opt/data/upstream-hermes-agent/skills/media/youtube-content/scripts/
```

Use `find /opt/data -name "fetch_transcript.py" -type f` if needed.

## Error Handling (Expanded)

- **Transcript disabled**: tell the user; suggest they check if subtitles are available on the video page.
- **Private/unavailable video**: relay the error and ask the user to verify the URL.
- **No matching language**: retry without `--language` to fetch any available transcript, then note the actual language to the user.
- **Dependency missing**: run `pip install youtube-transcript-api` and retry.
- **Digest script failure**: if `generate_luna_digest.py` produces no output or encounters errors, immediately use the fallback method: strip timestamps, join text, split into meaningful sentences (length > 20 chars), and create a structured digest with thematic sections following the Luna format guidelines. In automated workflows, do not spend time debugging - go directly to the fallback to ensure processing continues.
- **Complete script failure**: if generate_luna_digest.py cannot be found or crashes irreparably, create a basic structured digest manually:
  ```python
  with open(transcript_file, 'r') as f:
      lines = f.readlines()
  text = ' '.join([line.split(' ', 1)[-1] for line in lines if line.strip()])
  digest = f"• Core concept: {text[:100]}...\n• Key points extracted from transcript.\n"
  ```
- **Cloud IP blocking**: YouTube aggressively blocks transcript requests from cloud provider IPs (AWS, GCP, Azure). This is not a temporary rate-limiting issue but a fundamental access restriction. The script will return a JSON error: `{"error": "Could not retrieve a transcript..."}`.
  - **If the video is already cached** (see Workflow step 3), use the cached transcript — this bypasses the IP block.
  - **If the video is not cached**, you have several options:
    1. **Use a residential proxy or VPN** — configure the script to route requests through a non-cloud IP.
    2. **Use cookies from a logged-in YouTube session** — see the `references/cookie-setup.md` for instructions on extracting and using YouTube cookies.
    3. **Pre-fetch transcripts from a non-cloud machine** and store them in the cache before processing.
    4. **Wait for YouTube to unblock the IP** — this is unlikely to happen.
  - **Important**: Do not simply retry or wait — the block is persistent. The workflow should either skip the video (for batch processing) or inform the user of the need for proxy/cookie configuration (for interactive use).
- **Batch processing IP block handling**: When processing multiple videos, if a video is not in the cache and encounters an IP block error:
  - Log the error clearly.
  - Skip the video (do NOT remove from backlog).
  - Continue processing the next video.
  - At the end, report which videos failed and why, along with recommendations for resolving the IP block issue.

### Enhanced Batch Processing Workflow

For robust batch processing (e.g., cron jobs), follow this enhanced workflow:

1. **Read the backlog** from `/opt/data/.hermes/content/yt-backlog.json`
2. **Process videos sequentially** with proper error handling:
   - If transcript fetch fails (IP block, network error, etc.), **skip the video** and continue to the next
   - **DO NOT remove failed videos from the backlog** — they should be retried in future runs
   - Log failures with clear error messages
3. **After processing all videos**, generate a report of successes and failures
4. **Preserve the backlog** — only remove videos that were successfully processed and saved to the cache

#### Critical Pitfall: Backlog Integrity

**Never modify the backlog file until after all processing is complete.** Use a temporary list for removals and write back only once at the end. This prevents partial updates if the script crashes.

#### Recommended Batch Processing Script

Create a dedicated batch script to handle these edge cases:

```python
#!/usr/bin/env python3
"""
Batch processor for YouTube transcripts with proper error handling.
Preserves backlog integrity and handles IP blocks gracefully.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BACKLOG_PATH = "/opt/data/.hermes/content/yt-backlog.json"
CACHE_DIR = "/opt/data/.hermes/content/youtube-raw/"
DIGEST_FILE = "/opt/data/home/.hermes/yt-digest.txt"

def load_backlog():
    with open(BACKLOG_PATH, 'r') as f:
        return json.load(f)

def save_backlog(data):
    with open(BACKLOG_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def fetch_transcript(video_id):
    """Fetch transcript with error handling."""
    # Check cache first
    cache_file = CACHE_DIR / f"{video_id}_timestamped.txt"
    if cache_file.exists():
        return open(cache_file, 'r').read(), None
    
    # Attempt fetch
    cmd = [
        "/usr/bin/python3",
        "/opt/data/.hermes/skills/media/youtube-content/scripts/fetch_transcript.py",
        f"https://youtube.com/watch?v={video_id}",
        "--text-only",
        "--timestamps"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, result.stderr
    
    return result.stdout, None

def process_video(video_id):
    """Process a single video with full error handling."""
    try:
        transcript, error = fetch_transcript(video_id)
        if error:
            return {"status": "failed", "error": error}
        
        if not transcript:
            return {"status": "failed", "error": "No transcript received"}
        
        # Generate Luna digest (with fallback)
        # ... (digest generation logic)
        
        return {"status": "success", "video_id": video_id}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

def main():
    backlog = load_backlog()
    video_ids = backlog["unique_videos"][:]  # Copy for safe iteration
    
    successes = []
    failures = []
    
    for video_id in video_ids[:10]:  # Process first 10
        result = process_video(video_id)
        if result["status"] == "success":
            successes.append(video_id)
            # Only remove from backlog if successful
            if video_id in video_ids:
                video_ids.remove(video_id)
        else:
            failures.append((video_id, result.get("error", "Unknown error")))
    
    # Save updated backlog (only if modifications made)
    if successes:
        backlog["unique_videos"] = video_ids
        save_backlog(backlog)
    
    # Generate report
    report = f"""=== BATCH PROCESSING REPORT - {datetime.now().isoformat()} ===
Processed 10 videos from backlog
Successes: {len(successes)}
Failures: {len(failures)}

"""
    if successes:
        report += f"Successfully processed: {', '.join(successes)}\n"
    if failures:
        report += "\nFailed videos:\n"
        for vid, err in failures:
            report += f"  {vid}: {err}\n"
    
    report += "\nBacklog remaining: {len(video_ids)} videos\n"
    report += "=== END REPORT ===\n"
    
    with open(DIGEST_FILE, 'a') as f:
        f.write(report)
    
    print(report)

if __name__ == "__main__":
    main()
```

#### IP Block Handling in Batch Mode

When YouTube blocks your cloud IP:

1. **Do not retry immediately** — the block is persistent
2. **Skip the video** and continue with the next
3. **At the end of the batch**, generate a report listing blocked videos
4. **Consider implementing** one of the workarounds from the "Working around IP bans" section
5. **For future batches**, either:
   - Use pre-fetched transcripts (cache-first strategy)
   - Configure cookies or proxy before running the batch

#### Reporting Failures

Always include in the report:
- Which videos failed
- The specific error message
- Recommendations for resolving the issue
- Whether the backlog was modified

This ensures transparency and allows for manual intervention when automated processing fails.
- **Transcript disabled**: tell the user; suggest they check if subtitles are available on the video page.
- **Private/unavailable video**: relay the error and ask the user to verify the URL.
- **No matching language**: retry without `--language` to fetch any available transcript, then note the actual language to the user.
- **Dependency missing**: run `pip install youtube-transcript-api` and retry.
- **Digest script failure**: if `generate_luna_digest.py` produces no output or encounters errors, immediately use the fallback method: strip timestamps, join text, split into meaningful sentences, and create a structured digest with thematic sections following the Luna format guidelines. In automated workflows, do not spend time debugging - go directly to the fallback to ensure processing continues.
- **Complete script failure**: if generate_luna_digest.py cannot be found or crashes irreparably, create a basic structured digest manually:
  ```python
  with open(transcript_file, 'r') as f:
      lines = f.readlines()
  text = ' '.join([line.split(' ', 1)[-1] for line in lines if line.strip()])
  digest = f"• Core concept: {text[:100]}...\n• Key points extracted from transcript.\n"
  ```
- **Cloud IP blocking**: YouTube blocks transcript requests from cloud provider IPs (AWS, GCP, Azure). The script returns a JSON error: `{"error": "Could not retrieve a transcript..."}`. Workarounds:
  - **Always check the local cache at `/opt/data/home/.hermes/content/youtube-raw/<video_id>.txt`** first, as this often contains pre-fetched transcripts that bypass the block.
  - Use a residential proxy or VPN
  - Use cookies from a logged-in YouTube session (`--cookies` flag if supported)
  - Pre-fetch transcripts from a non-cloud machine and store them locally

## Pitfalls

- **youtube-transcript-api not installed**: The venv at `/opt/hermes/.venv` often lacks `youtube-transcript-api` and may not have `pip` available. The install also fails with `uv pip install` (permission denied writing to site-packages) and `uv pip install --user` (unsupported flag). **Correct workaround** — create a temporary venv:
  ```bash
  uv venv /tmp/yt-venv && uv pip install --python /tmp/yt-venv/bin/python youtube-transcript-api
  ```
  Then run scripts with that venv's Python:
  ```bash
  /tmp/yt-venv/bin/python SKILL_DIR/scripts/fetch_transcript.py "URL" --text-only --timestamps
  ```
  Do NOT use bare `python3` or `/opt/hermes/.venv/bin/python3` — both will fail with "youtube-transcript-api not installed."

- **Flag combinations change output format**:
  - No flags → JSON with `full_text` (plain text) + metadata
  - `--timestamps` alone → JSON with `full_text` + `timestamped_text` field (each line: `M:SS text`)
  - `--text-only` alone → plain text string (no JSON, no timestamps)
  - `--text-only --timestamps` → timestamped plain text (one line per segment: `M:SS text`), no JSON wrapping
  The workflow step 1 uses `--text-only --timestamps` intentionally — this gives raw timestamped lines suitable for LLM processing. Do NOT expect JSON when combining both flags.

- **Naming mismatch**: Video IDs in the backlog JSON (e.g., `b80by3Xk_A8`) may not match transcript filenames exactly due to prefixes or suffixes. Always check for existence using `video_id` as a substring, not exact match.

- **generate_luna_digest.py producing no output**: The script may exit without printing anything if there are issues with sentence extraction or if the transcript contains no valid sentences after timestamp stripping. To debug:
  1. Run the script with a small test file and redirect stderr to see any error messages: `python3 generate_luna_digest.py test.txt 2>&1`
  2. Add debug prints at key steps in the script (after reading file, after stripping timestamps, after sentence extraction) to see where it fails
  3. Common issues: regex patterns not matching timestamped lines due to extra whitespace, or sentence extraction returning empty list
  4. If debugging doesn't resolve the issue, use the fallback method: strip timestamps, join text, split into meaningful sentences (length > 20 chars), and create a structured digest with thematic sections following the Luna format guidelines.