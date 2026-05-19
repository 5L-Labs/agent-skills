# YouTube Content Skill — Known Environment Paths

> Verify these before assuming a failure is an actual content/YouTube problem.

## Verified paths (2026-05-18 run)

| Purpose | Correct path | Wrong path (causes "Permission denied") |
|---|---|---|
| Fetch/processing scripts | `/opt/data/.hermes/skills/media/youtube-content/scripts/` | `/opt/data/hermes-agent/skills/...` (missing leading dot) |
| Hermes venv Python | `/opt/hermes/.venv/bin/python3` | (works; do not blanket-reject) |
| Temp venv (dep fallback) | `/tmp/yt-venv/bin/python3` | — |
| Raw transcript cache | `/opt/data/content/youtube-raw/` | `/opt/data/home/.hermes/content/youtube-raw/` (wrong) |
| Backlog JSON | `/opt/data/content/yt-backlog.json` | `/opt/data/.hermes/content/yt-backlog.json` (wrong) |
| Playlist file | `/opt/data/.hermes/content/playlist-new-ids.txt` | `/opt/data/content/playlist-new-ids.txt` (empty stale copy; `/opt/data/.hermes/content/` is the active dir) |
| Latent-space backlog (pending queue) | `/opt/data/.hermes/content/yt-latent-space-backlog.txt` | — |

## Error diagnosis cheat-sheet

- `Permission denied: '/opt/data/hermes-agent/...'` (missing leading dot before `hermes`) → **Wrong path**, not a real permission failure. Skill's config dir is `/opt/data/.hermes/` (note the dot). Fix the path, don't adjust permissions.
- `Permission denied` on a path that **does** begin with `/opt/data/.hermes/` or another correctly resolved directory → actual filesystem permission issue (e.g. cron context can't write). Use a temp-dir workaround or escalate.
- `Max retries exceeded / SSL UNEXPECTED_EOF` → Cloud IP block. Retrying from the same host won't help.
  Use local cache if available, or retry from a non-cloud IP.
- JSON response with `"error": "Could not retrieve a transcript..."` → API natively blocked; check cache first.

## Transcript file naming convention

Files saved as `<VIDEO_ID>_transcript.txt`, `<VIDEO_ID>_fulltext.txt`, `<VIDEO_ID>_meta.json`.
Check for existence with `os.path.exists(os.path.join(RAW_DIR, f"{vid}_transcript.txt"))`.

## Latent-space backlog (`yt-latent-space-backlog.txt`) — the pending queue

- **Path**: `/opt/data/.hermes/content/yt-latent-space-backlog.txt`
- **Format**: one entry per line: `<VIDEO_ID>\t<TITLE>\t[DONE]` or `<VIDEO_ID> DONE`
- **Purpose**: tracks which videos are finished (suffixed DONE) vs still pending (no suffix)
- **All entries without DONE** are the actual batch queue; `playlist-new-ids.txt` is often empty while latent-backlog still has work
- **Three-source health check**:
  | File | Role |
  |---|---|
  | `/opt/data/.hermes/content/playlist-new-ids.txt` | freshly imported videos (often empty) |
  | `/opt/data/.hermes/content/yt-latent-space-backlog.txt` | authoritative pending queue |
  | `/opt/data/content/yt-backlog.json` | authoritative completed/failed record |
- **Don't halt early**: after checking playlist-new-ids.txt is empty, always also scan latent-backlog — skipping it produces false 'nothing to do' reports when work remains.
