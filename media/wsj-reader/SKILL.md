---
name: wsj-reader
description: Read WSJ headlines, articles and read-to-me audio; session cookie required.
version: 0.3.0
author: Nick Lange
license: Apache-2.0
metadata:
  hermes:
    tags: [wsj, wall-street-journal, news, audio, read-to-me, json, agent-cli]
    required_environment_variables: []
    required_commands: [python, wsj]
---

# wsj-reader

Programmatic WSJ access. Headline collections come from WSJ's authenticated GraphQL gateway (the cookie-free homepage scrape was bot-walled with 401s ~2026-10-01); article bodies and URL-based audio resolution use the same logged-in session cookies. Exposes CLI commands emitting JSON for consumption by other agents/skills.

## When to Use — natural-language → command

| User says… | Run |
|---|---|
| "today's WSJ", "what's on the front page" | `wsj headlines --via=graphql --limit 10` |
| "WSJ print edition headlines" | `wsj headlines --via=html` |
| "WSJ business section today" | `wsj headlines --via=html --section business` |
| "read the WSJ article at <url>" | `wsj article <url>` |
| "download the WSJ audio for this story" | `wsj audio <url-or-WP-WSJ-id> --download` |

## Setup

**One-time, by the human** — required for headlines (graphql), article/audio URL access (requires a browser):

1. Sign in to https://www.wsj.com.
2. DevTools → **Network** → click any `www.wsj.com` request → copy the full `Cookie:` header value.
3. From this skill's directory: `pbpaste | python scripts/set_cookie.py` (writes `.env` mode 600). A bookmarklet for one-click copy:

   ```
   javascript:(()=>{navigator.clipboard.writeText(document.cookie).then(()=>alert('WSJ cookies copied ('+document.cookie.length+' chars).'));})();
   ```

**One-time install**:

```bash
python3 -m pip install --user -e /path/to/agent-skills/media/wsj-reader
```

When an authenticated command prints `SESSION_EXPIRED` (exit code 2), repeat the cookie capture. WSJ's full Cookie header is required for article extraction — no minimal subset works.

## Agent invocation

```bash
wsj headlines --via=graphql --limit 10          # recommended path (cookie required)
wsj headlines --via=html --date 20260608       # specific print-edition date, requires cookie
wsj headlines --via=html --section business --limit 5
wsj headlines --via=graphql --collection most-popular --limit 5
wsj article https://www.wsj.com/finance/...html
wsj audio https://www.wsj.com/finance/...html --download
wsj audio WP-WSJ-0003640310 --download        # bypass the article fetch
```

Fallback if `wsj` is not on PATH: `python3 -m wsj_reader.cli headlines`.

Add `--json-errors` to mirror failures as structured JSON on stdout.

## How audio works

WSJ doesn't inline audio URLs in either headlines or articles. The flow:

1. Article page → extract `articleData.id` (e.g. `WP-WSJ-0003640310`) from `__NEXT_DATA__`.
2. `GET video-api.shdsvc.dowjones.io/api/legacy/find-all-videos?type=read-to-me&query={id}` → JSON with the canonical audio `id` (UUID) and creation date.
3. Construct `https://m.wsj.net/audio/{YYYYMMDD}/{uuid}/1/ele-{id-lower}-full.mp3` — public CDN, no auth on the MP3 itself.

The skill caches the audio-resolution call for 30 days alongside the MP3.

## Politeness

- 400ms ± 100ms jittered spacing between origin fetches (`WSJ_REQUEST_SPACING_MS`). WSJ is more sensitive than NYT/FT — keep the gap.
- Single-threaded; no parallel fetches.
- Adaptive backoff on 429/503, respects `Retry-After`.
- Per-invocation fetch budget of 200 (`WSJ_MAX_FETCHES`).
- Browser-like headers (`Sec-Fetch-*`, `Referer`, `Origin`) are required by WSJ's edge — included automatically.

## Cache

`media/wsj-reader/cache/` by default; override with `WSJ_CACHE_DIR`. Tiered TTL: articles + MP3s + audio-resolve 30d, headlines 1h.

## Tests

`pip install -e ".[dev]" && pytest` — unit tests use synthetic fixtures and HTTP mocks (no live calls, no copyrighted WSJ content in the repo).

## Pitfalls

- **Cookie-free homepage is dead (as of ~2026-10-01).** WSJ put a 401 bot-challenge
  wall on `https://www.wsj.com/` HTML; `headlines` default (`--via homepage`) now
  exits 4 NETWORK on datacenter IPs. Use `--via graphql` with the cookie instead.
- **GraphQL `--limit` > 10 risks a 403 → misleading `SESSION_EXPIRED` (exit 2).**
  WSJ's gateway treats `articleLimitPerCollection` above the ceiling 10 as scraping
  (verified: 3/5/10 pass, 15/20 blocked; 11–14 untested — the ceiling is the highest
  verified-safe value). The cookie is fine. As of 0.3.0 the graphql transport
  self-heals: on a 403 above the ceiling it retries once at `--limit 10` and adds a
  `graphql_note` to the payload. If you see SESSION_EXPIRED at limit ≤ 10, THAT is
  a real cookie expiry — re-paste.
- `daily-headlines.py` tries homepage first, falls back to graphql at `--limit 10`.

## Version History

- 0.3.0 (2026-10-07): GraphQL transport now downshifts limit-triggered 403s and retries at ceiling 10 (`graphql_note` in payload); 403 at safe limits still raises SESSION_EXPIRED.
- 0.2.1 (2026-10-07): Homepage transport blocked (401 bot wall, ~2026-10-01);
  documented graphql limit ceiling (≤10) and SESSION_EXPIRED false-positive.
  daily-headlines.py gained homepage → graphql(limit 10) fallback.
- 0.2.0 (2026-07-15): WSJ's shared-data.dowjones.io GraphQL endpoint now requires cookies.
  Added `Cookie` header to GraphQL transport. Both transports still work; the cookie
  is no longer optional for the GraphQL path.
