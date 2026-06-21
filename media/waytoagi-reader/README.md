# waytoagi-reader

Read the WaytoAGI (通往AGI之路) Feishu wiki daily update log as structured JSON. No authentication required — uses the public guest-mode SSR endpoint.

## Install

```sh
cd media/waytoagi-reader
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

For tests: `pip install -e ".[dev]"`.

## Use

```sh
waytoagi update-log                              # 7-day section, grouped by day
waytoagi update-log --date '6 月 18 日'           # one day
waytoagi update-log --flatten                    # flat items[]
waytoagi update-log --emit-raw-blocks            # debug
```

Exit codes: `0` ok, `3` heading not found, `4` transient, `5` SSR contract broken.

## How it works

1. `GET https://waytoagi.feishu.cn/wiki/<token>?with_guest=1` — Feishu sets `swp_csrf_token` via redirect and returns the SSR HTML.
2. The HTML inlines the full docx block tree as `"<token>":{"id":"<same-token>","data":{...}}` fragments. We anchor-match and balance-parse each block.
3. Decode AttributedText: `apool.numToAttrib` provides per-key metadata; `initialAttributedTexts.attribs` is a run-length encoding of which keys apply to which spans of `text`. `mention_doc` components yield `{title, url, token}`.
4. Match the target heading by normalized text (emoji- and whitespace-tolerant), collect its siblings up to the next same-or-shallower heading, group children by heading-level boundary into "days".

See `SKILL.md` for agent invocation, `LICENSING.md` for fixture policy, `schemas/update_log.schema.json` for the output contract.

## Cache

Raw-HTML TTL cache, default 300s. Override with `WAYTOAGI_CACHE_DIR`, `WAYTOAGI_CACHE_RAW_TTL`. Use `--no-cache` to bypass or `--refresh` to overwrite. Feishu sends `Cache-Control: no-store` and no `ETag`/`Last-Modified`, so conditional revalidation isn't currently feasible.

## Roadmap

- Parsed-blocks and rendered-output cache tiers (raw-only ships in v0.1).
- `waytoagi article <url>` sub-command that fetches a linked WaytoAGI wiki entry (currently we surface titles + URLs but don't follow them).
- Cloud LLM backends for the sibling `translate` skill.
