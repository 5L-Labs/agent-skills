# execute_code Subprocess Behavior Notes

## Observed Failure Mode (confirmed 2026-05-15 and 2026-05-16)

`execute_code`'s embedded `subprocess.run()` can return **exit code 1 with empty stdout** (silently — no stderr output either) for commands that normally succeed when run via `terminal()`. The captured stdout is a null-like empty string, which `json.loads()` parses into Python `None`, producing `AttributeError: 'NoneType' object has no attribute 'get'` in downstream code.

**.run(capture_output=True) is unreliable for any network call from `execute_code`.**

## Reproduction

```python
# This works in terminal(), returning populated JSON:
# /tmp/yt-venv/bin/yt-dlp --dump-single-json --no-playlist -q "URL" > /tmp/meta.json

# This in execute_code returns exit=1, stdout='' consistently:
import subprocess, json
proc = subprocess.run(
    ['/tmp/yt-venv/bin/yt-dlp', '--dump-single-json', '--no-playlist', '-q', url],
    capture_output=True, text=True, timeout=30
)
print(f"exit={proc.returncode}, stderr={proc.stderr[:100]}")  # exit=1, no useful error
data = json.loads(proc.stdout) or {}   # stdout is '' → json.loads returns None
data.get('chapters', [])               # → AttributeError
```

## Workaround

When an `execute_code`-based subprocess returns `exit=1` with empty stdout:

1. **Switch to `terminal()` with shell-quoted commands**. This is the fastest recovery path for a single URL. Use `terminal()` for the network call and then read the temp file in a follow-up step.
2. **Dump via `terminal()` with `> file` redirect in the same call**:
   ```bash
   /tmp/yt-venv/bin/yt-dlp --dump-single-json --no-playlist -q "URL" > /tmp/meta.json
   ```
   Then use `skill_view` or the file-reading tool to inspect `/tmp/meta.json`.
3. **Batch pattern: write script to `/tmp/`, invoke from `terminal()`**:
   ```
   # Step 1: write_script via Hermes
   # Step 2: /tmp/yt-venv/bin/python /tmp/batch_fetch.py
   ```
   Inside the script, `subprocess.run(shell=True)` is fine because it inherits the `terminal()` shell's working network namespace.
4. **Do NOT add a hard refusal based on an `execute_code` failure alone** — test with `terminal()` first.

## Why This Happens

The embedded `execute_code` interpreter-subprocess has a different network/proxy namespace than `terminal()`'s interactive shell session. This environment separation can affect:

- DNS resolution (sometimes returning `None` instead of a reachable address)
- SSL handshake (partial failures vs. full certificate-warning)
- Shell environment variables (PATH, proxy, NO_PROXY differ)
- Direct access to the hermes-proxy bypass path that `terminal()` uses

This is complementary to the already-documented SSLError/curl-exit-35 mismatch. It is NOT limited to curl — **any Python `subprocess.run()` call in `execute_code` targeting an external network resource can exhibit empty or null returns**.

## Implications for Batch Scripts

Bad pattern (will silently blow up):
```python
# ❌ Do NOT do this in execute_code:
for vid in video_ids:
    r = subprocess.run([yt_dlp, url, ...], capture_output=True, text=True)
    d = json.loads(r.stdout)   # r.stdout='' → crashes
```

Good pattern:
```bash
# ✅ Write-to-tmp, then terminal():
for vid in "${VIDS[@]}"; do
  ALL_PROXY="" /tmp/yt-venv/bin/yt-dlp --dump-single-json -q "$url" > "/tmp/$vid.json"
done
# process all files in a second step
```

## Confirmatory Pattern (quick diagnosis)

```bash
# In terminal() — if this works, the tool itself is fine:
ALL_PROXY="" /tmp/yt-venv/bin/yt-dlp --dump-single-json -q "URL" > /tmp/test.json
# then read /tmp/test.json

# In execute_code — if this returns null, the subprocess namespace is the bottleneck:
import subprocess, json
proc = subprocess.run(['ALL_PROXY=""', '/tmp/yt-venv/bin/yt-dlp', ...], capture_output=True, text=True)
```

---

*Added 2026-05-15; strengthened 2026-05-16: confirmed same pattern on both runs — `execute_code` returned `exit=1, null stdout` for all 10 URLs in a batch, while `terminal()` succeeded for the same commands. Conclusion: do NOT diagnose machine-wide network failure from `execute_code` subprocess failures alone.*
