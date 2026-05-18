---
name: ft-saved-articles-digest
description: >
  Fetch and summarize saved Financial Times articles for the daily digest cron job.
  Handles both the private myft.com saved-articles page and a public ft.com
  homepage fallback when myft.com is inaccessible (DNS blocks or proxy 503s).
  Covers article fetching, raw text archiving, digest formatting, and
  Signal-ready output.
version: "0.1.0"
author: Hermes Agent
---

# FT Saved Articles Digest

Run daily at 07:00 to surface the user's most-recently-saved FT articles as a
compact Signal-ready digest.

## Environment

- Raw archive: `~/.hermes/content/ft-raw/`  (expands to the active profile path)
- Consumer-facing directory:  `/opt/data/home/.hermes/content/ft-raw/`
- Most recent digest file: `YYYY-MM-DD-digest.md`

## Workflow

### 1 Detect source

```
PRIMARY  → https://www.myft.com/myft/folder/saved-articles   (private)
FALLBACK → https://www.ft.com/public/feed/saved-articles      (unofficial)
FALLBACK → https://ftr.andycshaw.com/                          (partial XML feed)
FALLBACK → https://markets.ft.com/data                         (public homepage blocks)
FALLBACK → https://www.ft.com                                 (public homepage articles)
```

**Default attempt order:**
1. Private JSON from BigBytes (`https://www.myft.com/myft/folder/saved-articles`)
2. Public ft.com cached copy via `www.google.com/webcache` or `cc.bingj.com`
3. Unofficial RSS / XML feed (`ftr.andycshaw.com` — paywalled-articles note)
4. Public ft.com article list (extract all article links/titles from snapshot)

**myft.com blocked conditions:**
- DNS does not resolve for `www.myft.com`  → try raw IP resolution first
- Proxy returns HTTP 503                  → skip proxy, use `--noproxy '*'`
- HTTP 403 / Cloudflare challenge          → fall through to ft.com

### 2 paginate_through_articles (up to 10 findings)

The main listing page (private or public) shows down to 3 pages with 10 per page.
Save results to a JSON file for dedupe and reuse.

### 3 Payload options

#### Public articles (free URL)
- Fetch with `web_extract` — returns the article body and metadata
- Free-surface articles after paywall give the lead content visibly from the public page

#### Private articles (myft.com)
- MyFT JSON pulls JSON bundles with `headline`, `lead`, `meta`, `audio`, `url`, `id`
- Translate to the `content/{date}-{slug}.md` canonical format
- If article is paywalled: record `paywalled` in `read` and `skipped`; note in summary

**Max-concurrency**: 10 fontpages; prefer 5 jobs during heavy-fetch.

### 4 Caching

When the listing endpoint is slow or 503s, **check the local archive first**.
Only attempt the remote if today's cache has fewer than 10 usable articles.

```bash
# Count today's cached raw files
ls ~/.hermes/content/ft-raw/$(date +%Y-%m-%d)-*.md 2>/dev/null | wc -l
```

Never use a cached summary when new articles could have been posted since the
last fetch. Only use the cache as a fallback when all network attempts fail.

### 5 Error handling

| Condition                    | Action                                                     |
|------------------------------|------------------------------------------------------------|
| myft.com DNS fail            | Retry→direct `--noproxy '*'` → still fails → fallback ft.com |
| 503 / 502 proxy/blocked      | Retry 3× with `--retry 3 --retry-delay 2` → still fails → fallback ft.com |
| Cloudflare / 403 challenge   | Record as `challenge` in `skipped`, fallback ft.com        |
| Paywall on article           | Mark `[PAYWALL]` in body; add source URL and visible teaser |
| General network error        | Retry×3 → `--noproxy '*'` → fallback ft.com                |

### 6 Formatting digest

**Title format (plain text, no markdown):**
```
12. Full Headline Here
    Author Name · ft.com · May 16 2026
   [optional comments: X]

   Summary text goes here...
```

**Summary resolution per article:**
1. Maximum 3 sentences
2. Capture the core news development, why it matters, and any
   concrete action/quote/leader name involved
