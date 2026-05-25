# ft.com Site Details

## URL Patterns

| Content type | Pattern |
|---|---|
| Articles | `https://www.ft.com/content/{uuid}` |
| Section/World | `https://www.ft.com/world` |
| Section/Markets | `https://www.ft.com/markets` |
| Section/Europe | `https://www.ft.com/europe` |
| Company page | `https://www.ft.com/companies/{slug}` |

### UUID format (article IDs)
UUID segments separated by hyphens, hex chars only:
```
a27cc653-71ee-4668-8fcf-562fd7c9b93f
```
Regex: `[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}`

## Known Section Pages (Tier 2 URLs)

Use these for URL harvesting when myft.com (tier 1) is blocked:

- `https://www.ft.com/world`
- `https://www.ft.com/markets` — also contains `Global buyout funds`, `JPMorgan`, `China securities`
- `https://www.ft.com/europe`
- `https://www.ft.com/global-economy`

Fetch via `web_extract` and scrape with: `re.findall(r'https://www\.ft\.com/content/[a-f0-9\-]+', content)`

## Article Metadata Embedded in Page

### Title
Always present as `# {Title}` heading within the first 50 words of raw text.

### Published Date
```
Published May 23 2026
```
Pattern: `Published\s+[A-Z][\w]+ \d{1,2} 20[0-9]{2}`

Sometimes absent from article page full-body raw; fallback: extract from the article URL's component list HTML.

### Author Byline
Format in page body (detectable via markdown links):
```
[Lauren Fedor](https://www.ft.com/lauren-fedor) in Washington
[Andrew England](https://www.ft.com/andrew-england) in London
```
Multiple names connected by ` and ` or `,` appear on separate lines.

**Pitfall: category names appear as links FIRST.** Blacklist `('Middle East war','European banks','Oil & Gas industry','EU defence','Chinese capital controls','Bolivia','War in Ukraine','US gun violence')`.

### Comment Count
First `[N]` link whose parent text includes `comment` in its href ` fragment (`#comments-anchor`):
```
[322](url#comments-anchor "Jump to comments section")
```
Regex: `'\[(\d{1,3})\]\x28[^)]*comment'`

### Paywall Detection
First indicator of paywall in `web_extract` result:
- `"Subscribe to read"` in `data['title']`
- `"Unlock the"` in body first 200 chars
- `"Please correct the errors below and try again"` in body
- `"Get the most from The Financial Times"` repeated ≥ 3 times (template boiler attesting)

---

## Known Raw text Boilerplate to Strip

These strings always appear at the head of article pages and must be stripped from body prose:
- `[Accessibility help](https://www.ft.com/accessibility) [Skip to`
- `Get instant alerts for this topic`
- `Manage your delivery channels here`
- `Remove from myFT`
- `Current progress 0%` / `100%` (reading indicator, appears twice)
- `Register for FT.com`
- `Unlock the White House Watch newsletter for free`
- Share links: `[x](twitter) [facebook] [linkedin] [whatsapp] [Save]`
- Image captions: `© (source)` at end
- `You already have an account on ft.com`
- `By signing up for this email`

---

## Section Page Article Teasers

Section page body content includes two lines per article:
```
[!LINK-TEXT](url)
[!SUBHEADING](url)
```
Use this to harvest both article links and subheading teaser text without needing to fetch each article individually — efficient for preliminary topic understanding.

---

## web_extract Truncation Notes

| Metric | Value |
|---|---|
| Max raw per URL | ~5,000 chars (hard cap) |
| Divergence point | Body prose typically cut after ~500 chars of actual article text |
| No retry/expand mechanism | web_extract is a black-box http fetcher; no streaming body option |
| Workaround | Fetch section page for headline + teaser; use home page index for topic commands |

Unless you have a specific site requirement where the full body must be returned, work within the 5,000-char cap. 2–3 sentence summaries distilled from truncated content are still high-value. Trust that the truncated text still covers the article's lede/opening.
