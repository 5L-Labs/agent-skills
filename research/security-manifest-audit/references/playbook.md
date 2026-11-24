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

# 3. generator regression tests (~1s, no network, fixtures built at run time)
/usr/bin/python3 scripts/test_generate_baseline.py
```

`--repo` also accepts `HERMES_AUDIT_REPO`; `--out` accepts `HERMES_AUDIT_OUT`.
The commit is read with `git rev-parse HEAD` from `--repo`, never hardcoded. The
validator also fails a manifest whose `commit` differs from the checkout.

## Validation keys

Manifest: `schema`, `skill`, `path`, `commit`, `shape`, `ceiling` (null at
`static`), `summary`, `actions`, `tools`, `binaries`, `resources`, `side_effects`,
`delegation`, `escalations`, `provenance`.

`evidence/static.json`: `files_scanned`, `skipped`, `hosts_found`, `setup_hosts`,
`doc_hosts`, `artifact_hosts`, `imports`, `clis`, `env_vars`, `credential_names`,
`hermes_tools`, `tool_vocabulary`, `tool_reach`, `setup_commands`, `signals`,
`shape_reasoning`.

## Tool vocabulary

Tool names come from the audited repo's `toolsets.py` (parsed with `ast`: list
elements are tool names, dict keys are toolset names). The built-in lists are the
fallback when that file is missing. `evidence.tool_vocabulary.source` records
which path was taken, so a corpus built without the repo's own list is visible.

Reach is our judgement, not the repo's: the built-in sets classify known names and
names discovered only from `toolsets.py` fall back to keyword hints. `terminal`
and `execute_code` reach is derived from the commands they run, and
`delegate_task` is `inherits` (ranked as medium for shape until a later stage
pins the child's toolset).

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
  Prose `whois`/`telnet` do not set the flag either: it needs code context.
- An inline code span is not code context. A markdown link on a line that also
  has a backticked filename elsewhere is documentation, not a runtime host.
- Install-time is install-time however it is written: `$ pip install`, `sudo apt
  install` and `npm install` inside a backtick all belong in `setup`. Missing
  them makes the installer look like runtime egress and inflates `wide`.
- The reverse also bites: `npm run dev`, `cargo test` and `go build` reach
  nothing. Only the install form of a package command touches the network, which
  is why installers are not "unbounded" shell commands.
- A toolset name (`file`, `web`, `skills`, `browser`) is not a tool. `memory` is a
  tool, but an English word, so it still needs tool-call context.
- `local_apps` is a vocabulary (`{name, syncs_to}`), never a copied source line.
- Files over 400 KB and `node_modules` are skipped and recorded under `skipped`.
  Read that list before declaring a skill clean.
- `import numpy as np` records `numpy`. Aliases are not module names.
- Stage-1 output is a draft. Never raise `confidence` to "fix" a shape, and never
  fill `ceiling` before Stage 4.
