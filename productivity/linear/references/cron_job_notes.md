# Cron Job & Autonomous Run Notes — Linear & GitHub

_Captured from dry-run of daily work-queue reminder cron job (May 2026)._

## What failed and why

| Step | Expected | Actual | Root cause |
|------|----------|--------|------------|
| `echo "LINEAR set"` | reports `yes` | `no` at runtime | Env var empty at execution despite being advertised; skills view "setup_needed" is a proactive check, not a runtime guarantee |
| `echo "GITHUB set"` | reports `yes` | `no` at runtime | Same — stale/empty env at runtime |
| `gh issue list` | lists issues | `command not found` | `gh` CLI not installed on this host |
| GitHub REST token auth | `200 OK` | `401 Bad credentials` | Token present in env but invalid/expired |
| `curl ... \| python3 -c` | runs one-liner | blocked by security scanner | Terminal tool's `curl | interpreter` pattern is flagged HIGH |
| `curl ... linear.app ...` | runs OK | blocked as "lookalike TLD" | `.app` TLD triggers MEDIUM scanner for file-extension confusion |
| `execute_code` + `os.environ` | reads `LINEAR_API_KEY` | empty | Sandbox `execute_code` does not inherit the tool's env table |

## Working pattern for cron / autonomous jobs

1. **Start with `scripts/check_auth.sh`** — fails fast if either token is bad.
2. **Use `write_file` to create scripts**, then `terminal` to run them.
3. **Save API responses to temp files** (`curl -o /tmp/resp.json`), then parse in a second step.
4. **Never pipe curl into python3 inline** — saves to file first.
5. **Quote/JSON-encode everything** going into GraphQL POST bodies with `json.dumps` in Python, not string interpolation in shell.
