---
name: youtube-content/in-repo-scripts
description: >
  Reference: in-repo batch scripts stability and URL patterns for Youtube
  Content skill batch workflows.
---

# In-Repo Batch Scripts — Verified Usage

> Maintained invariant: these scripts must produce results *end-to-end* —
> a script that silently fails on every video is worse than writing the
> loop inline.

## `batch_fetch.py` (`/opt/data/content/batch_fetch.py`)

| Aspect | Detail |
|---|---|
| Input | `failed_videos` list from `yt-backlog.json` |
| Output | `_transcript.txt`, `_fulltext.txt`, `_meta.json`, updates `unique_videos` |
| Subprocess call | `fetch_transcript.py url` — **no flags** → JSON output |
| Parse guard | `returncode == 0` + `json.loads(stdout)` + `if "error" in data` |
| Status | ✅ Works end-to-end (validated 2026-05-16) |

## `batch_fetch_retry.py` (`/opt/data/content/batch_fetch_retry.py`) — **BROKEN**

| Aspect | Detail |
|---|---|
| Input | `_failed.txt` entries (videos with no `_transcript.txt`) |
| Bug | Calls `fetch_transcript.py url --timestamps` then `json.loads(stdout)` |
| Root cause | `--timestamps` returns plaintext lines, not JSON; always fails |
| Fix needed | Drop `--timestamps` (JSON → JSON), or parse plaintext manually |
| Status | ❌ Do NOT use without patching; always 100 % silent-failure |

## `batch_fetch_candidates.py` (`/opt/data/content/batch_fetch_candidates.py`) — **BROKEN**

| Aspect | Detail |
|---|---|
| Input | Hard-coded 4 IDs (TZGVB6L_2Eo, yYZBd25rl4Q, -gE1cesJF9M, -uiF1txQxV8), latent-backlog DONE-stripping candidates |
| Bug | Calls `fetch_transcript.py url --text-only --timestamps` then `json.loads(stdout)` |
| Root cause | `--text-only --timestamps` returns plaintext, not JSON; always fails |
| Fix needed | Drop `--text-only --timestamps` (use no flags → JSON), or parse plaintext manually |
| Status | ❌ Do NOT use without patching; silently fails on every video |

> **SRM pattern**: Both `batch_fetch_retry.py` + `batch_fetch_candidates.py` share the same root cause
> — wrong flag combination for the subprocess. Study `batch_fetch.py` for the
> correct no-flag call pattern before writing any new fetch wrapper.

## `fetch_json()` canonical pattern (from `batch_fetch.py` — correct)

```python
result = subprocess.run(
    [PYTHON, SCRIPT, url], capture_output=True, text=True, timeout=120
)
if result.returncode != 0:
    return None
try:
    data = json.loads(result.stdout.strip())
    if isinstance(data, dict) and "error" in data:
        return None
except json.JSONDecodeError:
    return None
return data
```

**Reuse this exactly** when writing any new fetch wrapper.
