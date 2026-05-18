### Batch scripts (VTT or chapter-fallback, use when Python API is blocked)

These are shell/Python scripts that use `yt-dlp` and `urllib` directly to bypass Python SSL issues. They are stored at `/opt/data/content/` (not alongside the skill) — resolve with `find /opt/data/content -name "_fetch_transcripts_batch.py"`.

| Script | Purpose |
|--------|---------|
| `scripts/_fetch_transcripts_batch.py` | yt-dlp metadata → VTT → urllib → parse WebVTT → 3-file write |
| `scripts/yt_batch_10.sh` | bash wrapper: yt-dlp metadata → VTT try → chapter fallback → 3-file write |

> Before using, check script is at known locations: `/opt/data/content/scripts/ `/opt/data/skills/media/youtube-content/scripts/ `/opt/data/hermes-agent/skills/media/youtube-content/scripts/ `. See `references/cloud-ip-blocking.md` for full failure taxonomy and path selection guide.
