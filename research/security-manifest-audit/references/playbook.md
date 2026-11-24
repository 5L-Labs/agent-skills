# Security Manifest Audit — playbook

Operational detail for Stage 1 (static census). Dispatch and model notes live in
`run-2026-11.md`.

## Exact commands

```bash
# 1. deterministic baseline. PyYAML is on /usr/bin/python3, not the venv python.
/usr/bin/python3 scripts/generate_baseline.py \
    --repo   /path/to/audited-repo \
    --out    /path/to/audited-repo/security-manifests \
    --schema references/manifest.v0.json

# 2. validate + distribution report. Exit code 0 only when every check passes.
/usr/bin/python3 scripts/validate_corpus.py \
    --corpus   /path/to/audited-repo/security-manifests \
    --repo     /path/to/audited-repo \
    --json-out /tmp/validation.json \
    --report   /path/to/audited-repo/security-manifests/_reports/distribution.md
```

`--repo` also accepts `HERMES_AUDIT_REPO`; `--out` accepts `HERMES_AUDIT_OUT`.
The commit is read with `git rev-parse HEAD` from `--repo`, never hardcoded.

## Validation keys

Manifest: `schema`, `skill`, `path`, `commit`, `shape`, `ceiling`, `summary`,
`actions`, `tools`, `binaries`, `resources`, `side_effects`, `delegation`,
`escalations`, `provenance`.

`evidence/static.json`: `files_scanned`, `skipped`, `hosts_found`, `setup_hosts`,
`doc_hosts`, `artifact_hosts`, `imports`, `clis`, `env_vars`, `credential_names`,
`hermes_tools`, `tool_reach`, `setup_commands`, `signals`, `shape_reasoning`.

## Stage-confidence gate

`static` <= 0.5, `+review` <= 0.6, `+dynamic` <= 0.75, `+eval-backtest` <= 1.0.
`validate_corpus.py` checks the declared stage against the cap, not the number.
A reviewer that raises `confidence` without changing `method` and `inputs` fails
validation. `provenance.inputs` is what makes the score recomputable.

## Review briefing essentials (stage 2)

- Absolute paths for shared context, batch file, repo root and audited commit.
- "Baseline files already exist; verify and patch in place. Do not rewrite."
- Per-skill checkpoint: finish both files before starting the next skill.
- Resume rule: skip skills whose `provenance.method` is already `+review` or later.
- Never print credential values; names only. No network, no installs, no code execution.
- Use `patch`/`write_file`, never `execute_code` — approvals block in delegated sessions.

## Pitfalls

- A colon followed by `43` is not a raw socket. Look for `whois`,
  `socket.create_connection`, `socket.socket(...)` plus `connect`, or `ftplib`.
- An inline code span is not code context. A markdown link on a line that also
  has a backticked filename elsewhere is documentation, not a runtime host.
- Files over 400 KB and `node_modules` are skipped and recorded under `skipped`.
  Read that list before declaring a skill clean.
- `import numpy as np` records `numpy`. Aliases are not module names.
- Stage-1 output is a draft. Never raise `confidence` to "fix" a shape.
