---
name: youtube-batch-processor
title: YouTube Batch Processor
description: Process multiple YouTube videos from a backlog with automatic transcript fetching, Luna digest generation, and backlog management
domain: media processing
created: 2026-04-25
updated: 2026-04-25
---

# YouTube Batch Processor Skill

**Domain**: Media processing, transcript extraction, content summarization  
**Purpose**: Process multiple YouTube videos from a backlog with automatic transcript fetching, Luna digest generation, and backlog management

## Workflow Overview

### 1. Backlog Reading
Read video IDs from both `.txt` and `.json` backlog files:
- Text file: `/opt/data/.hermes/content/yt-latent-space-backlog.txt` (format: pipe-delimited, e.g. `index|video_id|group`)
- JSON file: `/opt/data/.hermes/content/yt-backlog.json` (field: `unique_videos[]`)

### 2. Transcript Fetching (per video, with Error Handling)
For each video ID, attempt transcript fetch (saving raw files for future re-formatting):

**⚠️ venv requirement**: The standard Hermes venv at `/opt/hermes/.venv` typically lacks `youtube-transcript-api`. The fetch script will return `{"error": "youtube-transcript-api not installed..."}`. **Workaround**: Create a temporary venv and use it:
```bash
uv venv /tmp/yt-venv && uv pip install --python /tmp/yt-venv/bin/python youtube-transcript-api
```
Use `/tmp/yt-venv/bin/python` for ALL fetch operations (not bare `python3` or `/opt/hermes/.venv/bin/python3`).
```bash
/opt/hermes/.venv/bin/python /opt/data/skills/media/youtube-content/scripts/fetch_transcript.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --text-only --timestamps \
  --save-dir /opt/data/.hermes/content/yt-raw-transcripts
```
This saves: `{video_id}.json` (full transcript data with segments) and `{video_id}_timestamped.txt`.

The raw JSON files allow re-formatting without re-fetching from YouTube (useful if you need to change digest style or retry processing).

**Failure Modes & Handling**:
- **Cloud IP blocking**: JSON error "Could not retrieve transcript" → YouTube blocks cloud IPs. **Always check the local cache at `/opt/data/home/.hermes/content/youtube-raw/VIDEO_ID.txt`** before falling back to proxies or skipping. If the file exists, use its contents directly.
- **Transcripts disabled**: JSON error `{"error": "Transcripts are disabled..."}` → Skip video, **keep in backlog** (creator may enable later)
- **No transcript / language mismatch**: JSON error `{"error": "No transcript found. Try specifying a language..."}` → Skip, keep in backlog
- **Video unavailable**: JSON error about availability/copyright → Skip, keep in backlog
- **Language codes unreliable**: The `--language en` flag often doesn't work. Always try **without** language flag first.

**Critical rule**: On **any** transcript fetch failure, the video ID stays in backlog for potential retry later.

### 3. Luna Digest Generation (On Success Only)
After fetching a valid timestamped transcript, generate a Luna-style digest.

**Method A (Broken — Do Not Use)**: Confirmed failed in practice (2026-04-28 cron run). The `generate_luna_digest.py` script produces the same sparse output for every transcript: `[Unknown Video]` as title, a long undifferentiated bullet of concatenated raw text, and `Big insight: See above sections for key points and takeaways.` — no thematic grouping, no real Luna structure. Always proceed directly to Method B or C.

**Method B (Fallback — Recommended)**: Use a Python fallback that strips timestamps, extracts meaningful sentences, and formats them as Luna-style bullets. This produces significantly richer digests than the script. See the Python code pattern in the "Fallback Digest Approach" section below.

**Method C (Manual Curation - Recommended for polished output)**: Create digest with:
- First line: `[URL]` or `URL` (the video link)
- Second line: blank
- Third line: `Video Title (speaker, source, length) transcript (what matters):`
- Sections with **bold headers** (no markdown `#`, just `**` not supported - use plain text bold intent)
- Main bullet `•` for key ideas (1-2 lines max)
- Sub-bullet `◦` for details/examples
- **Bold key terms** on first mention (using `**term**` or just all-caps emphasis)
- No emoji, no markdown headers
- End with a "Big Insight" section and caveats

