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

```
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

```
SKILL_DIR/scripts/fetch_transcript.py "URL" --save-dir /path/to/transcripts
```
Saves: `{DIR}/{VIDEO_ID}.json` (full transcript data) and `{DIR}/{VIDEO_ID}_timestamped.txt` (readable format).

### Generate Luna Digest Script

```
# Generate Luna digest from timestamped transcript file
python3 SKILL_DIR/scripts/generate_luna_digest.py "timestamped_transcript.txt"`
```

> **Note**: The provided `generate_luna_digest.py` script may not work reliably with all transcript formats or may produce no output. In automated workflows, be prepared to immediately use the fallback method if the script fails or produces no output.

> **Fallback method**: When the standard script fails or produces no output:
> 1. Strip timestamps from transcript lines (remove patterns like `0:05 `, `12:34 `, or `1:05:23 ` using regex `^\d+:\d{2}(?::\d{2})?\s+`)
> 2. Join remaining text and split into sentences
> 3. Filter to keep only meaningful sentences (length > 20 characters)
> 4. Group sentences into thematic sections (prospects/benefits, key applications, challenges/risks, philosophical considerations)
> 5. Format as Luna-style bullet points with `•` for main points and `◦` for sub-points
> 6. Bold key terms on first mention
> 7. This ensures batch processing can continue even when the standard script fails.

## Output Formats

After fetching the transcript, format it based on what the user asks for:

**Raw batch-artifact file names** (for automated/unguided runs):
- `{VIDEO_ID}_transcript.txt` — raw timestamped lines (one segment per line, `[MM:SS] text` or `M:SS text`)
- `{VIDEO_ID}_fulltext.txt` — timestamps stripped, all text joined in a single paragraph
- `{VIDEO_ID}_meta.json` — `{"video_id": "...", "segments_count": N, "duration_seconds": N}`

**User-facing transformations**: choose one.

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

> **Playlist-exhaustion signal** (cron runs): When an early scan shows ALL non-empty `playlist-new-ids.txt` lines carry `DONE`, the backlog has zero candidates. Report this immediately with the counts — do not silently exit or skip reporting. The user may want to know the system is clean rather than broken.

1. **Determine source of truth and candidate set** before writing any files.
   - **`yt-backlog.json` is authoritative** for which video IDs are known and their status (`unique_videos` = processed, `failed_videos` = failures). Do not derive processed/unprocessed status solely from `playlist-new-ids.txt`.
   - **`playlist-new-ids.txt`** is a subset/incremental tracker in `ID\tSTATUS` format. A line marked `DONE` means that specific batch-adding step was committed, but the ID may already appear in `yt-backlog.json` `unique_videos` from an earlier run. Use `unique_videos` as the authoritative "already done" set.
   - Candidates to fetch = IDs in the playlist file NOT marked `DONE`, minus any already in `yt-backlog.json` `unique_videos` or in `failed_videos` with status `confirmed_permanent`.
2. **Locate `fetch_transcript.py` first before fetching**. Confirm which Python interpreter has `youtube-transcript-api`: `python3 -c "import youtube_transcript_api"`. If absent, use the temporary venv workaround from the Pitfalls section. Note: other batch runner scripts (e.g. `batch_fetch.py`, `batch_fetch_retry.py`) hardcode `/opt/hermes/.venv/bin/python3`, which may lack the library — do not call those scripts blindly unless the import is proven present.
3. **Fetch** the transcript using `fetch_transcript.py` with `--text-only --timestamps`. This combination produces timestamped plain text (`M:SS text` or `[MM:SS] text`, one segment per line) — not JSON. Do not expect `segments_count` from stdout; parse the output into segments yourself if you need that number.
4. **Validate**: after running the script, check ALL THREE indicators before trusting stdout:
   - **rc ≠ 0** → script exited with an error code; read stderr.
   - **stderr** contains `SSLEOFError`, `UNEXPECTED_EOF_WHILE_READING`, or `Could not retrieve` → cloud IP block; skip and mark `confirmed_permanent`. **Do NOT write stdout to file.**
   - **stdout begins with `{"error"`** or similar JSON error object → `fetch_transcript.py` caught a network/SSL error but exited 0 with the error in stdout. This is a masked failure — treat identically to the stderr-SSL case.
   - If none of the above: confirm stdout is non-empty and lines match `M:SS text` or `[MM:SS] text` format. If empty, retry without `--language`. If still empty, treat as transcript disabled.
   - **Batch**: skip and continue (do NOT remove from backlog).
   - **Single video**: inform user and suggest checking if subtitles are available on the video page.
