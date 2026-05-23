# yt-dlp `--dump-single-json` Metadata Structure

## Key Fields for Batch Processing

```jsonc
{
  "id": "7HJCa-pHfSQ",            // video ID
  "title": "Video Title",
  "fulltitle": "Video Title - extra",
  "duration": 1693,               // seconds
  "duration_string": "28:13",
  "channel": "Channel Name",
  "uploader_id": "@handle",
  "upload_date": "20250718",
  "availability": "public",
  "chapters": [                   // built-in YouTube chapter markers
    {"start_time": 0.0, "title": "Introduction", "end_time": 46.0},
    ...
  ],
  "automatic_captions": {          // ASR captions keyed by language code
    "en": [
      {
        "ext": "vtt",              // format: json3 | srv1 | srv2 | srv3 | ttml | srt | vtt
        "url": "https://www.youtube.com/api/timedtext?...&lang=en&fmt=vtt",
        "name": "English (auto-generated)"
      }
    ],
    "cy": [ ... ],                 // Welsh fallback also auto-generated
    ...
  },
  "subtitles": {},                 // manual / user-uploaded subtitles (often empty)
  "format": "248+251 - 1080p+medium",
  "formats": [ ... ],              // all available download formats
  "webpage_url_basename": "watch",
  "_version": { "version": "2026.03.17", ... }
}
```

## Fetching Subtitles for a Video (yt-dlp pattern)

> **⚠️ execute_code → Python subprocess: SSL_CERT_FILE inheritance lock.**  
> If you call yt-dlp from a Python subprocess spawned inside `execute_code`, filter the env
> before passing it:  
> ```python
> env_no_ssl = {k: v for k, v in os.environ.items() if 'SSL' not in k.upper()}
> subprocess.run([YT_DLP, ...], env=env_no_ssl)  
> ```  
> The host `SSL_CERT_FILE` (`/usr/lib/ssl/cert.pem`, a system self-signed cert) breaks
> every Python SSL handshake in the child. Bash scripts launched via `terminal` are NOT
> affected because the terminal session inherits the same `SSL_CERT_FILE` and the shell
> environment (not Python) propagates it, so the binary uses its compiled CA chain.
> **Rule of thumb:** use `terminal → bash` for batch; if you must go via `execute_code`,
> aggressively wipe all `SSL_CERT*`, `PYTHONHTTPSVERIFY`, `REQUESTS_CA_BUNDLE`, and
> `CURL_CA_BUNDLE` from the subprocess env.

1. Call `--dump-single-json` to get metadata (including `automatic_captions.en[].url`)
2. For each video, download VTT: `--skip-download --write-auto-subs --sub-langs en --sub-format vtt --output /tmp/{id}.vtt`
3. Parse VTT with the pattern in `vtt-parsing.md`
4. **Sleep 3–5 seconds** between subtitle calls to avoid HTTP 429
5. **Use a per-video output directory** (`/tmp/subs_ytbatch/{VIDEO_ID}/`) so yt-dlp does not
   silently skip re-downloading when a file with the same name is already present in a
   shared temp directory.

## Subtitle URL Expiry

The `&ei=` parameter in timedtext URLs is a short-lived token (~5 minutes). Always
re-fetch metadata with `--dump-single-json` before a new batch of subtitle downloads,
don't reuse URLs from a previous run.

## EN captions may also appear as `a.en` or `en-orig`

Always check `automatic_captions.get('en')` first, then fall back to `a.en` or `en-orig`.

## Batches: cooling strategy

If processing more than ~10 videos:
- Spread fetches across minutes (e.g., `sleep(5)` between subtitle calls)
- Re-fetch metadata after every 10 videos (fresh `&ei=` tokens)
- If 429 received: sleep 60 seconds, then retry with fresh metadata