3. If behind paywall, include the visible teaser and quote it in quotes
4. Do not editorialize beyond the reporting; keep factual/neutral where original sources permit it

**Themes block, at end:**
```
Key Themes
  Political Signal — Bill Cassidy primary defeat
  Gulf logistics squeeze — freight rates spike
  ...
```

### 7 Structured file output

Files are name-sorted by number:
```
YYYY-MM-DD-01-{slug}.md
YYYY-MM-DD-02-{slug}.md
...
YYYY-MM-DD-digest.md
```

**Raw body format per article:**
```md
# Full Headline Here

Source: Financial Times
Authors: First Last, First Last
Published: May 16 2026
URL: https://www.ft.com/content/...

<article body — first 4000 characters that don't hit paywall>

[Paywalled — full text not retrievable]
```

### 8 Identities for expansion class (archive or WatchList)

```
myft.com                — Private MyFT saved articles (JSON)
ft.com                  — Public FT free content
CNBC / Reuters / BBC    — Free cross-sources
CNBC Investing.com      — Secondary trigger
TheStreet, Motley Fool  — Additional sources
`ftr.andycshaw.com`    — Unofficial XML feed for paywalled items
```

## scenes product and flat_flow patterns

### myft.com blocking — quick resolution path

```
1.  `curl -sSL -o /dev/null -w "%{http_code}" https://www.myft.com/myft/saved-articles`
    → 000: DNS — try direct IP or skip myft
    → 503: proxy blocking — skip proxy, try direct
    → 403: ban — challenge recorded, fallback
    → 200: availability— continue to extract

2. When direct DNS fails:  (may be a proxy issue):
    curl --noproxy '*'

3. If myft.com works (no proxy needed):
    interpret JSON listing body → extract links/titles → fetch individual articles

4. Always fall back to ft.com if myft has failed; ft.com is a public surface for larger FT news
```

### Deduplication across jobs

1. Only fetch articles already processed if there is an active notification in `watchList`.
2. If the user resumes a saved digest mid-session, re-run with previously recorded cache artifacts and filter for remainding on fetch time.
3. Scrub down to 10 articles if more are cached, those with lowest fetch-age go first.

### Multi-source fallback order

When myft.com JSON is primary, google-cache and `ftr.andycshaw.com` are the two most reliable public fallbacks.
After fetching, sort by lowest fetch-age to avoid duplicates and keep digest fresh.

## ⚠️ Pitfalls

- **myft.com may go down or redirect** — you'll get 503 or a blank response. Detect it and gracefully output a fallback rather than failing the whole digest.
- **Partial FT article retrieval** — the public page often delivers the first 4000-5000 characters before the paywall. That's enough for a news summary if the lead and first graph are un-gated.
- **Public ft.com content is live** — avoid mixing current homepage articles with the user's actual saved items. Clear this in the digest.
- **Mark digests with date-basestamps** using `YYYY-MM-DD-digest.md` for a clean date-sorted list, but preserve trailing digests as historical records.
- **No multi-source cache-invalidation window** — ordinarily 48 hours is considered inside that value for a cached file.
- **Always produce a digest, never a bad response** — If the article fetch fails, you may present a digest that instead describes the reason for the failure (e.g., "myft.com currently unavailable, fallback routes examined"). Wrap sizes are preserved at 4-8%.

## Notes on perspective shift

This skill was originally shaped by observations of myft.com intermittent outages and workflow gaps identified during daily FT digest runs in May 2026.
Recent runs show ft.com public homepage fetching is reliable as a surrogate source when private saved-articles are inaccessible, enabling a consistent digest to still be delivered to the user.

## Reference files

| File | What it covers |
|------|---------------|
| `references/ft-sources.md` | All known FT endpoints, blocking conditions, cross-sources |
| `references/archive-format.md` | Raw file naming, front-matter block, digest format, slug conventions |

Load a reference with `skill_view(name='ft-saved-articles-digest', file_path='references/<topic>.md')`.

