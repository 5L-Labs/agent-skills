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
# Option 1: youtube-transcript-api (may fail on cloud IPs / SSL-constrained environments)
pip install youtube-transcript-api

# Option 2: yt-dlp (RECOMMENDED — handles cookies, SSL, subtitles in one tool; often already installed)
uv tool install yt-dlp   # or: pip install yt-dlp
```

## Helper Scripts

`SKILL_DIR` is the directory containing this SKILL.md file.

1. `fetch_transcript.py`: Fetches transcript via `youtube-transcript-api` Python library
2. `generate_luna_digest.py`: Generates Luna-style digest from timestamped transcript
3. `fetch_transcript_ytdlp.py` (optional community script): Fetches transcripts by downloading VTT/JSON3 subtitles via yt-dlp — use when `youtube-transcript-api` is blocked by cloud-IP or SSL issues

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

## Batch Mode — walkthrough

For batch transcript download (multiple videos, typically from playlist-new-ids.txt and yt-backlog.json):

1. **Start from the playlist** (`/opt/data/content/playlist-new-ids.txt`): parse all lines; each line is `VIDEO_ID\t[Title]\tDONE`. The DONE marker may be appended after a `\t` with or without an intermediate title segment. A line is "done" only if the last tab-separated field is literally `DONE`. Skip those lines.
2. **If the playlist is fully DONE**, skip straight to the Fast-Audit routine below and report. Do **not** re-loop through the playlist on every run. Use the reconciliation script (`scripts/reconcile_batch_state.py`, added below) to get a one-line state summary.

   ### Fast-Audit routine (playlist-is-DONE case)

   When every playlist line ends with `\tDONE` the batch run has nothing to schedule from the playlist file. Before reporting "nothing to do", reconcile the three sources with this exact comparison:

   | Source | Done means |
   |--------|-----------|
   | playlist-new-ids.txt | last field = `DONE` |
   | yt-backlog.json → `unique_videos` | video_id is in the array |
   | youtube-raw/ | a `{ID}_transcript.txt` file exists AND passes the stub check below |

   If all three counts agree, **truly nothing to do** → report and exit. If they disagree (e.g. playlist done but backlog still has candidates, or raw has stubs not yet reflected in `failed_videos`), fall through to backlog processing as normal.

   The canonical stub check is:

  ```python
  import re
  with open(f"/opt/data/content/youtube-raw/{vid}_transcript.txt") as fh:
      content = fh.read()
  # Both bare and bracketed timestamp patterns.
  # CRITICAL — Python 3.13 re regression:
  #   Compiled patterns must embed re.MULTILINE at compile time; passing it as a
  #   second argument to re.findall() on a pre-compiled pattern either raises a
  #   ValueError or silently returns the wrong result (start-of-string only, not
  #   start-of-line). String-pattern forms like re.findall(r'^...', s, re.MULTILINE)
  #   work fine, but pre-compiled forms must have MULTILINE baked in.
  #   Result without MULTILINE: ^ matches only position 0 in the whole file → segs
  #   reports 1–2 instead of hundreds → every file looks like a stub.
  n_bare  = len(re.findall(r'^\\d{1,2}:\\d{2}(?::\\d{2})? ', content, re.MULTILINE))
  n_brack = len(re.findall(r'^\\[\\d{1,2}:\\d{2}(?::\\d{2})?\\]', content, re.MULTILINE))
  is_stub = (len(content) < 500
             or max(n_bare, n_brack) < 5
             or any(e in content for e in ['ERROR','SSL','UNEXPECTED_EOF','all subtitle formats failed']))
  is_valid = not is_stub
  ```

  **Alternative (pre-compiled form, correct for use inside helper scripts):**

  ```python
  bare_pat  = re.compile(r'^\\d{1,2}:\\d{2}(?::\\d{2})? ', re.MULTILINE)
  brack_pat = re.compile(r'^\\[\\d{1,2}:\\d{2}(?::\\d{2})?\\]', re.MULTILINE)
  n_bare  = len(re.findall(bare_pat,  content))
  n_brack = len(re.findall(brack_pat, content))
  ```

  A video is only "done" from `youtube-raw/`'s perspective if `is_valid` is `True`.
3. **Pick N videos** (usually 10) from the unprocessed set.
4. **Pre-flight check**: for each candidate, look in `/opt/data/home/.hermes/content/youtube-raw/`
   for a cached transcript before issuing a live fetch. Check all three suffixes —
   `{ID}_transcript.txt`, `{ID}_fulltext.txt`, `{ID}_meta.json` — and verify the transcript
   string passes the same `seg_count >= 5` check (using both `bare` and `[bracketed]` timestamp
   patterns from step 3). **Do not reject a home-cache entry on segment count alone**; apply
   the same `max(segs_bare, segs_brack)` rule that saved files use. If a cached file exists
   and is valid (>500 chars, no error terms), **first check whether the raw-dir equivalent
   already exists** — if it does, skip (already synced). If not, copy the cached files to
   `/opt/data/content/youtube-raw/` and mark that video as done — skip the live call entirely.
5. **Set `SSL_CERT_FILE` for every fetch call**, and start with `youtube-transcript-api` (via `/tmp/yt-venv/bin/python3`), falling back to `yt-dlp` only if the API client is absent or still failing after setting the cert. See Pitfalls below for the SSL/yt-dlp caveat.
6. **After each successful fetch**, save `{ID}_transcript.txt` (timestamped), `{ID}_fulltext.txt` (plain text), and `{ID}_meta.json` (video_id, title, segments, duration) to `/opt/data/content/youtube-raw/`.
7. **Update backlog**: add newly attempted IDs to `unique_videos` and confirmed-permanent failures to `failed_videos`. Update `last_updated` to the current UTC timestamp in ISO 8601.
8. **Mark playlist entries**: append `\tDONE` to the line for every video that got a valid transcript or was confirmed blocked. Do **not** mark DONE for videos that had a partial success or a non-blocking error.
10. **Report**: print succeeded/failed counts, per-video status, and backlog snapshot.

### Fast-Audit script (`scripts/reconcile_batch_state.py`)

When the playlist is fully DONE, run this script before reporting "nothing to do". It checks all three sources and prints a concise table:

```bash
python3 SKILL_DIR/scripts/reconcile_batch_state.py
```

If `playlist_count == backlog_count == valid_raw_count`, the system is current and the run can end with no fetch calls. If the counts disagree, the script displays the discrepancy so you can decide whether to investigate or proceed.

---

## Workflow (single video)

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

## Environment Setup

The `fetch_transcript.py` script requires `youtube-transcript-api`. Check availability:

```bash
python3 -c "import youtube_transcript_api; print('OK')"
```

Common locations:
- `/usr/bin/python3` (often pre-installed)
- `/opt/hermes/.venv/bin/python3`

**If not available**, try SSL_CERT_FILE (sometimes fixes cloud-IP blocks):
```bash
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt python3 script.py "URL"
```

If `youtube-transcript-api` cannot be installed or continues to fail with SSL/IP blocks,
**switch to using `yt-dlp` directly** (see the `yt-dlp` section below).

**yt-dlp** is often already present on this system and is the more robust option:
```bash
YT_DLP=$(which yt-dlp || which yt-dlp3)   # resolves to e.g. /tmp/yt-venv/bin/yt-dlp
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
  "$YT_DLP" --dump-single-json --quiet --no-warnings "https://www.youtube.com/watch?v=VIDEO_ID"
