# Validation Spec: security-manifest-audit
# Last updated: 2026-11-24
# Change: Stage-1 static census — tool vocabulary from toolsets.py, inherits reach, local_apps vocabulary, null ceiling

## Positive Checks (MUST be present)

- [ ] Every skill under `skills/` and `optional-skills/` at the audited commit has both
      `manifest.yaml` and `evidence/static.json`.
- [ ] Every manifest validates against `references/manifest.v0.json`, including
      `actions`, `binaries`, `ceiling` and `delegation.rule`.
- [ ] `provenance.method` is one of static/+review/+dynamic/+eval-backtest and
      `confidence <= cap(method)` (static 0.5, +review 0.6, +dynamic 0.75, +eval-backtest 1.0).
- [ ] `provenance.inputs` is present and populated, so the score can be recomputed.
- [ ] `commit` equals `git rev-parse HEAD` of the audited repo.
- [ ] `ceiling` is `null` at `method: static`: it is what the enforcer proves, not a copy
      of the draft shape.
- [ ] `resources.network.runtime` holds only hosts seen in code, commands or scripts.
- [ ] A shell-driving skill records `terminal` (or `execute_code`) with reach >= medium when
      it runs a network command in a fenced block.
- [ ] `delegate_task`, when present, has reach `inherits` and the skill is at least medium.
- [ ] `resources.local_apps` entries are `{name, syncs_to}` from the fixed vocabulary, and
      only when the match is in code or command context.
- [ ] Files and directories the scan skipped are recorded in `evidence.skipped`.
- [ ] `evidence.tool_vocabulary.source` states where the tool names came from.
- [ ] `scripts/test_generate_baseline.py` passes (14 fixture checks).
- [ ] A resource/tool distribution report is regenerated from the finished corpus.

## Negative Checks (MUST NOT be present)

- [ ] No credential values — names only.
- [ ] No unanchored secret patterns: the bare `sk-` matched task-/risk-. The anchored set is
      `\bsk-[A-Za-z0-9]{20,}`, `\bghp_[A-Za-z0-9]{36}\b`, `\bAKIA[0-9A-Z]{16}\b`, plus
      `sk-ant-`, `gho_`, `ghs_`, `github_pat_`, `xox[baprs]-` and `Bearer `.
- [ ] No toolset names in `tools`: `file`, `web`, `skills`, `browser`, `process`, `sandbox`.
      (`memory` IS a tool — keep it, but only when it appears in a tool-call context.)
- [ ] No copied source line in `local_apps`: no newline, quote or `#`, and under 40 chars.
- [ ] No host in more than one of runtime / setup / artifact_refs.
- [ ] No duplicated host within a single network list.
- [ ] No URL userinfo, query string or fragment stored in evidence.
- [ ] No manifest at `method: static` marked production-ready.
- [ ] No `confidence` raised without the matching `method` stage and fresh `inputs`.
- [ ] No `raw_sockets: true` from prose: it requires code or command context.

## Format Checks

- [ ] Report is Markdown; the summary sent to chat uses short bullets, not wide tables.
