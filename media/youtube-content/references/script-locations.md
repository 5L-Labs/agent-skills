# Script Locations (Actual vs. Skill-Bundled)

This project has multiple copies of YouTube processing scripts across several directories. The skill documentation references `SKILL_DIR` (the directory containing SKILL.md), but in practice there is a canonical production copy at `/opt/data/`.

## Skill-Bundled Scripts (Reference Location)

These are considered the "source of truth" for the skill definition and are what `SKILL_DIR` resolves to in a clean skill deployment:

```
/opt/data/skills/media/youtube-content/scripts/fetch_transcript.py
/opt/data/skills/media/youtube-content/scripts/generate_luna_digest.py
```

Other potential skill script locations (all check for `fetch_transcript.py` in order):
- `/opt/data/.hermes/skills/media/youtube-content/scripts/`
- `/opt/data/hermes-agent/skills/media/youtube-content/scripts/`
- `/opt/data/repos/agent-skills/media/youtube-content/scripts/`
- `/opt/data/upstream-hermes-agent/skills/media/youtube-content/scripts/`

## Production Batch Scripts (Not in SKILL_DIR)

These are separate utility scripts used by the batch processing infrastructure and cron jobs. They are **NOT** inside any skill directory:

| Script | Path | Used by |
|---|---|---|
| fetch_yt_transcripts.py | `/opt/data/scripts/fetch_yt_transcripts.py` | Cron job (fetches 5 videos per run on schedule) |
| _process_youtube_batch.py | `/opt/data/content/_process_youtube_batch.py` | Manual batch runs (fetches up to 10 with full state tracking) |
| process_yt.py | `/opt/data/content/process_yt.py` | Targeted fetch for specific video set (3 videos, hardcoded) |
| process_yt_retry.py | `/opt/data/content/process_yt_retry.py` | Retry helper with exponential backoff |

### Key Distinction

When someone says "run the YouTube batch job" they almost always mean `_process_youtube_batch.py` or the cron script `fetch_yt_transcripts.py`, not `fetch_transcript.py` from the skill scripts directory. The skill's `fetch_transcript.py` is meant for single-video, on-demand fetching.

## Python Interpreter to Use

In this environment:
```bash
/opt/hermes/.venv/bin/python  # Has youtube-transcript-api installed (required for fetch_transcript.py)
/usr/bin/python3               # Does NOT have youtube-transcript-api
```

System python may be used for `urllib`-based scripts (`fetch_yt_transcripts.py`) as they do not import external packages.