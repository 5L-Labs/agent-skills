# In-Repo Batch Scripts — Verified Usage

> Maintained invariant: these scripts must produce results *end-to-end* — a script that silently fails on every video is worse than writing the loop inline.

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
| Bug | Calls `fetch_transcript.py url --timestamps` and then does `json.loads(stdout)` |
| Root cause | `--timestamps` returns **plaintext** ("`M:SS text`" lines, one per segment), not JSON. `json.loads()` always fails, so no video ever succeeds through this script. |
| Fix needed | Option A: drop `--timestamps` from `subprocess.run()` args — `fetch_transcript.py` then returns JSON ✅  <br> Option B: drop `json.loads()`, split stdout by newlines, parse each line as `"[M:SS] text"` |
| Status | ❌ Do NOT use without patching; every run is 100% silent-failure |

## `fetch_json()` pattern (from `batch_fetch.py`)

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

**Reuse this pattern exactly** when writing new fetch wrappers.
