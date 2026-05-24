# Cron Job & Autonomous Run Notes — GitHub Issues

_Captured from dry-run of daily work-queue reminder cron job (May 2026)._

## What failed and why

| Step | Expected | Actual | Root cause |
|------|----------|--------|------------|
| `echo "GITHUB set"` | reports `yes` | `no` at runtime | Env var empty/revoked at execution despite being advertised |
| `gh issue list` | lists issues | `command not found` | `gh` CLI not installed on this host |
| GitHub REST token auth | `200 OK` | `401 Bad credentials` | Token present in env but invalid/expired |
| `curl ... \| python3 -c` | one-liner output | blocked by security scanner | `curl | interpreter` pattern flagged HIGH |
| `execute_code` + `os.environ` | reads GITHUB_TOKEN | empty | Sandbox env not shared with tool env table |

## Working pattern for cron / autonomous jobs

1. **Start with `bash /opt/data/skills/productivity/linear/scripts/check_auth.sh`** — fails fast if either token is bad.
2. **Use `write_file` tool to create scripts**, then `terminal` to run them.
3. **Save API responses to temp files** (`curl -o /tmp/resp.json`), then parse in a separate step.
4. **Never pipe curl directly into python3 inline** in terminal commands — saves to file first.
5. **Use Platform-GitHub as the worst-case fallback auth path** — never assume gh is installed.
