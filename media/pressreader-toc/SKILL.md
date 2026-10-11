---
name: pressreader-toc
description: Fetch the FT print edition table-of-contents from PressReader, normalize it into per-section story lists, and map print stories to ft.com URLs for downstream podcast processing.
version: 0.1.0
author: Nick Lange
license: Apache-2.0
metadata:
  hermes:
    tags: [ft, pressreader, newspaper, toc, weekend, podcast, json, agent-cli]
    required_environment_variables: [FT_COOKIE]
    required_commands: [python, prtoc, ft]
---

# pressreader-toc

Fetch the FT print edition table-of-contents from the public PressReader CDN (no auth needed for TOC), normalize it into per-section story lists, and map print stories to ft.com URLs via `ft search`. The output feeds the podcast pipeline.

## When to Use — natural-language → command

| User says… | Run |
|---|---|
| "what's in this weekend's Life & Arts", "show me today's FT sections", "list House & Home stories" | `prtoc toc weekend` |
| "map this weekend's stories to ft.com", "match the print stories" | `prtoc match weekend --buckets life-arts,house-home,magazine` |
| "give me the Life & Arts URLs for the podcast", "what can I listen to?" | `prtoc stories weekend --buckets life-arts --format urls` |

## Setup

**One-time, by the human** (requires a browser):

1. Run `ft` (from the `ft-reader` skill) and ensure `FT_COOKIE` is set in your env or `.env` file.
   - `prtoc toc` does NOT need this (the TOC endpoint is public).
   - `prtoc match` and `ft search` need it.
2. Install: `python3 -m pip install --user -e /path/to/agent-skills/media/pressreader-toc`
3. Also install `ft-reader` (`ft search` must be on PATH for `prtoc match`).

Optional: set `PRESSREADER_DATA_DIR` to control where issue JSON files are stored (default: `~/.pressreader/issues/`).

## Agent invocation

```bash
prtoc toc today             # Fetch today's FT (and HTSI if Saturday)
prtoc toc weekend           # Most recent Saturday's paper
prtoc toc 2026-07-04        # Specific date

prtoc match 2026-07-04      # Map stories to ft.com (weekend buckets by default)
prtoc match 2026-07-04 --all  # Include main news sections too (more ft.com queries)
prtoc match 2026-07-04 --buckets life-arts,house-home --dry-run  # Preview queries

prtoc stories 2026-07-04 --format urls   # Clean URL list for downstream
prtoc stories 2026-07-04 --format json   # Full records with match scores
```

All commands print JSON to stdout. Errors go to stderr. `--json-errors` mirrors errors as `{"error": {...}}` on stdout. Exit codes: `0` ok, `3` not found, `2` session expired (ft cookie stale), `4` network error, `1` other.

## Weekend podcast recipe

```bash
# Step 1: fetch TOC for this weekend (public CDN, no auth)
prtoc toc weekend

# Step 2: map Life & Arts + House & Home + Magazine to ft.com (~20 searches, ~1 min)
prtoc match weekend --buckets life-arts,house-home,magazine

# Step 3: hand off to podcast pipeline
prtoc stories weekend --buckets life-arts,house-home,magazine --format urls \
  | while read url; do
      ft article "$url" | jq -r '.audio.url // empty'
    done
```

## Commands

### `prtoc toc <date|weekend|today>`

Fetches and normalizes the TOC. `weekend` = today if Saturday, else most recent Saturday. Dates are the print cover date in local time (fine for US edition / US timezone).

Returns: `{schema_version, date, total_stories, issues: [{cid, pub_name, cached, entries: [...]}]}`

Each entry has:
- `kind`: `story` | `teaser` | `filler`
- `title`, `byline`, `text` (snippet)
- `page`, `pages` (for multi-page articles)
- `section`, `theme` (e.g. section=`"Magazine"`, theme=`"America At 250"`)
- `bucket`: `main` | `life-arts` | `books-arts-travel-style-food` | `house-home` | `magazine` | `htsi` | `data`
- `match_status`: `pending` (fresh), `matched`, or `unmatched`

Cache: the normalized issue is stored in `PRESSREADER_DATA_DIR` and reused on subsequent runs. Use `--refresh` to re-fetch.

PressReader publishes on Saturdays: `v99e` (FT US daily) + `9lh5` (HTSI US); HTSI skips some weeks. If HTSI isn't found with `--pub all`, a warning is emitted and the FT issue is still returned. Use `--pub htsi` to fail explicitly.

### `prtoc match <date>`

Maps `kind=story` entries in the stored issue to ft.com URLs via `ft search`. Resumable — already-matched entries are skipped. `--retry-unmatched` to retry failures.

Default scope: weekend buckets (`life-arts`, `books-arts-travel-style-food`, `house-home`, `magazine`, `htsi`). Add `--all` to also match main news sections (more searches, more ft.com quota consumed).

Throttled at ~2s + jitter between searches to avoid triggering ft.com rate limits. Results cached 30 days in the ft-reader cache — re-runs after scoring tweaks are free.

Aborts immediately on exit code 2 (SESSION_EXPIRED) and persists partial state. On abort, re-run after refreshing `FT_COOKIE`.

Returns: `{schema_version, date, report: {searched, matched, unmatched, low_confidence, aborted, unmatched_titles, low_confidence_titles}}`

### `prtoc stories <date>`

Emits matched stories for the given buckets. `--format urls` (default) prints one URL per line; `--format json` returns full records.

## Notes

- **No PressReader auth needed**: TOC endpoint is public CDN. Never crawl article bodies/images from PressReader.
- **ft.com ban risk**: `ft search` uses your real session cookie. `prtoc match` defaults to weekend buckets (~20–50 queries), not all 124 daily stories, to minimize exposure.
- **HTSI TTS MP3s**: PressReader serves per-article TTS audio at `a.prcdn.co/tts/<uid>$en_en.mp3`. Not implemented yet — potential future fallback for print-only pieces that don't match on ft.com.
- **Cookie refresh**: When `ft search` returns SESSION_EXPIRED, see the ft-reader SKILL.md for how to re-paste the FT cookie from a browser DevTools session.