**Example digest structure:**
```
https://www.youtube.com/watch?v=VIDEO_ID

Topic Title (speaker, duration) transcript (what matters):
    •    Core Concept = definition:
    ◦    Detail or example 1.
    ◦    Detail or example 2.
    •    Second concept:
    ◦    Explanation with specifics.
    •    Practical relevance:
    ◦    Use case A.
    ◦    Use case B.
    •    Big Insight: main takeaway in one line.
         
    •    Caveats: limitations or open questions.
    ◦    Limitation detail.
```

### 4. Digest Storage
Save to: `/opt/data/.hermes/content/youtube-raw/VIDEO_ID.txt`

### 5. Backlog Cleanup (ONLY After Success)
Remove the **successfully processed** video ID from BOTH files:
- Text file: Remove the entire line containing the video ID (`sed -i '/VIDEO_ID/d'`)
- JSON file: Filter `unique_videos` array to exclude the ID (`jq '.unique_videos -= ["VIDEO_ID"]'`)

**Critical rule**: Only remove IDs after successful transcript fetch **and** digest save. Never remove on failure.

### 6. Verification Checklist
After processing each video, verify:
- [ ] Transcript is valid text (not JSON error)
- [ ] Digest file exists at correct path
- [ ] Video ID removed from `yt-latent-space-backlog.txt`
- [ ] Video ID removed from `yt-backlog.json`
- [ ] Remaining video count decreased by exactly 1

## Example Cron Job Setup

```bash
# Process 2 videos daily at 9 AM
0 9 * * * /opt/hermes/.venv/python /path/to/process_backlog.py --limit 2
```

## Manual Digest Curation (Recommended)

The `generate_luna_digest.py` script provides a basic template, but **manual curation produces significantly better results**. Here's the recommended approach:

### Step 1: Fetch transcript and save raw data
```bash
cd /opt/hermes
/opt/hermes/.venv/bin/python /opt/data/skills/media/youtube-content/scripts/fetch_transcript.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --text-only --timestamps \
  --save-dir /opt/data/.hermes/content/yt-raw-transcripts
```

### Step 2: Review raw transcript
```bash
cat /opt/data/.hermes/content/yt-raw-transcripts/VIDEO_ID_timestamped.txt
```

### Step 3: Create manually curated digest

**File location**: `/opt/data/.hermes/content/youtube-raw/VIDEO_ID.txt`

**Format**:
```
https://www.youtube.com/watch?v=VIDEO_ID

Video Title (speaker, source, length) transcript (what matters):
    •    Introduction
    ◦    Key opening statement 1.
    ◦    Key opening statement 2.

    •    **Core Concept**
    ◦    Clear explanation of main idea.
    ◦    How it works in practice.

    •    **Key Requirements or Prerequisites**
    ◦    What's needed to implement.
    ◦    Important constraints.

    •    **Practical Application**
    ◦    Real-world use case.
    ◦    Implementation pattern.

    •    **Key Takeaway**
    ◦    Main insight in one line.
```

**Real-world example** (from Portworx/Kubernetes StatefulSets video):
```
https://www.youtube.com/watch?v=S9j3aJ5lQw0

Portworx Volume Placement Strategies for Kubernetes StatefulSets transcript (what matters):
    Speaker: Ryan Wallner, Technical Advocate, Portworx
    Source: YouTube, Length: ~6 minutes

    •    Introduction
    ◦    Hello and welcome to another Portworx lightboard session.
    ◦    Today we're going to take you through volume placement strategies.

    •    **Core Concept: Volume Placement Strategies**
    ◦    Volume placement strategies allow flexible configuration of where volumes land in Kubernetes.
    ◦    Multiple volumes for a pod/statefulset can land on specific nodes or near pods.
    ◦    Strategies use labels to determine volume placement relative to workloads.

    •    **Use Case: StatefulSets with Cassandra**
    ◦    Stateful sets allow ordering of stateful services in scheduling and deployment.
    ◦    Cassandra uses a seed node pattern where subsequent nodes reference the first node.
    ◦    A Cassandra application typically has two volumes: data and configuration.

    •    **Implementation Requirements**
    ◦    Labels on PVCs: type=data for data volumes, type=config for config volumes.
    ◦    Enables targeted placement using label selectors in volume placement strategies.

    •    **Affinity & Anti-Affinity Rules**
    ◦    Volume anti-affinity does the opposite of affinity rules.
    ◦    Example: data volume should land next to config volumes but not next to other data volumes.
    ◦    Prevents multiple data volumes on the same node for failure resistance.
    ◦    Configuration volumes also use anti-affinity to avoid colocating on same nodes.

    •    **Practical Deployment Pattern**
    ◦    Each Cassandra node gets dedicated data and config volumes.
    ◦    Volumes colocate with pods on same Kubernetes node.
    ◦    Config volumes land near data volumes, not next to other config volumes.
    ◦    Rules can be tied to storage classes for automated enforcement.

    •    **Key Takeaway**
    ◦    Portworx volume placement strategies provide fine-grained control over where persistent volumes land in relation to pods and other volumes.
```

