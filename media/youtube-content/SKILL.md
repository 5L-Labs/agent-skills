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

## Helper Script

`SKILL_DIR` is the directory containing this SKILL.md file. The script accepts any standard YouTube URL format, short links (youtu.be), shorts, embeds, live links, or a raw 11-character video ID.

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

## Output Formats

After fetching the transcript, format it based on what the user asks for:

- **Chapters**: Group by topic shifts, output timestamped chapter list
- **Summary**: Concise 5-10 sentence overview of the entire video
- **Chapter summaries**: Chapters with a short paragraph summary for each
- **Thread**: Twitter/X thread format — numbered posts, each under 280 chars
- **Blog post**: Full article with title, sections, and key takeaways
- **Quotes**: Notable quotes with timestamps

### Example — Chapters Output

```
00:00 Introduction — host opens with the problem statement
03:45 Background — prior work and why existing solutions fall short
12:20 Core method — walkthrough of the proposed approach
24:10 Results — benchmark comparisons and key takeaways
31:55 Q&A — audience questions on scalability and next steps
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

Example structure:

```
[Video Title] transcript (what matters):
    •    Core concept = definition. Short explanation.
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

## Workflow

1. **Fetch** the transcript using the helper script with `--text-only --timestamps`.
2. **Validate**: confirm the output is non-empty and in the expected language. If empty, retry without `--language` to get any available transcript. If still empty, tell the user the video likely has transcripts disabled.
3. **Chunk if needed**: if the transcript exceeds ~50K characters, split into overlapping chunks (~40K with 2K overlap) and summarize each chunk before merging.
4. **Transform** into the requested output format. If the user did not specify a format, default to Luna digest style.
5. **Verify**: re-read the transformed output to check for coherence, correct timestamps, and completeness before presenting.

## Pitfalls

- **System python3 missing youtube-transcript-api**: On this server, system `python3` has no pip and `uv pip install` doesn't install to it. The module is pre-installed in `/opt/hermes/.venv/bin/python`. Always run the script with that interpreter:
  ```bash
  /opt/hermes/.venv/bin/python SKILL_DIR/scripts/fetch_transcript.py "URL" --text-only --timestamps
  ```
  Do NOT use bare `python3` — it will fail with "youtube-transcript-api not installed."

- **Cloud IP blocking**: YouTube blocks transcript requests from cloud provider IPs (AWS, GCP, Azure). The script returns a JSON error: `{"error": "Could not retrieve a transcript..."}`. Workarounds:
  - Use a residential proxy or VPN
  - Use cookies from a logged-in YouTube session (`--cookies` flag if supported)
  - Pre-fetch transcripts from a non-cloud machine and store them locally

- **Script output is JSON, not formatted text**: The default output (no flags) and `--timestamps` flag both return a JSON object with these fields:
  ```json
  {
    "video_id": "...",
    "segment_count": 2918,
    "duration": "1:16:15",
    "full_text": "plain text transcript...",
    "timestamped_text": "0:00 first line\n0:02 second line\n..."
  }
  ```
  The `timestamped_text` field uses `M:SS text` format (no brackets). To get `[MM:SS] text` format, parse and reformat.

  **3-part timestamps on long videos**: For videos over ~60 minutes, timestamps switch from `M:SS` (2-part, e.g., `59:42`) to `H:MM:SS` (3-part, e.g., `1:00:04`). A naive regex like `^(\d+):(\d{2})` will NOT match 3-part timestamps — the line is silently skipped, producing a partially-formatted transcript. Always check 3-part FIRST before 2-part:
  ```python
  def format_timestamp(line):
      m = re.match(r'^(\d+):(\d{2}):(\d{2})\s+(.*)', line)
      if m:
          total_mins = int(m.group(1)) * 60 + int(m.group(2))
          return f"[{total_mins:02d}:{m.group(3)}] {m.group(4)}"
      m = re.match(r'^(\d+):(\d{2})\s+(.*)', line)
      if m:
          return f"[{int(m.group(1)):02d}:{m.group(2)}] {m.group(3)}"
      return line
  ```

  The `--text-only` flag returns just the plain text string.

## Error Handling

- **Transcript disabled**: tell the user; suggest they check if subtitles are available on the video page.
- **Private/unavailable video**: relay the error and ask the user to verify the URL.
- **No matching language**: retry without `--language` to fetch any available transcript, then note the actual language to the user.
- **Dependency missing**: run `pip install youtube-transcript-api` and retry.
