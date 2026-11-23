---
name: security-manifest-audit
description: "Use when auditing skills into security manifests."
version: 1.0.0
author: Hermes Agent 01
license: MIT
metadata:
  hermes:
    tags: [security, audit, manifests, delegation]
---

# Security Manifest Audit

Builds a per-skill `manifest.yaml` + `evidence/static.json` corpus for a skill catalog. No skill code is executed and no network calls are made by the auditors.

## When to Use

Use when a skill catalog needs a security/egress census: manifest generation, tool-reach classification, credential/host discovery, or a repeatable audit of many skills at once.

## Architecture: deterministic first

1. Enumerate skills into 15-skill batch files. Keep briefing, batches, retries, generator and reports in the audited repo under `security-manifests/_run/` so restarts survive scratch pruning.
2. Run `scripts/generate_baseline.py` with `/usr/bin/python3` (needs PyYAML). It scans every text file and emits evidence JSON plus draft manifests. Baseline shapes over-call `wide` — they are drafts, not truth.
3. LLM review in five-skill micro-batches. Each child reads the full skill source, patches files in place, and checkpoints after EACH skill. Never rewrite a verified skill.
4. Final deterministic validation and a resource/tool distribution report.

## Dispatch rules (learned the hard way)

- Pin the child model in config with `hermes config set delegation.model <model>` and `delegation.provider`. Per-task `model`/`provider` fields passed to `delegate_task` are ignored when config pins one.
- Keep `delegation.max_concurrent_children` at 3 and send at most 3 tasks per call. The tool rejects larger calls, and a 10-way fan-out hit Nous Portal 429 fair-share.
- A free model at 3-way concurrency is the safe default. Paid models can die mid-run with 402 out-of-credits. Per-skill checkpointing makes this survivable.
- In delegated sessions `execute_code` approval prompts block. Put "use `patch`/`write_file`, never `execute_code`" in the briefing.
- Batch files must carry absolute paths; a relative "read shared_context.md" resolved to the wrong directory in one child.
- A content-policy refusal can arrive AFTER all files were checkpointed. Verify on disk before re-dispatching.

## Manifest invariants

- Schema `hermes-security-manifest/v0`, audited commit, `shape: narrow|medium|wide`, top-level `side_effects` and `delegation` (not nested under `resources`), `provenance.confidence >= 0.7`.
- Shape: narrow = no runtime network or credentials; medium = fixed hosts or scoped credentials; wide = open-world egress or inherited wide delegation. Tool reach uses the same scale; skill shape = widest of code and tools unless the wide part is a declared escalation.
- Credentials: names only. Keep runtime hosts, install-time setup hosts and viewer-side artifact hosts separate. Generic prose tool mentions (`file`, `memory`, `skills`, `web`) are false positives.

## Validation (MUST pass before calling a corpus done)

- [ ] Every skill in the batch lists has both files.
- [ ] All YAML parse and contain every required field.
- [ ] Zero deterministic-baseline notes remain; confidence >= 0.7 everywhere.
- [ ] No secret-like patterns in manifests.
- [ ] Resource/tool distribution report generated.

See `references/playbook.md` for the model-failure matrix, exact validation commands and the report generator.