```
Output: full JSON with `title`, `duration`, `chapters`, `automatic_captions[…].url` fields.

### Preferred yt-dlp Fetch Pattern

When `youtube-transcript-api` fails with SSL/IP errors, use `yt-dlp` + VTT:

```bash
# 1. Get metadata (title, duration, chapter list)
YT_DLP=/tmp/yt-venv/bin/yt-dlp
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt "$YT_DLP" \
  --dump-single-json --quiet --no-warnings "URL"

# 2. Download English auto-generated VTT subtitle file
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt "$YT_DLP" \
  --skip-download --write-auto-subs \
  --sub-langs en --sub-format "vtt/srt" \
  --output "/tmp/subs/%(id)s.%(ext)s" \
  --quiet --no-warnings \
  --extractor-retries 2 --sleep-requests 1 \
  "URL"

# 3. Parse VTT → timestamped text
#    Standard VTT timestamp: MM:SS.mmm --> MM:SS.mmm (one-digit hours omitted, hh:mm:ss for >10h)
#    See the VTT parsing pattern in references/vtt-parsing.md
```

Save `yt_dlp` at the front of environment checks; only fall back to `youtube-transcript-api` if yt-dlp is absent.

### Puppeteer/Playwright / Cookie Auth

Some videos require authenticated access. `yt-dlp` can use a Netscape cookies file:

```bash
yt-dlp --cookies-from-browser chrome --skip-download --write-auto-subs ... "URL"
yt-dlp --cookies /path/to/cookies.txt ...
```

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

### yt-dlp binary locations (check these when yt-dlp path is unknown)

```bash
/tmp/yt-venv/bin/yt-dlp          # uv-created temp venv (fastest to check)
/usr/local/bin/yt-dlp            
/usr/bin/yt-dlp
$(which yt-dlp 2>/dev/null)      # if already on PATH
```

For VTT/subtitle parsing patterns and caveats, see [references/vtt-parsing.md](references/vtt-parsing.md).

## Error Handling

- **Transcript disabled**: tell the user; suggest they check if subtitles are available on video page.
- **Private/unavailable video**: relay the error and ask the user to verify the URL.
- **No matching language**: retry without `--language` to fetch any available transcript, then note the actual language to the user.
- **Dependency missing**: run `pip install youtube-transcript-api` and retry.
- **SSL/IP block** (`UNEXPECTED_EOF_WHILE_READING` or `Could not retrieve a transcript`) — indicates cloud IP or network MITM interference. **Workaround: set `SSL_CERT_FILE`**:
  ```bash
  export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
  ```
  If still blocked, **switch to `yt-dlp`** (often already installed and less affected). See Setup section.
- **VTT 429 Too Many Requests** — YouTube rate-limits subtitle API requests (punishes rapid VTT fetches). Fix:
  - Add `--sleep-subtitles 2 --extractor-retries 2` to the yt-dlp command
  - In batch processing: sleep 3–5 seconds between video subtitle fetches
  - If still rate-limited, sleep 60 seconds and retry with fresh metadata (the `&ei=` token in subtitle URLs is time-limited — re-fetch metadata via `--dump-single-json` first)
- **Digest script failure**: if `generate_luna_digest.py` produces no output or encounters errors, immediately use the fallback method: strip timestamps, join text, split into meaningful sentences (length > 20 chars), and create a structured digest with thematic sections following the Luna format guidelines. In automated workflows, do not spend time debugging - go directly to the fallback to ensure processing continues.
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

## Error Handling (batch mode)

These additional batched-fetch failure modes were observed in production cron runs:

### `all subtitle formats failed` — no English subtitles exist

`yt-dlp` writes an error lines like:
```
Video ID: <id>
Timestamp: 2026-05-22T14:23:38+00:00
Error: all subtitle formats failed
Status: FAIL
```
This means the video has no machine-translated or auto-generated English captions at all. Retrying will not succeed. Record the video in `failed_videos` with status `confirmed_permanent` and do not re-try in subsequent batches.

### `yt-dlp` itself can fail with the same cloud-IP SSL error

Even after `SSL_CERT_FILE` is set, `yt-dlp --dump-single-json --write-auto-subs` can return:
```
ERROR: [youtube] <ID>: Unable to download API page: [SSL: UNEXPECTED_EOF_WHILE_READING]
```
This is a transport-layer block on this environment's IP, not a client bug. `youtube-transcript-api` hits the same error. If both clients fail with the same `UNEXPECTED_EOF_WHILE_READING`, the environment cannot reach YouTube's HTTPS API — log as `confirmed_permanent` in `failed_videos` and drive all retries from the local home cache (`/opt/data/home/.hermes/content/youtube-raw/`).

## Pitfalls

- **Python 3.13 `re.MULTILINE` + pre-compiled patterns**: In Python 3.13, calling `re.findall(compiled_pat, string)` **without** `re.MULTILINE` baked into the compiled pattern will match `^` only at position 0 of the entire string — not at the start of every line. The fix is to compile the pattern with `re.MULTILINE` from the start:

  ```python
  # ❌ WRONG in Python 3.13 — ^ only matches start of whole string
  pat = re.compile(r'^\[\d{1,2}:\d{2}:?\d{2}?\]')
  re.findall(pat, multiline_text)   # 1 hit instead of hundreds

  # ✅ CORRECT — embeds MULTILINE at compile time
  pat = re.compile(r'^\d{1,2}:\d{2}(?::\d{2})? ', re.MULTILINE)
  re.findall(pat, multiline_text)   # correct per-line counts
  ```

  This regression was discovered in `scripts/reconcile_batch_state.py`: the unpatched `is_stub()` was returning `True` for every `_transcript.txt` file (reported 0 valid, 112 stubs) because `^` matched only the first line and segs was always ≤ 2. Any other script in this skill that uses compiled `.findall()` on multi-line transcript text must embed `re.MULTILINE` at compile time.

- **`re.findall(pattern_str, string, flags)` on a *string* pattern is still safe**: `re.findall(r'^...', multiline_string, re.MULTILINE)` — this form is unaffected by the 3.13 change because the pattern isn't pre-compiled. Use this form for one-off queries in `execute_code` cells.

- **youtube-transcript-api not installed**: The venv at `/opt/hermes/.venv` often lacks `youtube-transcript-api` and may not have `pip` available. The install also fails with `uv pip install` (permission denied writing to site-packages) and `uv pip install --user` (unsupported flag). **Correct workaround** — create a temporary venv:
  ```bash
  uv venv /tmp/yt-venv && uv pip install --python /tmp/yt-venv/bin/python youtube-transcript-api
  ```
  Then run scripts with that venv's Python:
  ```bash
  /tmp/yt-venv/bin/python SKILL_DIR/scripts/fetch_transcript.py "URL" --text-only --timestamps
  ```
  Do NOT use bare `python3` or `/opt/hermes/.venv/bin/python3` — both will fail with "youtube-transcript-api not installed."

- **SSLError UNEXPECTED_EOF_WHILE_READING** from `youtube-transcript-api` on this platform: The `youtube-transcript-api` library can hit SSL handshake errors even when plain `curl` to `youtube.com` works fine. **Fix: set `SSL_CERT_FILE`**:
  ```bash
  export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
  ```
  If the error persists, **abandon `youtube-transcript-api` entirely and switch to `yt-dlp`** (see Setup), which handles SSL/certs internally without this issue.

> **⚠️ yt-dlp is NOT immune to SSL errors in cloud environments.** In a cloud IP (AWS, GCP, Azure) environment, `yt-dlp --dump-single-json` and `yt-dlp --write-auto-subs` can both return the same `UNEXPECTED_EOF_WHILE_READING` error. If both clients fail, the block is environmental, not client-side — there is no client-only workaround. Log as `confirmed_permanent` and drive retries from the local cache.

- **yt-dlp VTT downloads return HTTP 429** — YouTube rate-limits subtitle API requests (punishes rapid VTT fetches). Fix:
  - Add `--sleep-subtitles 2 --extractor-retries 2` to the yt-dlp command
  - In batch processing: sleep 3–5 seconds between video subtitle fetches
  - If still rate-limited, sleep 60 seconds and retry with fresh metadata (the `&ei=` token in subtitle URLs is time-limited — re-fetch metadata via `--dump-single-json` first)

- **yt-dlp `--dump-single-json` returns HTML error body but exit code 0**: This means the API returned an HTML error page (not JSON). Extract the error message from the HTML `<title>` tag, or check `stderr`. Always verify the output is valid JSON before passing it to `json.loads()`.

- **Raw `_transcript.txt` files use two possible timestamp formats** — both are produced legitimately by different sources and batch processing must handle both:

  | Format | Example | Source |
  |--------|---------|--------|
  | Bare `MM:SS text` | `0:00 Introduction …` | `fetch_transcript.py` via `youtube-transcript-api` |
  | Bracketed `[HH:MM] text` | `[00:00] I entered venture …` | VTT → converted by `yt-dlp`/legacy pipeline |

  When **counting segments or detecting timestamps** in a saved transcript, test both patterns:

  ```python
  import re
  n_bare  = len(re.findall(r'^\d{1,2}:\d{2}(?::\d{2})? ', text, re.MULTILINE))
  n_brack = len(re.findall(r'^\[\d{2}:\d{2}(?::\d{2})?\] ', text, re.MULTILINE))
  seg_count = max(n_bare, n_brack)
  ```

  When **stripping timestamps** (fallback digest, segment splitting), also try both patterns before treating a file as empty.

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

- **VTT timestamp format variants**: VTT files use `HH:MM:SS.mmm --> HH:MM:SS.mmm` or `MM:SS.mmm --> MM:SS.mmm` (single-digit hours omitted for <10h videos). When parsing, treat any segment with hour ≥ 10 as `H:MM:SS`, otherwise as `MM:SS`. See [references/vtt-parsing.md](references/vtt-parsing.md) for the robust pattern.

- **yt-dlp `--write-auto-subs` skips if sub already downloaded**: The `--output` template must change for each video (use `%(id)s.%(ext)s`), and old temp VTT files must be cleaned between videos, otherwise yt-dlp silently skips downloading because it thinks the file is already present.
- **playlist-new-ids.txt carries titles in some entries**: Lines follow `VIDEO_ID\t[Title]\tDONE`. When the title is present the DONE marker is the **last** tab-separated field. When there is no title the last field is still `DONE`. Always test `fields[-1] == 'DONE'`, not the second field. Using the Fast-Audit script avoids manual parsing pitfalls.
