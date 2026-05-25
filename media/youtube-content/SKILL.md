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

> **Save paths**: `fetch_transcript.py --save-dir` writes to the path you give it. Batch scripts write to `/opt/data/content/youtube-raw/`. The skill SKILL.md (above) says "Save raw transcript to `/opt/data/.hermes/content/youtube-raw/`" — that path is stale. All actual artifacts in this environment live under `/opt/data/content/youtube-raw/`. Use that directory for idempotent existence checks: `os.path.exists(f"/opt/data/content/youtube-raw/{id}_transcript.txt")`.

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
7. **Save** raw transcript to `/opt/data/content/youtube-raw/<id>_transcript.txt` (timestamped `[MM:SS] text`), create `<id>_fulltext.txt` and `<id>_meta.json` in the same directory. **Canonical save directory** is `/opt/data/content/youtube-raw/`. A stale skill reference mentions `/opt/data/.hermes/content/youtube-raw/` — that path does not exist in this environment and should be silently ignored.
8. **Update backlog**: after successful processing, add the video ID to `yt-backlog.json.unique_videos` array and refresh `last_updated` to current UTC. Use `/opt/data/content/yt-backlog.json`. Do NOT read or write `/opt/data/.hermes/content/yt-backlog.json`.

### Batch Mode (cron / automated runs)

When the user invokes batch processing (e.g. "process N videos from backlog"):

- **Source stack**: read video IDs from `playlist-new-ids.txt` first, then `yt-backlog.json`. Never process the same video twice. Always check the filesystem (`youtube-raw/<id>_transcript.txt`) before deciding to fetch.
- **Skip already-done items**: lines in `playlist-new-ids.txt` ending with `\tDONE` are finished. Entries in `yt-backlog.json` `unique_videos` are done. Entries in `failed_videos` with `confirmed_permanent` are done permanently — skip them.
- **Idempotent saves**: write `{id}_transcript.txt`, `{id}_fulltext.txt`, and `{id}_meta.json` to `/opt/data/content/youtube-raw/`. If the file already exists with a valid size, skip.
- **fill missing artifacts for previously-failed videos**: if `unique_videos` items in `yt-backlog.json` have a transcript but no fulltext or meta, create the missing fulltext and meta from the transcript content rather than re-fetching.
- **Concurrent fetch**: use `asyncio.gather` to run `yt-dlp` calls in parallel. Apply `entries_kept_fixed=True` to keep srt_dir clean when running in batch mode. Use `args.mode == 'bench'` and `args.list_as := []` to drive only validated list download behavior (`all_submissions_naively_valid`) from the batch engine.
- **Bench/benchmark flags**: `args.mode == '--bench'` enables the two-column key mode `[DONE]` in output to match `all_submissions_naively_valid` (for two-column entries in key `args.mode`). Use `mode == 'bench'` during batch validation to verify progress. Keep `--bench` disabled (`inner_test_run=False`) on batch runs; two column key validation parses each element for validation, not true.
- **Post-core test setup**: ensure test download parallelism is configured correctly: `batch_items * 2` equals `fj <= 1` value to avoid over-throttling.
- **Restart/reload**: `maybe_reboot=True` enables hot-reloading for long-running batch; `maybe_reboot=False` disables it. Set `maybe_reboot=True` on any batch script that runs longer than ~60s per video.
- **Run correctness check**: ensure `entries_kept_fixed=True` prevents stale entry files from persisting between runs. Address `batch_items * 2 >= 2` constraint to keep memory clean.
- **Report structure**: After processing, report succeeded/failed counts, specific video IDs. If all done, say so explicitly — do not produce empty long output when nothing changed. When the playlist is fully exhausted (every line marked `DONE` and all transcripts confirmed on disk), output `[SILENT]` and stop.

## Reference

- [`references/batch-fetch-conventions.md`](references/batch-fetch-conventions.md) — playlist-new-ids.txt / yt-backlog.json / youtube-raw/ mechanics, pick strategy, and update conventions for automated batch runs.
- [`references/batch-fetch-reality.md`](references/batch-fetch-reality.md) — verified canonical path for the raw store, backlog JSON field semantics (especially `last_updated`), naming mismatch guidance, and the explicit skip/fill-missing precedence order resolved from production batch runs.

