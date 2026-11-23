# Validation Spec: security-manifest-audit
# Last updated: 2026-11-23
# Change: initial skill, validated against the 185-skill Phase 1 audit

## Positive Checks (MUST be present)

- [ ] Every skill listed in the batch files has both `manifest.yaml` and `evidence/static.json`.
- [ ] Every manifest parses as YAML and contains: schema, skill, path, commit, shape, summary, tools, resources, side_effects, delegation, escalations, provenance.
- [ ] `provenance.confidence >= 0.7` on every manifest and no deterministic-baseline note remains.
- [ ] `shape` is one of narrow, medium, wide; `side_effects` and `delegation` are top-level keys.
- [ ] A resource/tool distribution report is generated from the finished corpus.

## Negative Checks (MUST NOT be present)

- [ ] No credential values in manifests or evidence (names only).
- [ ] No secret-like patterns (`sk-`, `ghp_`, `AKIA`) in manifests.
- [ ] No prose-only tool names left in `tools` (file, memory, skills, web).
- [ ] No runtime/setup/artifact host conflation.

## Format Checks

- [ ] Report is Markdown; summary to chat uses short bullets, not wide tables.
