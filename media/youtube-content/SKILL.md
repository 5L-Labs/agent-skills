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

1. **Locate authoritative source files** — check ALL three:
   | File | What it sources |
   |---|---|
   | `/opt/data/.hermes/content/playlist-new-ids.txt` | freshly imported videos |
   | `/opt/data/.hermes/content/yt-latent-space-backlog.txt` | authoritative pending queue |
   | `/opt/data/content/yt-backlog.json` | authoritative completed/failed record |
   Read all three before deciding on the queue. **Never stop at an empty `playlist-new-ids.txt`** — the latent-space backlog may still contain un-DONE entries and is the authoritative pending list in practice.

2. **CANDIDATE SELECTION — Dual file-size threshold method**

   Build the candidate list from the latent-space backlog in FIFO order.
   For each video ID, check the pair of raw files:

   - `youtube-raw/{VIDEO_ID}_transcript.txt`  (target ≥ **500 B**)
   - `youtube-raw/{VIDEO_ID}_fulltext.txt`    (target ≥ **5 000 B**)

   **Skip** a video if both files exist and exceed their thresholds — it
   already has a real transcript. **Include** it if either file is missing
   or below threshold. Further distinction, in priority order:
   
   | Priority | Condition | Action |
   |---|---|---|
   1 | No files at all | process on next run |
   2 | `_transcript.txt` is 0 B (zero-segment stub with cached fulltext) | **re-segment from fulltext** or fetch live |
   3 | `_fulltext.txt` ≤ 5 KB **and** contains zero lines > 200 chars | chapter-outline stub from IP block — treat as need-live-fetch |
   4 | `_fulltext.txt` > 1 KB but < 5 KB with no long lines | suspiciously short / bookmarks — treat as stub |

   Apply this check in combination with the latent "DONE" marker: a
   video marked DONE in latent-backlog is *not* a candidate unless its
   files were saved but are below the real-content thresholds.

3. **Fetch** the transcript using the fetch_transcript.py helper script with `--text-only --timestamps`.
3. **Validate**: check if output is a JSON error (indicating transcripts disabled, private video, etc.). If error JSON:
   - For batch processing: skip this video and continue with next one (do NOT remove from backlog)
   - For single video: inform user and suggest checking if subtitles are available on video page
   If not error JSON, confirm output is non-empty and in expected language. If empty, retry without `--language` to get any available transcript. If still empty, treat as transcript disabled.
4. **Check for existing transcript** before fetching: if `/opt/data/content/youtube-raw/<name>.txt` already exists, skip fetching to avoid duplicates.
5. **Chunk if needed**: if the transcript exceeds ~50K characters, split into overlapping chunks (~40K with 2K overlap) and summarize each chunk before merging.
6. **Transform** into the requested output format:
   - For Luna digest: first try running the generate_luna_digest.py script on the timestamped transcript
   - If the script produces no output or encounters an error, immediately use the fallback method: strip timestamps, join text, split into meaningful sentences (length > 20 chars), and create a structured digest with thematic sections following the Luna format guidelines
   - For other formats: follow the specific formatting guidelines in the Output Formats section
7. **Verify**: re-read the transformed output to check for coherence, correct timestamps, and completeness before presenting.
8. **Save** raw transcript to `/opt/data/content/youtube-raw/{VIDEO_ID}_transcript.txt` and fulltext to `{VIDEO_ID}_fulltext.txt`, metadata to `{VIDEO_ID}_meta.json`
9. **Update backlog**: after successful processing, add the video ID to `yt-backlog.json` `unique_videos` array.
10. **Mark in latent-backlog**: append `DONE` to the video ID's line in `/opt/data/.hermes/content/yt-latent-space-backlog.txt` (not `playlist-new-ids.txt`, which is usually stale).
11. **Remove from playlist**: if the video appears in any queue-source file, append `DONE` to its line to prevent re-fetch next run.

## Environment Setup

The scripts require `youtube-transcript-api`. In this environment the package is already installed in the agent's venv at `/opt/hermes/.venv/bin/python3`; run scripts with that interpreter to avoid dependency issues:

```bash
/opt/hermes/.venv/bin/python3 fetch_transcript.py "URL" --timestamps
```

Verify availability:
```bash
/opt/hermes/.venv/bin/python3 -c "import youtube_transcript_api; print('OK')"
```

