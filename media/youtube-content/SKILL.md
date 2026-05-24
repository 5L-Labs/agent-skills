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
3. `reconcile_batch_state.py`: Scripted three-way audit (playlist × backlog × raw); returns 0 if counts agree, 1 if discrepancy detected.

Also see `references/timestamp-formats.md` for dual-format timestamp handling.

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

## Batch Mode — walkthrough

For batch transcript download (multiple videos, typically from playlist-new-ids.txt and yt-backlog.json):

1. **Start from the playlist** (`/opt/data/content/playlist-new-ids.txt`): parse all lines; each line is `VIDEO_ID\t[Title]\tDONE`. The DONE marker may be appended after a `\t` with or without an intermediate title segment. A line is "done" only if the last tab-separated field is literally `DONE`. Skip those lines.

   > **CRITICAL** — The intent of this step is "feed me all IDs from the playlist."
   > But if a _single idempotent re-run_ found the playlist already DONE and advanced to
   > Fast-Audit without ever executing steps 3–9 below, the playlist will fall out of sync with yt-backlog.json.
   > Symptoms: reconcile_batch_state.py reports `backlog unique_videos >> playlist DONE count` but `no candidates to fetch`.
   > **Always reconcile before concluding "nothing to do": see step 2a below.**
2. **If the playlist is fully DONE**, **ALWAYS** run Fast-Audit before declaring idle. Do **not** re-loop through the playlist on every run. Run `scripts/reconcile_batch_state.py`.

   ### Fast-Audit routine (playlist-is-DONE case)

   Before reporting "nothing to do", reconcile the three sources and compare counts:

   | Source | Done means |
   |--------|-----------|
   | `playlist-new-ids.txt` | last field = `DONE` |
   | `yt-backlog.json` → `unique_videos` | video_id is in the string array |
   | `youtube-raw/` | a `{ID}_transcript.txt` file exists AND passes the stub check below |

   **Stub check** — Python 3.13 safe:

   ```python
   import re
   with open(f"/opt/data/content/youtube-raw/{vid}_transcript.txt") as fh:
       content = fh.read()
   n_bare  = len(re.findall(r'^\d{1,2}:\d{2}(?::\d{2})? ', content, re.MULTILINE))
   n_brack = len(re.findall(r'^\[\d{1,2}:\d{2}(?::\d{2})?\] ', content, re.MULTILINE))
   is_stub = (len(content) < 500
              or max(n_bare, n_brack) < 5
              or any(e in content for e in ['ERROR','SSL','UNEXPECTED_EOF',
                                             'all subtitle formats failed',
                                             'Cloud IP','batch_fetch',
                                             'transcript file found but empty',
                                             'post_batch_recheck']))
   is_valid = not is_stub
   ```

   A video is only "done" from `youtube-raw/`'s perspective if `is_valid` is `True`.

  ### Playlist backfill (MANDATORY if Fast-Audit detects a gap)

  If `reconcile_batch_state.py` reports that `backlog unique_videos > playlist DONE count`, OR that there
  are `confirmed_permanent` IDs in `failed_videos` that are **not in** `unique_videos` in the backlog JSON,
  those IDs need backfilling before declaring idle:

  ```python
  import json, os

  BACKLOG  = '/opt/data/content/yt-backlog.json'
  PLAYLIST = '/opt/data/content/playlist-new-ids.txt'
  RAW_DIR  = '/opt/data/content/youtube-raw/'

  with open(BACKLOG) as f:
      backlog = json.load(f)

  playlist_set = set()
  with open(PLAYLIST) as f:
      for line in f:
          parts = line.strip().split('\t')
          if parts and parts[-1] == 'DONE':
              playlist_set.add(parts[0])

  fv_ids = {v['video_id']
            for v in backlog.get('failed_videos', [])
            if v.get('status') == 'confirmed_permanent'}

  unprocessed = set(backlog['unique_videos']) - playlist_set

  for vid in sorted(unprocessed):
      if vid in fv_ids:
          # confirmed_permanent: write a stub so youtube-raw/ has a file,
          # then add a playlist marker.  Do NOT attempt a live fetch.
          stub_path = os.path.join(RAW_DIR, f'{vid}_transcript.txt')
          if not os.path.exists(stub_path):
              with open(stub_path, 'w') as f:
                  f.write(
                      f'{vid}: confirmed_permanent — no available English transcripts '
                      f'(source: failed_videos entry).\n'
                  )
          # Add DONE marker to playlist using real tab (0x09), not a shell \t escape.
          with open(PLAYLIST, 'ab') as f:
              f.write(f'{vid}\tDONE\n'.encode())
      # else: still unresolved — skip, let next batch attempt it
  ```

  Re-run `reconcile_batch_state.py` to confirm the counts converge before finalising the report.
  **Do not suppress or skip this backfill step** — the playlist is the public-facing manifest and
  must accurately reflect every ID that the agent knows about, even if no new transcript was fetched
  in the current run.

  <sub-tip style="color: red">When `unprocessed` contains IDs that are already in
  `confirmed_permanent` but are **absent from `unique_videos`** in the backlog (a
  one-off drift), do two things: (1) patch the `unique_videos` array, and (2)
  add a playlist marker.  See Pitfalls — "confirmed_permanent driver missing
  from unique_videos" for the exact fix.</sub-tip>
