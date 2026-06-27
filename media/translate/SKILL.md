---
name: translate
description: JSON-in/JSON-out translation pipe. Translates selected string fields in any JSON document (defaults work for the reader-skill schema family — title/headline/heading/summary/text). Pluggable LLM backend; defaults to local Ollama; cache stable across runs.
version: 0.1.0
author: Nick Lange
license: Apache-2.0
metadata:
  hermes:
    tags: [translate, llm, ollama, post-processor, json, agent-cli]
    required_environment_variables: []
    required_commands: [translate, python]
---

# translate

A composition primitive for the reader-skill family. Reads JSON on stdin, walks the document, translates selected string fields, writes JSON to stdout.

```sh
waytoagi update-log | translate --target en
wsj headlines      | translate --target en --model qwen2.5:32b-instruct
ft myft            | translate --target zh --backend openai
```

## When to Use — natural-language → command

| User says… | Run |
|---|---|
| "translate this WaytoAGI feed to English" | `waytoagi update-log \| translate --target en` |
| "in-place Chinese → English" | `waytoagi update-log \| translate --target en --inplace` |
| "swap to a bigger local model" | `translate --target en --model qwen2.5:32b-instruct` |
| "use cloud" | `TRANSLATE_BACKEND=openai translate --target en` (planned; v0.1 ships noop + ollama) |

## Install

```sh
cd media/translate
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Zero install-time dependencies; only stdlib (urllib) is used to call backends.

## Default fields walked

`title`, `headline`, `heading`, `summary`, `text` — matches the reader-skill JSON family.

Override with `--field`:

- `--field title,summary` → exactly those fields.
- `--field +flashline,-text` → start from defaults, add `flashline`, drop `text`.

## Output

For each translated field, a sibling `<key>_<lang>` is added:

```json
{"title": "🎏 近 7 日更新日志", "title_en": "🎏 Last 7 Days Changelog"}
```

`--inplace` replaces the source string instead.

On per-item failure, the sibling is set to `null` and a `<key>_<lang>_error` field captures the cause. Failures don't abort the run.

## Cache

Translations of a fixed input under a fixed (backend, model, prompt) are stable. Cached indefinitely at `$XDG_CACHE_HOME/translate/{first2}/{sha}.json`.

The cache key includes `backend`, `model`, and a prompt-version hash — swapping models does NOT silently reuse the older output.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | `BAD_INPUT` — stdin was not valid JSON |
| 4 | `BACKEND` — at least one item failed (failed items are reported inline as `_error` siblings) |

## Backends

- `noop` — echoes `[<target>] <text>`. Useful for pipeline testing without an LLM.
- `ollama` — calls `http://localhost:11434/api/chat`. Configure with `TRANSLATE_MODEL` (default `qwen2.5:7b-instruct`) and `OLLAMA_HOST`.

Planned: `openai`, `anthropic`, `llamacpp`, multi-backend fallback (`TRANSLATE_FALLBACK`).
