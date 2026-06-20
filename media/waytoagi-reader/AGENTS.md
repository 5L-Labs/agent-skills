# AGENTS.md — waytoagi-reader

Entrypoint for any agent following the AGENTS.md convention (Codex, Cursor, Aider, generic CLI agents). Mirrors `SKILL.md` and `GEMINI.md`.

## Invocation

After `pip install -e .` in this directory:

```
waytoagi update-log [--url URL] [--heading TEXT] [--date 'M 月 D 日'] [--flatten] [--emit-raw-blocks]
```

The command prints one JSON object to stdout with `"schema_version": 1`. Errors go to stderr.

No authentication required — the WaytoAGI wiki is publicly readable in guest mode.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 3 | `NOT_FOUND` — heading text didn't match any heading block in the SSR (try `--heading` with current literal text) |
| 4 | transient — network/timeout/decode error |
| 5 | `UPSTREAM_CONTRACT_BROKEN` — zero blocks parsed, or heading found but section empty (Feishu likely changed SSR shape; run with `--emit-raw-blocks` and inspect) |

## Required environment

Cache (v0.1, raw-HTML tier): `WAYTOAGI_CACHE_DIR` (default `$XDG_CACHE_HOME/waytoagi-reader`), `WAYTOAGI_CACHE_RAW_TTL` (default 300s).

## Output schema

See `schemas/update_log.schema.json`. Days are heading-level blocks under the target section; each day's items live as that heading's children. Items have `{id, type, title, url, summary}`.

## Non-interactive guarantee

The CLI never prompts.

## Example agent workflow

```sh
# Pull today's WaytoAGI updates as flat items and pipe titles to another tool.
waytoagi update-log --flatten | jq -r '.items[] | select(.title) | "\(.title)\t\(.url)"'
```

```sh
# Translate Chinese summaries to English via the (planned) sibling translate skill.
waytoagi update-log | translate --target en
```
