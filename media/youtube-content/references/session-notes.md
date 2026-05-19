# YouTube Content — Re-useable Workflow Notes

> Session-specific notes from runs where live fetch is blocked or retried.  
> All paths below refer to the **active config dir**: `/opt/data/.hermes/`

## In-repo batch scripts pitfall (discovered 2026-05-18)

`batch_fetch_retry.py` (in `/opt/data/content/`) calls `fetch_transcript.py URL --timestamps` and then parses stdout with `json.loads()`. The `--timestamps` flag returns **plain-text**, not JSON, so `json.loads()` always raises `JSONDecodeError` and no video can succeed through this script as-is. Before reusing it, fix the call:

- **Preferred fix**: drop `--timestamps` from the `subprocess.run()` args in `batch_fetch_retry.py` so `fetch_transcript.py` returns JSON (the script's own parser expects JSON).
- **Alternative fix**: keep `--timestamps`, remove `json.loads()`, and parse each line as `"[M:SS] text"` manually.

Meanwhile, `batch_fetch.py` at the same path handles this correctly — it calls `fetch_transcript.py` with no flags (JSON output) and uses `fetch_json()` (return-code check + JSON guard) before saving.

## Known environment paths

When `youtube-transcript-api` connects from a cloud provider IP it fails at the HTTPS level:
```
SSLError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1029)
```

The error is emitted as a JSON error string on stdout with exit code 1. Watch for both:
- `result.returncode != 0` AND
- `json.loads(stdout)` → `{"error": "..."}`

**Do NOT treat a 1103-char `<html><title>Sorry...</title>` response as valid XML** — this is the Google IP-block page.

## In-repo batch scripts (pre-validated patterns)

| Script | Purpose |
|---|---|
| `/opt/data/repos/batch_fetch.py` | Retry from `failed_videos` in `yt-backlog.json`; uses `fetch_json()` with proper returncode+JSON guard |
| `/opt/data/repos/batch_fetch_retry.py` | Retry any `_failed.txt` entry; skip videos with an existing `_transcript.txt` |

Reusing these scripts avoids re-implementing: per-video manifest I/O, duration, language fallback, and state bookkeeping. Study the `fetch_json()` and `save_video()` functions before writing fresh code.

## Local-cache check pattern (stub detection)

Always check `_fulltext.txt` size and content before treating it as a cache hit:

```python
ft_size = os.path.getsize(ft_path)
with open(ft_path) as f:
    raw = f.read().strip()
is_stub = (ft_size < 500
           or raw.startswith("Video:")
           or "unavailable" in raw.lower()
           or "yt-dlp returned" in raw.lower())
```

A stub should **not** be treated as a real fulltext — leave `segments` as 0 in meta.json if no verbatim was recovered.

## Zero-segment fulltext: reorganization of the YouTube transcript pipeline

When `fetch_transcript.py` returns `segments: []` but `full_text` is real content (≥ 8 KB):
- Save the `full_text` to `_fulltext.txt` (cleaned)
- Save an empty `_transcript.txt`
- Record `"segments": 0, "note": "segments_missing_fulltext_only"` in `_meta.json`
- The fulltext alone is sufficient to confirm content was harvested
- Re-segment in post using `split_into_timed_paragraphs(fulltext, duration)` when real timestamps are needed

> The 25 KB lower bound in the original skill was calibrated from a prior environment. The realistic real-content floor is **8 KB** — anything shorter is almost always a chapter-outline stub (22–940 byte chapter headings with no spoken-word body, returned when the cloud-IP block prevents timedtext delivery but the oEmbed/API still returns chapter metadata). See **SRM pattern** below.

## Subtle Return-code / Format Mismatch (SRM) — in-repo batch scripts

There are two flavors of SRM in this workspace:

| Script | Call pattern | Expected format | What it actually receives | Bug? |
|---|---|---|---|---|
| `batch_fetch.py` | `fetch_transcript.py url` (no flags) | JSON (`json.loads(stdout)`) | JSON ✓ | No |
| `batch_fetch_retry.py` | `fetch_transcript.py url --timestamps` | JSON (`json.loads(stdout)`) | **plain‑text** | **Yes — always fails silently** |

Fix for `batch_fetch_retry.py`: drop `--timestamps` from the `subprocess.run()` args so `fetch_transcript.py` returns JSON (which is what its own `json.loads(stdout)` expects).

> A definitive script-gotcha catalogue (SRM table + fix) is maintained in `references/in-repo-scripts.md` in this skill. Consult it before writing any new fetch wrapper.

## oEmbed as a cheap metadata source

`https://www.youtube.com/oembed?url=<WATCH_URL>&format=json` works even when the timedtext API is blocked. It returns title and author in JSON. Use it to backfill `meta.json` title fields.

## `fetch_transcript.py` flag combinations

| Flags | Output |
|---|---|
| (none) | JSON with `full_text` + metadata |
| `--timestamps` | JSON with `full_text` + `timestamped_text` (each line: `M:SS text`) |
| `--text-only` | plain text string (no JSON, no timestamps) |
| `--text-only --timestamps` | **timestamped plain text** (one line per segment: `M:SS text`), no JSON wrapping |

Workflow step `--text-only --timestamps` gets raw timestamped lines suitable for LLM processing. Do NOT expect JSON when combining both flags.

## Approved script interpreter

Use `/opt/hermes/.venv/bin/python3` (not bare `python3`).
