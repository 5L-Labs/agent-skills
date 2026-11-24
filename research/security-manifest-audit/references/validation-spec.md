# Validation Spec: security-manifest-audit
# Last updated: 2026-11-24
# Change: Stage-1 static census — deterministic fixes, schema validation, stage-capped confidence

## Positive Checks (MUST be present)

- [ ] Every skill under `skills/` and `optional-skills/` at the audited commit has both
      `manifest.yaml` and `evidence/static.json`.
- [ ] Every manifest validates against `references/manifest.v0.json`, including
      `actions`, `binaries`, `ceiling` and `delegation.rule`.
- [ ] `provenance.method` is one of static/+review/+dynamic/+eval-backtest and
      `confidence <= cap(method)` (static 0.5, +review 0.6, +dynamic 0.75, +eval-backtest 1.0).
- [ ] `provenance.inputs` is present and populated, so the score can be recomputed.
- [ ] `commit` equals `git rev-parse HEAD` of the audited repo.
- [ ] `resources.network.runtime` holds only hosts seen in code, commands or scripts.
- [ ] `resources.local_apps` is populated wherever the Apple/iMessage/iCloud regex matches.
- [ ] Files and directories the scan skipped are recorded in `evidence.skipped`.
- [ ] A resource/tool distribution report is regenerated from the finished corpus.

## Negative Checks (MUST NOT be present)

- [ ] No credential values — names only.
- [ ] No unanchored secret patterns: the bare `sk-` matched task-/risk-. The anchored set is
      `\bsk-[A-Za-z0-9]{20,}`, `\bghp_[A-Za-z0-9]{36}\b`, `\bAKIA[0-9A-Z]{16}\b`, plus
      `sk-ant-`, `gho_`, `ghs_`, `github_pat_`, `xox[baprs]-` and `Bearer `.
- [ ] No prose-only words in `tools`: `file`, `memory`, `skills`, `web`, `browser`, `process`.
- [ ] No host in more than one of runtime / setup / artifact_refs.
- [ ] No duplicated host within a single network list.
- [ ] No URL userinfo, query string or fragment stored in evidence.
- [ ] No manifest at `method: static` marked production-ready.
- [ ] No `confidence` raised without the matching `method` stage and fresh `inputs`.

## Format Checks

- [ ] Report is Markdown; the summary sent to chat uses short bullets, not wide tables.
