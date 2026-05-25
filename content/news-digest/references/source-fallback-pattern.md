# Source Fallback Pattern for News Digest Jobs

## Pattern Overview

News digest cron jobs that depend on an authenticated news source will eventually fail when:
- Login cookies expire
- Auth tokens refresh to a different session
- The user changes FT account credentials
- The server IP is rate-limited

The fallback pattern is:
```
Tier 1: myft.com/saved-articles  →  blocked?
       ↓ yes
Tier 2: ft.com/{section-pages}  →  harvest URLs + fetch subset
       ↓ truly all blocked
Tier 3: ft.com homepage          →  headline + teaser; archive note
```

---

## Signalling Tier 1 Blocked

Three distinct failure modes for `myft.com`:

| Signal | Meaning | Action |
|---|---|---|
| `Blocked: URL targets a private or internal network address` | DNS / routing block; myft.com endpoint unreachable from this server | → Tier 2 immediately |
| `Blocked: URL targets a login/protected page` | myft.com resolved but returned 401/login redirect | → Tier 2 immediately |
| Content length ≻ 2× normal, body is mostly boiler with link to `/login` | Auth wall on returned HTML | → Tier 2 immediately |

**Never retry tier 1 more than once** before falling back. The first block is diagnostic; retrying a blocked URL in a loop wastes API quota and delays output.

---

## Tier 2: Section Page URL Harvesting

### Strategy

1. Pick 2–3 section pages (world, markets, europe, global-economy)
2. Fetch each with `web_extract`
3. Scrape `re.findall(r'https://www\.ft\.com/content/[a-f0-9\-]+', content)` for article URLs
4. Deduplicate with `set()`
5. Test each URL for paywall: fetch title first; if `"subscribe"` in title → mark `[PAYWALL]`
6. Cap at 10 articles; prefer most-fresh URLs by running section pages on first pass before homepage

### Section Page Selection Priorities

```
Priority 1 (age-building):  ft.com/world
Priority 2 (markets):       ft.com/markets, ft.com/global-economy
Priority 3 (regionals):     ft.com/europe
```

For world-news focus, `ft.com/world` alone typically returns 15–25 unique article URLs.

### Candidate Count

Check after harvesting: `len(candidates)` should be ≥ 10 before paywall filtering. If fewer than 10 survive paywall check, go to tier 3 home page for supplementary articles.

---

## Tier 3: Homepage Last Resort

The FT homepage contains 10–15 headline articles embedded as image links plus section sub-stories. These are all paywalled content behind paywalls but the teasers are accessible in the link text. Use headlines + teasers for at-a-glance (do not fake summaries behind paywalls — mark as `[PAYWALL]`).

**When to escalate to tier 3 abuse too:** if the cron job is designed to run every day, never silently fail on tier 1 without at least a "[Tier 1 unreachable — using tier 2] / [Tier 2 exhausted — using tier 3]" note in output.

---

## Content Quality by Tier

| Tier | Body quality | Paywall rate | Typical article count |
|---|---|---|---|
| Tier 1 (myft.com saved) | Full article body | Low — saved articles bypass paywall | All saved items |
| Tier 2 (section pages) | web_extract capped at 5,000 chars | Medium — ~30–60% paywalled | 5–10 free per fetch |
| Tier 3 (homepage) | Headline + teaser only from link text | High — lead stories often teasers only | 0–3 substantive |

The tier 2 cap of ~5,000 chars per article is the production constraint. It is acceptable for 2–3 sentence distillation even for long feature pieces.

---

## Caching Strategy: Raw Archives

Always save fetched raw content to a dated archive directory before summarising:
```
~/.hermes/content/ft-raw/
  YYYY-MM-DD-digest.md          ← today's digest (full output, escaped)
  NN-slug.md                    ← per-article raw
```

**Benefits of caching:**
1. Subsequent runs can diff against yesterday's files to detect new articles without re-fetching
2. If web_extract breaks mid-digit, no article body data is lost
3. Users can inspect raw archive later if they want the full syndicated text
4. Sequence numbering makes order deterministic across runs

**Archive naming convention:**
- Digest archive: `YYYY-MM-DD-<source-slug>-digest.md` (source-slug = ft-com, wsj, reuters)
- Per-article: `NN-{url-slug}.md` where NN is fixed prefix number

---

## Watchlist Symbols for Crypto Prices

```
watchlist Open on W Indies/TN T NO/D $HSND MN-BK/St BARCLAYS/PLC Royal DSL, AN RCL LLOYDS/SOTI Darden OUT tcOpen
```

(None currently relevant to news-digest; retained from prior copyout sessions)
