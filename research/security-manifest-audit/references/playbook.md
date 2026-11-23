# Security Manifest Audit — playbook

## Model-failure matrix (observed 2026-11, 185-skill audit)

| Setup | Result | Lesson |
|---|---|---|
| qwen3.8-27b local, 10 tasks | context overflow / gateway interruption, 0 files | small models cannot hold a full review batch |
| qwen/qwen4-max:free, 10-way fan-out | Nous Portal 429 fair-share, 0 files | free tier still has account-level concurrency limits |
| moonshotai/kimi-k3.1-pro, 3-way | 54 skills verified, then 402 out of credits | paid model works until billing stops; checkpoints saved the work |
| tencent/hy4-flash:free, 3-way | all remaining work completed | safe default in this environment |

Raw HTTP calls to auth.json tokens failed 401; kilocode key 401 INVALID_TOKEN; openrouter 402 no credits. The gateway CLI path (`hermes chat -m ...`) worked when raw API calls did not. Always smoke-test with `hermes chat -q 'Reply OK' -Q -m <model> --max-turns 1` before a large fan-out.

## Exact commands

```bash
# Pin child model and concurrency
hermes config set delegation.model tencent/hy4-flash:free
hermes config set delegation.provider nous
hermes config set delegation.max_concurrent_children 3
hermes config set delegation.child_timeout_seconds 1800

# Deterministic baseline
/usr/bin/python3 /path/to/security-manifests/_run/generate_baseline.py
```

Validation keys: `schema`, `skill`, `path`, `commit`, `shape`, `summary`, `tools`, `resources`, `side_effects`, `delegation`, `escalations`, `provenance`. Evidence keys: `hosts_found`, `imports`, `clis`, `env_vars`, `hermes_tools`, `setup_commands`, `shape_reasoning`. Check confidence >= 0.7, zero baseline notes, artifact coverage against batch lists, and secret-like regexes. Use `/usr/bin/python3` (PyYAML installed there).

## Review briefing essentials

- Absolute paths for shared context, batch file, repo root and audited commit.
- "Baseline files already exist; verify and patch in place. Do not rewrite from scratch."
- Per-skill checkpoint: finish both files before starting the next skill.
- Resume rule: skip skills whose provenance has confidence >= 0.7 and no baseline note.
- Never print credential values; names only. No network, no installs, no skill-code execution.

## Pitfalls

- Reviewers sometimes nest `side_effects` under `resources`; final validation must check top-level presence and fix in place.
- Tool names in prose over-call shape. Fix `tools` and `tool_mediated` before trusting `shape`.
- A child may use `execute_code` despite the briefing; steer it mid-run to `patch`/`write_file`.
- Results reported by children are self-reports. Always verify on disk before declaring done.