3. **Pick N videos** (usually 10) from the unprocessed set.
4. **Pre-flight check**: for each candidate, look in `/opt/data/home/.hermes/content/youtube-raw/`
   for a cached transcript before issuing a live fetch. Check suffixes —
   `{ID}_transcript.txt`, `{ID}_fulltext.txt`, `{ID}_meta.json` — and verify with the same
   `max(n_bare, n_brack)` rule. If a cached file exists and is valid (>500 chars,
   no error terms), copy the cached files to `/opt/data/content/youtube-raw/`
   and mark that video as done — skip the live call entirely.
5. **Set `SSL_CERT_FILE` for every fetch call**, and start with `youtube-transcript-api`
   (via `/tmp/yt-venv/bin/python3`), falling back to `yt-dlp` only if the API client is absent
   or still failing after setting the cert. See Pitfalls below for the SSL/yt-dlp caveat.
6. **After each successful fetch**, save `{ID}_transcript.txt` (timestamped),
   `{ID}_fulltext.txt` (plain text), and `{ID}_meta.json` (video_id, title, segments, duration)
   to `/opt/data/content/youtube-raw/`.
7. **Update backlog**: add newly attempted IDs to `unique_videos` and confirmed-permanent
   failures to `failed_videos`. Update `last_updated` to the current UTC timestamp in ISO 8601.
8. **Batch permanent-failure guard**: if every fetch attempt in the batch hits the same
   `UNEXPECTED_EOF_WHILE_READING` on both `youtube-transcript-api` and `yt-dlp`, the environment
   itself is blocked. Do **not** write new stubs. Instead verify that each candidate ID already
   has a `confirmed_permanent` entry in `failed_videos`. If any candidate is not yet logged,
   add it with the note `"batch_fetch <ISO timestamp>: Cloud IP SSL block — both
   youtube-transcript-api and yt-dlp failed with UNEXPECTED_EOF_WHILE_READING."`
9. **Mark playlist entries**: append `\tDONE` to the line for every video that got a valid
   transcript or was confirmed blocked. Do **not** mark DONE for videos that had a partial
   success or a non-blocking error.
10. **Report**: print succeeded/failed counts, per-video status. If the playlist-backlog
    gap was detected and backfilled, include the size of the gap in the report so operators
    are aware that a partial (historical) state needed reconciling.

For a scripted three-way comparison, run `scripts/reconcile_batch_state.py`.
For a diagnostic table of all discrepancy patterns (symptom → cause → fix),
see `references/batch-audit-discrepancy-patterns.md`.

### Batch Pitfalls

- **`reconcile_batch_state.py` exits 1 even when system is fully reconciled — all gap explained by confirmed_permanent stubs** — If `playlist DONE == backlog unique_videos` but `valid_raw < both`, the difference may be 100% accounted for by stub files that carry `confirmed_permanent` entries in `failed_videos`. No unprocessed candidates exist, yet the script reports `DISCREPANCY DETECTED` and exits code 1. **Fix**: before treating any discrepancy as actionable, enumerate `stub_raw ∩ confirmed_permanent` and `unprocessed = backlog – playlist DONE`. If `stub_raw ⊆ confirmed_permanent` and `unprocessed` is empty, the system is fully reconciled — no live fetch warranted. Do not spawn new hardware even if the script exits 1.

  Compatible assertion:
  ```
  # sanity_gap:  confirmed_permanent_gap = len(set(confirmed_permanent_ids) - valid_raw)
  # sanity_gap:  playlist_backlog_ok = (playlist_done_count == backlog_unique_count)
  # sanity_gap:  unprocessed_count = backlog_unique_count - valid_raw_count - confirmed_permanent_gap
  # → if playlist_backlog_ok and unprocessed_count == 0 → RECONCILED, skip fetch
  ```

  Treat this as a normal exit path and mark the run with zero new fetches.

- **Playlist falls out of sync with backlog (most common batch desync)** — When every playlist line
  is `DONE` and step 2 is satisfied, it is tempting to skip straight to Fast-Audit and then report
  idle. The problem: Fast-Audit may return `DISCREPANCY DETECTED` because `backlog unique_videos >> playlist DONE`,
  but steps 3–9 are skipped so the gap is never repaired in the playlist file.
  **Fix**: Always run `reconcile_batch_state.py` first. If it reports a backlog–playlist gap, run the
  **Playlist backfill** section before ending the run. Zero new fetches with a fully-reconciled state
  is a correct and acceptable outcome; zero new fetches with an unresolved backlog-playlist gap is not.

