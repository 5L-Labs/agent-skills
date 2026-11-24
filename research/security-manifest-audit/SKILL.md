---
name: security-manifest-audit
description: "Use when auditing skills into static security manifests."
version: 2.1.0
author: Hermes Agent 01
license: MIT
metadata:
  hermes:
    tags: [security, audit, manifests, delegation]
---

# Security Manifest Audit — Stage 1, static census

Builds a per-skill `manifest.yaml` + `evidence/static.json` corpus for a skill
catalog, where every grant is backed by evidence a later stage can check.
Output defaults to `<audited-repo>/security-manifests/<skill>/` plus
`_schema/manifest.v0.json` and `_reports/distribution.md`.

**This skill implements Stage 1 only: the static census.** No skill code is
executed and no network calls are made. It reads text and produces drafts at
`provenance.method: static`, `confidence <= 0.5`.

## Stages

| stage | what it earns | method | confidence cap | status |
|---|---|---|---|---|
| 1 static census | which files exist and what they reference | `static` | 0.5 | **implemented here** |
| 2 review | a reviewer verifies shape, hosts and tools against every file | `+review` | 0.6 | TODO |
| 3 deny-all dynamic run | the skill runs in a jail with DNS/CONNECT/SNI sinkholes | `+dynamic` | 0.75 | TODO |
| 4 eval generation + backtest | generated evals pass under narrow/manifest/open jails | `+eval-backtest` | 1.0 | TODO |
| 5 narrowing + export | drop unused grants, add observed hosts, emit OpenShell/nono policies | inherits | - | TODO |

Stage 1 manifests are inputs to stages 2-5, not a finished grant. A manifest at
`method: static` is never production-ready: 0.5 sits below the 0.7 prod floor in
the environment profiles by construction.

## Architecture: deterministic first

1. Run `scripts/generate_baseline.py --repo <audited-repo>`. It enumerates every
   `SKILL.md` under `skills/` and `optional-skills/`, scans the text, and writes
   `<out>/<skill>/manifest.yaml` + `<out>/<skill>/evidence/static.json`. Pass
   `--schema references/manifest.v0.json` to drop the schema into `<out>/_schema/`.
   Deterministic output is a **draft**, not truth.
2. Later stages patch those files in place, one skill at a time, and raise
   `provenance.method` — never the number alone.
3. Validate with `scripts/validate_corpus.py`. It gates on the stage, not the
   score, and regenerates the distribution report.

## What Stage 1 decides deterministically

- Which tool **names** exist is read from the audited repo's `toolsets.py`, so a
  new tool is picked up without editing the generator. The built-in list is the
  fallback and is recorded in the evidence as `tool_vocabulary.source`.
- A URL is a runtime candidate only in code, a command or a script. Prose and
  markdown links are documentation. Install-time commands go to `setup` only,
  never to runtime egress.
- `terminal` and `execute_code` reach is classified from the commands they run:
  an open-world command (`ssh`, `docker`, cloud CLIs, agent CLIs) is `wide`; a
  network CLI against a nameable service (`curl` to a fixed host, `gh`) is
  `medium`; local commands are `narrow`.
- `delegate_task` is `inherits`: Stage 1 does not pin the child's toolset, so the
  parent is as wide as whatever the child is handed. `delegation.rule:
  narrow-only` states the requirement to enforce, not an observed fact.
- Tool names count only in tool-call contexts. `file`, `web`, `skills`, `browser`
  and `process` are toolset names, not tools.
- `local_apps` is a fixed vocabulary (`{name, syncs_to}`), matched only in code
  or command context. No source line is ever copied into a manifest.
- Ports, methods, `est_bytes`, `gpu`, `cpu_ram` and `ceiling` are `unknown`/null
  unless observed; `platforms` falls back to the skill's own frontmatter.
- `raw_sockets` is a flag that requires socket-level enforcement. It does not
  force `wide`: a local debug port is not open-world egress.
- Shape = widest of the skill's own code reach and its tools' reach.

## Manifest format

Schema: `references/manifest.v0.json`. Required top-level keys: `schema`, `skill`,
`path`, `commit`, `shape`, `ceiling`, `summary`, `actions`, `tools`, `binaries`,
`resources`, `side_effects`, `delegation`, `escalations`, `provenance`.

- `actions[]` — `class` (read/draft/write-shared/irreversible), `review_gate`
  (autorun/human) and `service`. Stage 1 drafts one entry per detected write so
  stage 2 confirms rather than invents.
- `binaries[]` — one entry per program with its OpenShell/nono `scope`.
- `ceiling` — `null` at Stage 1. It is what the OpenShell prover enforces, so it
  may not be copied from a draft shape; the validator rejects a non-null ceiling
  at `method: static`.
- `tools[].reach` — `narrow|medium|wide|inherits|unknown`; `inherits` is
  `delegate_task`.
- `delegation.rule: narrow-only`.
- `provenance.inputs` — everything the confidence score is recomputed from:
  `files_scanned`, `files_skipped`, `hosts_runtime`, `hosts_setup`, `tools`,
  `review`, `dynamic`, `backtest`.

## Validation (MUST pass before calling a corpus done)

Run

```bash
/usr/bin/python3 scripts/validate_corpus.py --corpus <out> --repo <audited-repo> \
  --report <out>/_reports/distribution.md
/usr/bin/python3 scripts/test_generate_baseline.py    # generator regression tests
```

It MUST report `result: pass`: every skill covered; YAML/JSON parse; schema
valid; `confidence <= cap(method)`; `provenance.inputs` present; `commit` equals
the audited repo's `git rev-parse HEAD`; `ceiling` null at `method: static`; no
anchored secret patterns; no toolset names in `tools`; runtime/setup/artifact
host sets disjoint; no duplicated hosts.

`references/playbook.md` has exact commands and the review briefing.
`references/validation-spec.md` has the MUST/MUST NOT checks.
`references/run-2026-11.md` has the 185-skill run log (model-failure matrix and
dispatch rules — environment-specific, not skill rules).
