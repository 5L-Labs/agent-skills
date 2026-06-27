# GEMINI.md — waytoagi-reader

Entrypoint for the Gemini CLI. Same contract as `SKILL.md` (Claude) and `AGENTS.md` (Codex/generic).

## Invocation

```
waytoagi update-log [--url URL] [--heading TEXT] [--date 'M 月 D 日'] [--flatten] [--emit-raw-blocks]
```

JSON to stdout with `"schema_version": 1`. Errors to stderr.

Exit codes: `0` ok, `3` `NOT_FOUND`, `4` transient, `5` `UPSTREAM_CONTRACT_BROKEN`.

## Setup

1. `pip install -e .` in `media/waytoagi-reader/`.
2. That's it — no API keys, no cookies, no app registration. The WaytoAGI wiki is publicly readable in guest mode.

## Output schema

`schemas/update_log.schema.json` defines the output shape.

## Politeness

One fetch per invocation under normal use. No parallel fetches. Default User-Agent is a modern Chrome string.

## Caching

Raw-HTML TTL cache (default 300s). Override with `WAYTOAGI_CACHE_DIR`, `WAYTOAGI_CACHE_RAW_TTL`. `--no-cache` / `--refresh` flags also available. Feishu sends no ETag/Last-Modified, so conditional revalidation is currently infeasible.
