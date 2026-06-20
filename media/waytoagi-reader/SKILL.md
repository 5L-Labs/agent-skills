---
name: waytoagi-reader
description: Read the 通往AGI之路 (WaytoAGI) Feishu wiki daily update log as structured JSON. No auth required — uses the public guest-mode SSR endpoint.
version: 0.1.0
author: Nick Lange
license: Apache-2.0
metadata:
  hermes:
    tags: [waytoagi, feishu, lark, wiki, china, ai-news, json, agent-cli]
    required_environment_variables: []
    required_commands: [python, waytoagi]
---

# waytoagi-reader

Programmatic access to the WaytoAGI Feishu wiki daily update log ("🎏 近 7 日更新日志"). Emits JSON for downstream agents/skills.

No authentication required — the wiki is publicly readable in guest mode. The skill fetches the SSR HTML, extracts the inline Feishu block-tree JSON, decodes AttributedText with apool mention-doc expansion, and renders the target section.

## When to Use — natural-language → command

| User says… | Run |
|---|---|
| "today's WaytoAGI updates", "近 7 日更新日志", "what's new on WaytoAGI" | `waytoagi update-log` |
| "WaytoAGI 6/18", "WaytoAGI June 18" | `waytoagi update-log --date '6 月 18 日'` |
| "flat list of recent WaytoAGI items" | `waytoagi update-log --flatten` |

## Setup

```bash
python3 -m pip install --user -e /path/to/agent-skills/media/waytoagi-reader
```

No `.env`, no cookies, no API key.

## Agent invocation

```bash
waytoagi update-log                              # full 7-day section, grouped by day
waytoagi update-log --date '6 月 18 日'           # one day
waytoagi update-log --flatten                    # flat items[] for downstream pipes
waytoagi update-log --heading '近 7 日更新日志'   # override heading match (defensive)
waytoagi update-log --emit-raw-blocks            # debugging: dump the full block dict
```

Fallback if `waytoagi` is not on PATH: `python3 -m waytoagi_reader.cli update-log`.

## Output

`schemas/update_log.schema.json`. Days are heading-level blocks under the target section; items are the bullets/text/image/divider blocks attached to each day. Each item has `{id, type, title, url, summary}`; `title` and `url` are populated when the bullet contains a Feishu `mention_doc` link (the common case for daily entries).

The flat `--flatten` variant is intended for downstream `translate` pipes (sibling skill in this repo, `media/translate/`).

## Exit codes

| Code | Meaning | Recovery |
|---|---|---|
| 0 | OK | — |
| 3 | NOT_FOUND — heading text didn't match any heading block | Pass `--heading` with the current literal text, or open the page to see if it was renamed |
| 4 | Transient — fetch error, decode error, etc. | Retry |
| 5 | UPSTREAM_CONTRACT_BROKEN — heading found but section empty, or zero blocks parsed | Inspect with `--emit-raw-blocks`; Feishu likely changed SSR shape |

## Politeness

- One fetch per invocation under normal use.
- No parallel fetches.
- Default User-Agent is a modern Chrome string; override is not exposed yet (add if/when a tenant complains).

## Cache

Raw-HTML TTL cache (v0.1). Default 300s. Override with `WAYTOAGI_CACHE_DIR`, `WAYTOAGI_CACHE_RAW_TTL`. `--no-cache` bypasses; `--refresh` bypasses read but writes.

Feishu sends `Cache-Control: no-store` and no `ETag`/`Last-Modified`, so conditional revalidation is not currently possible. The two follow-on tiers (parsed-blocks, rendered JSON) are deliberately deferred — they're a JSON parse away from the raw tier.

## Translation

Out of scope for this skill by design. Compose with the sibling `translate` skill (`media/translate/`):

```bash
waytoagi update-log | translate --target en
```

## Tests

`pip install -e ".[dev]" && pytest`. Synthetic fixtures only — no waytoagi content reproduced in the repo. See `LICENSING.md` for why.