5. **Check for existing transcript before fetching, strict priority**. A "valid hit" = file exists + size > 500 B + first line matches timestamped format `[M:SS] text` or `M:SS text`. The first valid hit wins — do not miss a cached transcript in a lower-priority location.
   1. `/opt/data/.hermes/content/youtube-raw/<name>_transcript.txt` — **primary output dir** (this run's current target)
   2. `/opt/data/home/.hermes/content/youtube-raw/<name>.txt` — **home-cache** (pre-fetched from home-IP; no `_transcript` prefix in filename)
   3. `/opt/data/.hermes/content/youtube-raw/<name>_transcript.txt` — **legacy review dir** — authoritative only if primary + home-cache both fail. See `references/legacy-review-dir-audit.md` for copy/upgrade protocol.
   Stop checking after the first valid hit. Error stubs (`_error.txt` without a matching transcript file) are NOT valid hits — continue to the next location.
6. **Chunk if needed**: if the transcript exceeds ~50K characters, split into overlapping chunks (~40K with 2K overlap) and summarize each chunk before merging.
7. **Write three files per video** — always all three, never delete prior ones without inspection:
   - `<VIDEO_ID>_transcript.txt` — raw timestamped lines as-is from source (one segment per line)
   - `<VIDEO_ID>_fulltext.txt` — timestamps stripped, all text joined
   - `<VIDEO_ID>_meta.json` — `{"video_id": "...", "segments_count": N, "duration_seconds": N}`
   **Meta JSON schema**: strictly use keys `video_id` (string), `segments_count` (int), `duration_seconds` (int). Do not use `segments` or `duration` or `source` — existing files may have legacy keys but new writes must use the canonical keys.
8. **Transform** into the requested output format:
   - For Luna digest: first try running `generate_luna_digest.py` on the timestamped transcript
   - If the script produces no output or encounters an error, immediately use the fallback method: strip timestamps, join text, split into meaningful sentences (length > 20 chars), and create a structured digest with thematic sections following the Luna format guidelines
   - For other formats: follow the specific formatting guidelines in the Output Formats section
9. **Verify**: re-read the transformed output to check for coherence, correct timestamps, and completeness before presenting. After writing, also verify all three local files exist with non-trivial sizes.
10. **Save** raw transcript to `/opt/data/.hermes/content/youtube-raw/<name>.txt` (also save to home-cache path when home-cache was the source so both paths stay in sync).
11. **Synchronise `yt-backlog.json` (authoritative) BEFORE marking `playlist-new-ids.txt` DONE**:
   - Add processed video IDs to `unique_videos`.
   - **Pre-batch promotion pass**: before starting the batch, scan `failed_videos` for IDs whose transcript file now exists in any of the three transcript dirs; promote those candidates out of `confirmed_permanent` and into `unique_videos`, changing their status to `cloud_ip_blocked_recovered` with a note explaining the recovery path (home-cache, legacy dir, or re-fetch). This accounts for the regularly-seen 8–12 stale `confirmed_permanent` entries per batch.
   - For videos that just succeeded: remove from `failed_videos` entirely (do not keep a stale `confirmed_permanent` entry alongside the new `unique_videos` entry).
   - Add confirmed new failures to `failed_videos` with `status: confirmed_permanent` or `status: cloud_ip_blocked_recovered`, with a descriptive `note` string.
   - Set `last_updated` to UTC-ISO. This is the only place batch completion is authoritatively recorded. `playlist-new-ids.txt` DONE marking is secondary/provisional and may lag.