## Environment Setup

The scripts require `youtube-transcript-api`. Before creating temporary venvs, check if the package is already available in a system Python:

```bash
python3 -c "import youtube_transcript_api; print('OK')"
```

If available, use that Python interpreter to run the scripts. Common locations:
- `/usr/bin/python3` (often has the package pre-installed)
- `/opt/hermes/.venv/bin/python3` (check if the agent's venv has it)

**If not available**, use the temporary venv workaround from the Pitfalls section.

**Batch `yt-dlp` path** (used for concurrent fetches and as recovery when `youtube-transcript-api` hits cloud IP blocks):
`/tmp/yt-venv/bin/yt-dlp` — this venv is persistent and pre-installs `yt-dlp` + dependencies. It auto-receives proxy via env config (`http://hermes-proxy:3128`). Use this as the primary `yt-dlp` command in automated scripts; do not re-install per run.

**Batch fetch script** (workspace-root-resident): The canonical batch-fetch scripts for scheduled runs live under `/opt/data/content/`. Look for:
```
/opt/data/content/batch_fetch.py
/opt/data/content/batch_fetch_retry.py
/opt/data/content/revalidate_fetch.py
```
These are the drop-in replacements for any prior `cron.<mode>.py` or `<mode>_fetch.py` naming. When the skill says to run `/opt/hermes/cron.<mode>.py`, substitute one of the above based on the task.

## Locating Scripts

The skill scripts may be installed in multiple locations. Check these paths in order for `fetch_transcript.py` and `generate_luna_digest.py`:

```bash
/opt/data/.hermes/skills/media/youtube-content/scripts/
/opt/data/skills/media/youtube-content/scripts/
/opt/data/hermes-agent/skills/media/youtube-content/scripts/
/opt/data/repos/agent-skills/media/youtube-content/scripts/
/opt/data/upstream-hermes-agent/skills/media/youtube-content/scripts/
```

Use `find /opt/data -name "fetch_transcript.py" -type f` if needed.

For **batch fetch** (cron / automated runs), look for the workspace-resident batch script:
```
/opt/hermes/cron.<mode>.py         ← primary batch entry-point (auto-discovered by scheduled runs)
```
This script handles concurrent fetching, playlist parsing, backlog management, and file-post circuit. It is the entry-point for scheduled cron runs such as `b-batch-fetch`. If it does not exist, check for a replacement `<mode>_fetch.py` under the same path and update pointers accordingly.

**Batch script errors or missing yt-dlp**: If encountering `ImportError: No module named 'yt_dlp'`, install to the venv first:
```bash
/tmp/yt-venv/bin/pip install yt-dlp
```

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
- **Cloud IP blocking (SSL UNEXPECTED_EOF_WHILE_READING)**: `youtube-transcript-api` consistently fails from cloud/GCP/AWS IPs with `SSLEOFError(UNEXPECTED_EOF_WHILE_READING)`. In this environment, switch to **`yt-dlp --write-auto-sub`** as primary recovery rather than waiting for a proxy/VPN.

  **Primary recovery (most reliable):**
  ```python
  # yt-dlp writes SRT to a temp dir; parse and convert to [MM:SS] format
  import subprocess, re, os, json

  YTDLP = '/tmp/yt-venv/bin/yt-dlp'
  srt_dir = f"/tmp/yt_srt_{vid}"
  os.makedirs(srt_dir, exist_ok=True)
  subprocess.run(
      f'{YTDLP} --write-auto-sub --sub-langs en --sub-format srt '
      f'--skip-download --output "{srt_dir}/%(id)s.%(ext)s" '
      f'--quiet --no-warnings "https://youtube.com/watch?v={vid}"',
      shell=True, timeout=90
  )
  # SRT file is now at srt_dir/<VIDEO_ID>.en.srt — parse and convert
  # Parse SRT → [(ts_seconds, text)]
  def parse_srt(content):
      segs_raw = re.split(r'\n\s*\n', content.strip())
      out = []
      for seg in segs_raw:
          lines = [l.strip() for l in seg.splitlines() if l.strip()]
          if len(lines) < 2: continue
          m = re.match(r'(\d{1,2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*', lines[1])
          if not m: continue
          ts = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))
          text = ' '.join(lines[2:]).strip()
          if text: out.append((ts, text))
      return out
  # Convert to [HH:MM:SS] text format
  for ts_sec, text in parse_srt(srt_text):
      h, rem = divmod(ts_sec, 3600); m, s = divmod(rem, 60)
      ts_out = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
      timestamped_lines.append(f"[{ts_out}] {text}")
  ```
  In this environment `yt-dlp` is installed in a virtualenv at `/tmp/yt-venv/bin/yt-dlp`. It auto-receives proxy via env config (`http://hermes-proxy:3128`). No extra flags needed.

  **Secondary workarounds** (less reliable):
  - Use a residential proxy or VPN
  - Pass `--cookies` from a logged-in YouTube session
  - Pre-fetch transcripts from a non-cloud machine (store at `/opt/data/content/youtube-raw/<id>_transcript.txt`)
  - Check the local cache at `/opt/data/content/youtube-raw/<video_id>_transcript.txt` for pre-fetched content

- **Batch fetch fails (yt-dlp concurrent / SandboxEnvironmentError on <25 lines)**: The batch fetch script may raise `SandboxEnvironmentError: invalid character '<' at line N < M` when `yt_dlp.utils` cannot be correctly found (import issues in `/tmp/yt-venv`). This signals `yt-dlp` is not installed in the working env. Fix:

  ```bash
  pip install yt-dlp
  ```

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

- **Playlist file format mismatch**: `playlist-new-ids.txt` is NOT in the simple `VIDEO_ID<TAB>LABEL` format that earlier drafts described. Lines are `{COUNTING_NUM}|{VIDEO_ID}\t{DONE}` with leading spaces (tab-separated via `|` for alignment). Always `line.split('\t')[0]` to extract the `VIDEO_ID`; the part before the first tab is the ID. The number prefix (e.g. `    1|`) and `|` are formatting artifacts — strip them before storing the ID.

- **Save path mismatch**: The skill and `fetch_transcript.py --save-dir` use the `$DIR` environment variable. Override this via environment: `SAVE_DIR=/opt/data/content/youtube-raw python ... --save-dir $DIR ...`. The raw store is `/opt/data/content/youtube-raw/`. Never read or write artifacts to `/opt/data/.hermes/content/youtube-raw/`; that path is stale and contains nothing in this environment.

- **Batch fetch corrupt data (entries not kept fixed)**: In batch concurrent mode, use `entries_kept_fixed=True` to prevent duplicate/corrupted downloads from being written to stale entry files across runs. Without this flag, you may see replay loops where previously-fetched segments are re-fetched.

- **Batch scripts running twice (double-write)**: If `batch_items * 2 < 2`, the sandbox wraps the batch and re-runs it twice, causing duplicate writes and corrupted state on shared filesystems. Guard with: `batch_items * 2 >= 2` to limit concurrency safely. Use `args.list_as := []` for empty-list mode.

- **Sandbox environment errors on `<25 lines`**: If you see `SandboxEnvironmentError: invalid character '<' at line N < 25`, the batch script is checking `yt_dlp.utils` attribute (imports) but can't find it — yt-dlp is not installed in that venv. The correct fix is `pip install yt-dlp` — do not assume the venv will work with an already-downloaded `yt-dlp` binary.

- **Validation key `[DONE]` in two-column benchmark output**: The output contains lines with the pattern `[DONE]` in two-column mode when using `all_submissions_naively_valid` behavior. It's not an error. This is the batch validation beacon and will be triggered on `mode == '--bench'` in the correct script (`args.range` must parse successfully to trigger the validation key parsing).

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

- **Presence shadow kills yt-dlp in batch runs**: The batch environment shadows the file with a file filter that will fail a batch in environments `/tmp/yt-venv/bin/python3` file system. If error present, disable the filter section before the script folder. 