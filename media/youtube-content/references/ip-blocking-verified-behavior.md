# Verified IP-Blocking & yt-dlp Behavior on This Machine

## confirmed_environment: 2025-05-15-T23Z / reinforced 2026-05-16

### What works from terminal()
- `curl -s https://www.youtube.com/watch?v=...` → HTTP 200
- `ALL_PROXY="" yt-dlp --dump-single-json "https://youtube.com/watch?v=ID"` → valid JSON
- `ALL_PROXY="" yt-dlp --dump-single-json --quiet …` → valid JSON, no truncation
- `all_proxy=""` **is** sufficient for `--dump-single-json` and `--dump-single-json` metadata retrieval — the hermes-proxy does not intercept these

### What is definitely blocked
- `youtube.com/api/timedtext` signed URLs → Google "Sorry" CAPTCHA block page
- `yt-dlp --write-auto-subs / --write-subs` → HTTP 429 on timedtext (same terminal session)
- `ALL_PROXY=""` does _not_ unblock api/timedtext — the block is at the IP level, not proxy level; `client: android_vr` impersonation does not help either
- `execute_code` Python `urllib` and `subprocess.run()` → null/empty from yt-dlp, `SSLError` from urllib

### Important nuance: EN auto-caps in metadata ≠ currently fetchable captions

> **Verified 2026-05-16 on 8/10 videos**: All 8 transcript-API-blocked videos showed `automatic_captions['en']` with **14 segments** in the `yt-dlp --dump-single-json` metadata. The signed timedtext URLs all resolved to the Google "Sorry" CAPTCHA block page via both `curl` and Python. **An EN auto-caption entry in `automatic_captions[]` only proves captions were generated at some point — it does NOT mean you can currently reach the timedtext endpoint.** Do not try alternative language names (`en-US`, `en-orig`) as a workaround when IP-blocked — every language tag is signed by the same mechanism and hits the same block.

Counterexample from 2026-05-15 session: some videos DID have working English captions that could be fetched from that session's network path, so this nuance is environment-dependent, not universally blocked.

### What works as fallback
1. **Chapter outline** — `yt-dlp --dump-single-json` returns `chapters[]` array with start_time + title → write `note="chapter_outline_ip_blocked"` → mark DONE ✓
2. **Pre-fetch from non-cloud network** — store both dirs, batch processor reads from cache ✓

### What does NOT work as fallback
- Cookie injection via `--cookies-from-browser` — timedtext still returns 429
- Stale signed VTT URLs from a JSON dump written to a file — expire in minutes; `curl` hits CAPTCHA block
- `--write-subs` → `requested_subtitles` present in JSON ≠ VTT file on disk; always glob for actual `.vtt`/`.srt` after the call

### network_namespace_durable_rule

```bash
# terminal()  ← use this for ALL YouTube network operations
terminal('ALL_PROXY="" curl …')
terminal('ALL_PROXY="" yt-dlp …')

# execute_code  ← generally blocked for YouTube
execute_code('import urllib; …')     # UNEXPECTED_EOF / SSLError
execute_code('subprocess.run(…)')    # null/empty output (exit=1)
# Any subprocess.run() called from execute_code code shares execute_code's
# blocked network namespace — not safe for YouTube access.
```

### _fetch_latent_videos.py  (scripts/_fetch_latent_videos.py)
Batch helper written 2026-05-15. Run only from `terminal()`, not `execute_code`:
```bash
# Override video list via env or edit VIDEO_IDS in the script
VIDEOS="7UGjf080qag IYrO9h4KYZc …" terminal('/tmp/yt-venv/bin/python _fetch_latent_videos.py')
# or:
VIDEO_IDS='["7UGjf080qag"]' python3 _fetch_latent_videos.py
```
Path A: VTT (--write-auto-subs, same session), Path B: chapters (chapter_outline_ip_blocked note).

### 2026-05-16 session specifics

| Metric | Value |
|---|---|
| Videos processed | 10 |
| Succeeded (chapter fallback) | 2 (tIVKgztDaYQ: 15 chapters, ddd4xjuJTyg: 17 chapters) |
| Failed (no chapters, timedtext blocked, EN autocaps present but unfetchable) | 8 |
| execute_code subprocess null rate | 10/10 (0% success) |
| terminal() null rate | 0/10 (100% metadata retrieval via yt-dlp) |

All 8 failed videos had `EN=14 segments` in the metadata but `chapters=0` and timedtext all returned Google "Sorry". All 8 were marked as transient (not added to `failed_videos` in yt-backlog.json). Latent backlog left unmarked for automatic retry.
