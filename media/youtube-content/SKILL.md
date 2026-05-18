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

### Batch Scripts (cron / playlist mode)

Use these when the Python `youtube-transcript-api` call is blocked (SSL error from cloud IP). See `references/batch-scripts.md` and `references/cloud-ip-blocking.md` for selection guidance.

| Script | Use when |
|--------|----------|
| `_fetch_transcripts_batch.py` | Python urllib available, strict VTT parse needed |
| `yt_batch_10.sh` | shell needed, video count hardcoded |

Canonical storage paths for this deployment:
- Playlist: `/opt/data/content/playlist-new-ids.txt`
- Backlog: `/opt/data/content/yt-backlog.json`
- Raw dir: `/opt/data/content/youtube-raw/`
- Batch scripts (on-disk): `/opt/data/content/scripts/ `, check with `find /opt/data/content -name "_fetch_transcripts_batch.py" -type f`
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
7. **Save** raw transcript to `/opt/data/.hermes/content/youtube-raw/<name>.txt`.
8. **Update backlog**: after successful processing, remove the video ID from the backlog JSON (`/opt/data/.hermes/content/yt-backlog.json` -> `unique_videos` array).

### Batch / cron job (playlist-driven)

Run only when `/opt/data/content/playlist-new-ids.txt` contains entries that do NOT already end in `DONE`.

```
Checked through playlist in /opt/data/content/playlist-new-ids.txt first.
```

**Re-scan preconditions** (before any network call):
1. Read `/opt/data/content/playlist-new-ids.txt` — skip lines ending `DONE`; those are already processed.
2. Read `/opt/data/content/yt-backlog.json` → `unique_videos` array + `failed_videos`.
3. **If playlist is fully exhausted** (every entry ends in `DONE`) → report zeros, skip network.
4. Pre-scan: for each candidate, if the 3-file set (`{VIDEO_ID}_transcript.txt`, `_fulltext.txt`, `_meta.json`) already exists in `/opt/data/content/youtube-raw/` and `meta.note` is NOT `chapter_outline_ip_blocked` → skip as DONE. If the note IS `chapter_outline_ip_blocked`, report honestly but skip re-fetch (add note — OCR-blocked videos rarely succeed on retry anyway).
5. Detector: orphan 3-file sets (on-disk files exist but `unique_videos` has no entry) → silently add to `unique_videos`, skip network call.
6. **Pick next N** (default 10) unprocessed and write to `VIDEOS` array in `_fetch_transcripts_batch.py`.
7. Run `_fetch_transcripts_batch.py` selected video set (circuit-break at 3 seconds, parallel-limit 10).
8. For each processed video: write `{VIDEO_ID}_transcript.txt`, `{VIDEO_ID}_fulltext.txt`, `{VIDEO_ID}_meta.json` to `/opt/data/content/youtube-raw/`. `meta.json` must contain: `video_id`, `title`, `segment_count`, `duration`, `fetched_at`, and optional `note`.
9. Append `VIDEO_ID` to `/opt/data/content/yt-backlog.json` → `unique_videos`.
10. Append ` DONE` to the matching line in `playlist-new-ids.txt`.
11. Write `last_batch_report.json` with target IDs, success/failure breakdown, and reason for each failure.

## Environment Setup

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

## Error Handling

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
- **Cloud IP blocking**: YouTube blocks transcript requests from cloud provider IPs (AWS, GCP, Azure). The `youtube_transcript_api` call, `yt-dlp` query, and even direct `urllib` HTML fetch all fail identically with `SSL: UNEXPECTED_EOF_WHILE_READING` — this is an IP-range block, not a library bug. On `OPT_DATA_PATTERN` this machine, **no Python or urllib-based retry can succeed while the block lasts**. Preferred workarounds, in order: (1) run from a non-cloud machine, (2) run on a stable network. See `references/cloud-ip-blocking.md` for the full failure taxonomy and per-layer behaviour.
  - **Always check the local cache at `/opt/data/content/youtube-raw/<video_id>.txt`** first, as this contains pre-fetched transcripts fetched before the block or from a different network path.
  - **Chapter fallback**: when both transcript fetch and VTT attempt fail, extract chapter titles + timestamps from `yt-dlp` metadata (if available) and save with `note: "chapter_outline_ip_blocked"`. Future runs should skip re-fetch for any 3-file set with this note but present it honestly.
  - **Confirmed-permanent vs transient-block**: in `yt-backlog.json` record verbatim error text. Use `"status": "confirmed_permanent"` for disabled-subs / IP blacklist; use `"status": "transient_block"` for transient timeouts and empty-yt-dlp responses. Update `last_updated` every cron run.

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