---
name: ft-saved-articles-digest/references/ft-sources
description: >
  Canonical URLs and endpoints known to carry (or have carried) saved FT
  article data. Use this as the ordered brute-force list when the myft.com
  endpoint is down or blocked. Add newly discovered stable sources here.
---

## Sources Ordered by Reliability

| Rank | Endpoint | Notes |
|------|----------|-------|
| 1 | `https://www.myft.com/myft/folder/saved-articles` | Private, requires auth; JSON response with headline/lead/meta |
| 2 | `https://www.ft.com/content/<ft-uuid>` | Individual articles; public page may show gated content |
| 3 | `https://www.ft.com` | Homepage; articles listed in carousels, not bookmarks |
| 4 | `https://ftr.andycshaw.com/` | Unofficial XML/RSS-like, partially paywalled |
| 5 | `https://ftr2.andycshaw.com/` | Alternate unofficial feed |
| 6 | `https://www.ft.com/rss` | Often returns 504; unreliable |
| 7 | `https://www.ft.com/rss_feeds.xml` | Returns 404 |

## Blocked / Unreachable in This Environment

| Endpoint | Failure Reason |
|----------|---------------|
| `https://www.myft.com/...` | 503 via proxy; DNS fails for `www.myft.com` without proxy |
| `https://ftr.andycshaw.com/` | 403 (blocked) |

## Cross-sources (Free, No Auth)

Use these to reconstruct context when ft.com / myft.com articles are
fully paywalled and only the teaser is retrievable:
- CNBC — news section
- Reuters — tech, energy, corporate
- BBC News
- Al Jazeera
- AP News
- TheStreet, Motley Fool (markets & biz)

## Rate limits

- `web_extract`: ~1 min per article if multi-fetched; ~20-30 s sequentially
- `curl` to ft.com: no known rate-limit on article pages
- myft.com API: unknown (private endpoint)

## Article URL sexp pattern

FT article URLs after myft.com listing redirect:
```
https://www.ft.com/content/<ft-uuid>
Example: https://www.ft.com/content/0c2adc44-5dcf-4273-943e-9899a1ce44ff
```
The `ft-uuid` is 36 chars, hex in 5-groups.