**Key formatting rules**:
- Use `**bold**` for section headers (not markdown `#`)
- Main bullet `•` for section titles and key concepts
- Sub-bullet `◦` for details and examples
- **Bold** key terms on first mention
- Max 1-2 lines per bullet
- No markdown headers, no emoji

## Pitfalls & Lessons Learned

| Issue | What Happened | Fix |
|-------|--------------|-----|
| **`--language en` errors** | Script returned `{"error": "No transcript found. Try specifying a language..."}` even after passing `--language en` | Don't use `--language` flag; try plain fetch, then retry without any language flag |
| **`generate_luna_digest.py` failure** | Script produces sparse output ("[Unknown Video]", "Big insight: See above sections") on nearly all transcripts | This is the expected behavior — immediately fall back to the Python timestamp-stripping approach (see below). Do not spend time debugging the script. |
| **Video without transcript** | `fsLh-NYhOoU` had no transcript available | Skip gracefully; keep in backlog (may be enabled later) |
| **Backlog consistency** | Removing from only one file causes drift | Always update both `.txt` AND `.json` in same operation |
| **Long transcripts** | Script may truncate for very long videos | Consider chunking: split transcript >50K chars into overlapping chunks |
| **venv missing youtube-transcript-api** | `/opt/hermes/.venv` lacks the package; pip/uv installs fail due to permissions | Create a fresh venv with `uv venv /tmp/yt-venv && uv pip install --python /tmp/yt-venv/bin/python youtube-transcript-api`. Use `/tmp/yt-venv/bin/python` for all fetch operations. |

## Fallback Digest Approach (Method B — Use as Default in Automation)

When `generate_luna_digest.py` fails or produces sparse output, use this Python pattern:

```python
import re

def strip_timestamps(content):
    lines = content.split('\n')
    result = []
    for line in lines:
        # Remove M:SS or H:MM:SS at start of each line
        stripped = re.sub(r'^\d+:\d{2}(?::\d{2})?\s+', '', line)
        result.append(stripped)
    return '\n'.join(result)

def extract_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    meaningful = [s.strip() for s in sentences if len(s.strip()) > 25]
    return meaningful

text = strip_timestamps(open('/path/to/VIDEO_ID_timestamped.txt').read())
sents = extract_sentences(text)
# Bucket sentences by theme using keyword matching, then format as Luna bullets
```

**Key formatting rules:**
- Use `•` (U+2022) for main bullet points
- Use `◦` (U+25E6) for sub-bullets
- **Bold** key terms on first mention
- No markdown headers, no emoji
- Max 1-2 lines per bullet
- End with "Big insight:" line and optional caveats

## Expected Transcript Output Format

The fetch script with `--text-only --timestamps` produces:
```
0:00 first words of transcript
0:03 next words here
0:07 more words
...
```

This is **plain text**, not JSON. No flags = JSON. `--text-only` alone = plain text without timestamps. Both flags = plain text with timestamps (pipe-friendly).

## Quality Standards for Final Digest

- **Concise**: Each bullet max 2 lines
- **Structured**: Thematic sections with clear headers
- **Actionable**: Key insights and practical takeaways
- **Complete**: URL, context, sections, insights, caveats
- **Clean**: No markdown headers, no emoji, consistent formatting

## Automation Safety

- **Idempotency**: Running twice is safe - already-processed IDs are gone
- **Failure tolerance**: Single video failure doesn't block queue
- **Logging**: Log skipped videos with reason for later review
- **Rate limiting**: Add small delays between requests if processing many
- **Resumability**: Can stop mid-batch and resume; only successful ones removed

---

## See also

- [Data Persistence Pattern](../../devops/data-persistence-pattern) - General pattern for adding `--save-dir` to fetch scripts