**If not available** (e.g. a fresh install), use the temporary venv workaround from the Pitfalls section.

## Locating Scripts

The skill scripts may be installed in multiple locations. Check these paths in order:

```bash
/opt/data/.hermes/skills/media/youtube-content/scripts/       ← ACTIVE CONFIG DIR (prefer this one)
/opt/data/skills/media/youtube-content/scripts/
/opt/data/.hermes-agent/skills/media/youtube-content/scripts/  ← INCORRECT — do not use; missing leading dot
/opt/data/repos/agent-skills/media/youtube-content/scripts/
/opt/data/upstream-hermes-agent/skills/media/youtube-content/scripts/
```

Use `find /opt/data -name "fetch_transcript.py" -type f` if needed.

> > **Known paths** (this environment): see `references/environment-paths.md` for the canonical
> cache dir, backlog file, working-script directory, and Python interpreter. This file
> documents every path that was wrong during the 2026-05-18 run and the correct values.
>
> > **Session notes**: see `references/session-notes.md` for run-specific edge cases (IP-block,
> cache-first workflow, zero-segment stubs, in-repo script discovery patterns).

> **PATH NOTE**: The active configuration directory at this installation is `/opt/data/.hermes/` (note the **leading dot** before `hermes`).
> The path `/opt/data/hermes-agent/` (without the dot) is a **different/invalid directory** and will produce
> `[Errno 13] Permission denied` errors. This is a wrong-path error, not an actual filesystem permissions problem.
> Always use `/opt/data/.hermes/` for the fetch/pipeline scripts, data directories, and backlog files.

## In-Repo Batch Scripts

Before writing a fresh batch fetch from scratch, **check for existing scripts** in the workspace that already encode the right logic. Common locations:

| Path | Notes |
|---|---|
| `/opt/data/repos/` | `batch_fetch.py` — retry from `failed_videos`; `batch_fetch_retry.py` — retry from `_failed.txt` entries |
| `/opt/data/content/` | `batch_fetch.py`, `batch_fetch_retry.py`, `batch_fetch_candidates.py` — all alongside data files; `batch_fetch_candidates.py` picks from latent-space backlog DONE-stripping and four hard-coded candidate IDs |

Reusing in-repo scripts avoids re-inventing: per-video manifest I/O, return-code checking, JSON parsing, `_failed.txt` lifecycle, duration, language fallback, yt-backlog.json wiring, and zero-segment truthfulness detection.

---

## Error Handling

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
- **Cloud IP blocking** (proven-definitive in this environment, session 2026-05-19): YouTube blocks transcript requests from cloud provider IPs (AWS, GCP, Azure). Both `youtube-transcript-api` and `yt-dlp` return identical `SSLEOFError` regardless of client library. Testing confirmed:
  - `youtube-transcript-api` → `SSLError(SSLEOFError)`
  - `yt-dlp` (installed fresh in temp venv) → identical `[SSL: UNEXPECTED_EOF_WHILE_READING]` error
  - `curl` to `timedtext` signed-URL → Google IP-block page (1 103 bytes), blocked regardless of client

  **Status: no proved-unblocked client-side approach exists from this cloud provider.**
  Workarounds that are still worth documenting (priority order):
  1. **Check local cache first** — before every fetch test: `if os.path.exists(SAVE_DIR/{video_id}_fulltext.txt)` with a real-size check (≥ 25 KB for full episodes). Cache hit → skip fetch.
  2. **Use a residential proxy or VPN** — required for a clean fetch from a cloud environment. Document the IP-block condition in `_failed.txt` and move on.
  3. **Pre-fetch on a non-cloud machine** — store the result locally, guarantee no block. Copy files into `/opt/data/content/youtube-raw/` to satisfy the pipeline without a live fetch.
  4. **yt-dlp** — *can* be installed in this environment via `uv pip install --python /tmp/yt-venv/<py>/bin/python yt-dlp`; you will see yt-dlp downloading and `yt-dlp --version` reporting success. **However, execution from this cloud IP is still blocked.** Install it for other reasons; don't expect it to bypass the IP block. `yt-dlp`'s own stderr clearly shows `WARNING: [youtube] [SSL: UNEXPECTED_EOF_WHILE_READING]` before giving up.
  5. **Do NOT attempt** `timedtext` signed-URL fetching via `curl` as a "workaround" — it returns the same Google IP-block page (1103 bytes, `<title>Sorry...</title>`). This surface is blocked regardless of client library.
  6. **Zero-segment stub (non-zero fulltext)**: When `_fulltext.txt` already contains 20K+ bytes of real text but `_transcript.txt` is 0-byte (because all live fetch attempts failed, leaving only the cached fulltext), the correct action is to re-segment from fulltext using proportional paragraph splitting — treat this as a full-cache hit, not a "missing transcript" bail.