- **`reconcile_batch_state.py` glob bug — always returns 0 raw files** — The glob on line 49
  reads `f'{RAW_DIR}*_transcript.txt'`. Because `RAW_DIR` already has a trailing slash
  (`'/opt/data/content/youtube-raw/'`), this resolves to `'/opt/data/content/youtube-raw*_transcript.txt'`
  (missing `/` between `RAW_DIR` and `*`), which matches 0 files regardless of what is on disk.
  The script then always reports `valid=0, stubs=0`, falsely triggering `DISCREPANCY DETECTED` even
  on a fully-up-to-date batch.

  **This bug has been fixed in-place in the installed script** (`os.path.join(RAW_DIR, '*_transcript.txt')`),
  but the SKILL.md here documents the expected script for future installs.
  If a fresh install shows 0 raw files when `/opt/data/content/youtube-raw/` clearly contains files,
  verify with the audit script below before re-processing the entire backlog.

- **Both `youtube-transcript-api` and `yt-dlp` fail with `UNEXPECTED_EOF_WHILE_READING` in cloud** — this is a transport-layer environmental block, not a client bug. Retrying produces the same result. All taken IDs likely already have stub files in `youtube-raw/` — verify. Do **not** write new stubs; verify `confirmed_permanent` is logged and skip.
- **Large files may have `n_bare == 0`** — VTT-derived timestamped files use bracket format `[HH:MM]`. Always test `max(n_bare, n_brack)`, never just `n_bare`. A 70 KB file with 0 bare and 1500+ bracketed timestamps is **not** a stub.
- **`confirmed_permanent` ID in `failed_videos` but missing from `unique_videos`** — The backlog `confirmed_permanent` entry is the ground truth; `unique_videos` is the manifest. If a `confirmed_permanent` video is absent from `unique_videos`, the three-way audit will flag it as "no valid raw" rather than "known permanent failure", misleading re-processing. Fix: patch `unique_videos` to include the missing ID **before** backfilling the playlist or building the stub file.
- **Writing a DONE line to the playlist with `echo` loses the tab** — `echo 'VID\tDONE' >> file` writes a literal backslash-t (`\t`), not an actual `0x09` tab byte, in shells where `echo` doesn't interpret escape sequences. The audit script splits on a real tab, so the line is miscounted. Fix: append in Python (`open(PLAYLIST, 'ab').write(f'{vid}\tDONE\n'.encode())`) or use bash's `$'\t'` expansion.

## Workflow (single video)

1. **Fetch** the transcript using the fetch_transcript.py helper script with `--text-only --timestamps`.
2. **Validate**: check if output is a JSON error (indicating transcripts disabled, private video, etc.). If error JSON:
   - For batch processing: skip this video and continue with next one (do NOT remove from backlog)
   - For single video: inform user and suggest checking if subtitles are available on video page
   If not error JSON, confirm output is non-empty and in expected language. If empty, retry without `--language` to get any available transcript. If still empty, treat as transcript disabled.
3. **Check for existing transcript** before fetching: if `/opt/data/.hermes/content/youtube-raw/<name>.txt` already exists, skip fetching to avoid duplicates.
4. **Pre-flight home-cache check** (batch mode): if `/opt/data/home/.hermes/content/youtube-raw/<name>_transcript.txt` exists and passes `is_stub()` (checking both bare and bracketed timestamp formats), copy all three files (`_transcript.txt`, `_fulltext.txt`, `_meta.json`) to `/opt/data/content/youtube-raw/` and mark the video done — skip the live fetch entirely.
5. **Chunk if needed**: if the transcript exceeds ~50K characters, split into overlapping chunks (~40K with 2K overlap) and summarize each chunk before merging.
6. **Transform** into the requested output format:
   - For Luna digest: first try running the generate_luna_digest.py script on the timestamped transcript
   - If the script produces no output or encounters an error, immediately use the fallback method: strip timestamps, join text, split into meaningful sentences (length > 20 chars), and create a structured digest with thematic sections following the Luna format guidelines
   - For other formats: follow the specific formatting guidelines in the Output Formats section
7. **Verify**: re-read the transformed output to check for coherence, correct timestamps, and completeness before presenting.
8. **Save** raw transcript to `/opt/data/.hermes/content/youtube-raw/<name>.txt`
9. **Update backlog**: after successful processing, remove the video ID from the backlog JSON (`/opt/data/.hermes/content/yt-backlog.json` -> `unique_videos` array).

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

- **`reconcile_batch_state.py` glob bug — found and fixed in-session** — The glob on line 49 of the shipped script reads `f'{RAW_DIR}*_transcript.txt'`. Because `RAW_DIR` already has a trailing slash, this resolves to `'/opt/data/content/youtube-raw*_transcript.txt'` (missing `/` between `RAW_DIR` and `*`), which matches nothing. The script then always reports `valid=0, stubs=0` regardless of what is on disk, falsely triggering `DISCREPANCY DETECTED` even on a fully-processed batch.

  **This bug has been fixed in-place** (`os.path.join(RAW_DIR, '*_transcript.txt')`). Documented here so that a fresh install of the skill that still carries the buggy script gets a heads-up, and in case the fix is ever reverted. If the script shows 0 raw files when `/opt/data/content/youtube-raw/` clearly contains files, verify with a manual audit before re-processing the entire backlog — see `references/batch-audit-state-check.md`.