- **Zero-segment stub (prefetched-failure)**: When `_fulltext.txt` is under 500 bytes, or contains error strings (`yt-dlp returned`, `Transcript unavailable`, `unavailable`, `Video:`), it is a stub from a prior failed run — not real content. Leave `segments: 0` in `_meta.json` and skip the video. Only mark as verbatim-transcript-complete after size ≥ 500 bytes passes the sniff test.
- **Mini-stub: chapter-only header file**: When `_transcript.txt` is non-zero (e.g., 500 B – 2 KB) but every line is just a timestamped chapter heading (`M:SS Title`) with no spoken-word body text, the file is a cloud-IP stub, not a real transcript. Detect by checking whether every line (after regex timestamp strip) starts with a title-case word and the total sentence count after stripping is insignificant. **Do not treat such files as real transcripts** — write `segments: 0` to `_meta.json` and do not add the video to `unique_videos`. The real next step is a residential proxy or cached fulltext from an alternative source.

## Critical Pitfalls for Batch / Automated Workflows

### Subprocess return code MUST be checked before parsing output

When `fetch_transcript.py` exits non-zero, it **always** writes its JSON error payload to stdout (not stderr). If your wrapper script skips the return-code check, it will parse the error JSON as if it were a success, writing empty/failed files and mistakenly marking the video as processed.

**Bad pattern — silently accepts error JSON:**
```python
result = subprocess.run(..., capture_output=True, text=True, ...)
data = json.loads(result.stdout)   # Return code never checked!
```

**Correct pattern:**
```python
result = subprocess.run(..., capture_output=True, text=True, ...)
if result.returncode != 0:         # Reject before parsing
    return None                    # Treat as failed
try:
    data = json.loads(result.stdout.strip())
    if isinstance(data, dict) and "error" in data:
        return None                # Explicit error field → failed
except json.JSONDecodeError:
    return None                    # Not valid JSON → failed
```

---

### Zero-segment responses: `full_text` is populated but `segments` is `[]`

Under certain conditions (rate-limit responses, cached partial data, transient window) `youtube-transcript-api` can return a valid response where `full_text` contains real content but `segments` is an empty list. **Do not treat this as a failure** — save the fulltext and mark the video as partially-acquired or re-queue it for a retry with a longer delay. A 25–90 KB `full_text` with 0 segments means the transcript is available; it was just not segmented in that response.

Detection:
```python
segs = data.get("segments", [])
ft = data.get("full_text", "")
has_real_text = bool(re.sub(r"\s+", "", ft).strip())
if not segs and has_real_text:
    # Save fulltext — valid partial acquisition, not a hard failure
```

Save-format guidance for zero-segment results: write full `full_text` to `_fulltext.txt` (cleaned), write an empty `_transcript.txt`, and record `segments: 0` in `_meta.json`. The fulltext file alone is sufficient to confirm content was harvested.

## Pitfalls

- **youtube-transcript-api not installed**: The venv at `/opt/hermes/.venv` often lacks `youtube-transcript-api` and may not have `pip` available. The install also fails with `uv pip install` (permission denied writing to site-packages).
  **Correct workaround** — create a temporary venv:
  ```bash
  uv venv /tmp/yt-venv && uv pip install --python /tmp/yt-venv/bin/python youtube-transcript-api
  ```
  Then run scripts with that venv's Python:
  ```bash
  /tmp/yt-venv/bin/python SKILL_DIR/scripts/fetch_transcript.py "URL" --text-only --timestamps
  ```
  > Note: `uv pip install --user` may or may not be supported depending on the `uv` version installed.
  > **Do NOT use bare `python3`** — it may not be Python from `/opt/hermes/`.
  > **`/opt/hermes/.venv/bin/python3`** *can* carry `youtube-transcript-api` in this environment; if it fails, fall back to the temporary venv.

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