---
name: news-digest
description: Build automated news digest pipelines from paywalled and public news sites. Covers ft.com saved-articles fallback (myft.com login wall → ft.com homepage scraping), web_extract truncation handling, article body extraction, author byline parsing, section-page URL harvesting, raw archive saving, and Signal-ready digest formatting. Load when building or running a scheduled news/bookmark digest cron job.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [news, digest, ft.com, cron, web-extraction, paywall, scraping]
---

# News Digest: Scheduled FT / News Aggregation Jobs

Class-level skill for building and maintaining automated news digest jobs that pull from publish-first news sites and format the result for messaging delivery (e.g. Signal).

## When to Load

- Setting up or fixing a cron job that fetches news article summaries
- Debugging a news digest job that suddenly stopped returning articles
- Adding a new news source to an existing digest pipeline
- Investigating paywall / login-block issues on news sites

---

## Architecture: Three-Tier Source Strategy

News sites sit on a spectrum from fully-open to auth-gated. A resilient digest job must work on all three tiers in order of availability.

```
TIER 1 — Authorised source (ideal)
  e.g. myft.com/myft/folder/saved-articles
  → Requires login cookie / auth header
  → If accessible: fetch article list → iterate → save raw → summarise

TIER 2 — Public section / topic page (fallback tier 1)
  e.g. ft.com/world, ft.com/markets, nytimes.com/section/world
  → No auth required, but URL structure differs from tier 1
  → Scrape article URLs from section page(s) → unique → fetch each

TIER 3 — Public homepage (last resort)
  e.g. ft.com, nytimes.com
  → Available without auth, but mix of lead stories + "load more" blobs
  → Scrape headline branches + section-page links as supplementary
```

**Rule:** Prefer tier 1 (bookmark list) when working; on failure, cascade down without manual intervention.

---

## Core Workflow

### Phase 1 — Attempt Tier 1 (Bookmark / Saved-Articles Page)

```python
from hermes_tools import web_extract

# myft.com saved articles (requires logged-in session)
r = web_extract(urls=["https://www.myft.com/myft/folder/saved-articles"])
```

**What 'blocked' looks like:**
```json
{"error": "Blocked: URL targets a private or internal network address"}
```
or DNS failure, HTTP 503, or redirect to login page. Check `r['results'][0]['error']`.

If blocked → skip to Phase 2. Do **not** retry this URL in the same session — no session state changes.

---

### Phase 2 — Harvest Article URLs from Section / Homepage Pages

When Tier 1 is unavailable, harvest fresh article URLs from the public site.

```python
import re

section_pages = [
    "https://www.ft.com/world",
    "https://www.ft.com/markets",
    "https://www.ft.com/europe",
]

all_article_urls = set()
for section_url in section_pages:
    r = web_extract(urls=[section_url])
    body = r['results'][0]['content']
    # FT article URLs: /content/ followed by a UUID
    urls = re.findall(r'https://www\.ft\.com/content/[a-f0-9\-]+', body)
    all_article_urls.update(urls)
```

**Deduplicate aggressively.** Section pages overlap heavily — the same article appears on homepage and section listings simultaneously. Use a `set`.

**Filter paywalled URLs before fetching:** test one candidate first:
```python
test = web_extract(urls=[candidate_url])
if "subscribe" in test['results'][0]['title'].lower():
    paywalled_urls.add(candidate_url)
```
Review the first title; if it says "Subscribe to read" or "Unlock the FT" it is paywalled. Skip it from the main article list — you can keep it in a `[PAYWALL]` note.

---

### Phase 3 — Fetch Article Bodies

**web_extract truncation:** `web_extract` caps results at ~5,000 chars per URL. For long articles this means the body text is incomplete — the tool reports the truncation in the tool result error field.

```python
# Safe pattern: loop over URL list, save immediately
for url in urls_to_fetch:
    r = web_extract(urls=[url])
    data = r['results'][0]
    raw = data['content']
    title = data['title']
    raw_content_path = save_raw(url, raw)  # see archive pattern below
```

If you need _more_ body than 5,000 chars: there is no workaround within `web_extract`. Two options:
1. Accept the truncated body for summaries; body quality is still sufficient for 2–3 sentence distillation
2. Use section pages to scrape article URLs rather than fetching individual bodies — the text snippets embedded in section pages often give enough topic coverage

**Paywall detection after fetch:** even after the title check, some articles only expose the first 30–50 words before a paywall. Check for these boiletplate markers in `raw`:
- `"Please correct the errors below"`
- `"Register for FT.com"`
- `"Unlock the"`
- `"This article contains"`
If present → treat as `[PAYWALL]` regardless of title.

---

### Phase 4 — Parse Metadata from Raw Text

FT.com embeds all article metadata inline. Use regex on the raw content string.

#### Date
```python
import re
date_m = re.search(r'Published\s+([A-Z][\w]+ \d{1,2} 20\d{2})', raw)
date = date_m.group(1) if date_m else ""
```

#### Comments count
```python
comments_m = re.search(r'\[(\d{1,3})\]\x28[^)]*comment', raw)
comments = comments_m.group(1) if comments_m else ""
```
`comments_m` is surrounded by the article's print/comment count link — the first `[N]` link that contains 'comment' in its href text.

#### Author names (the tricky part)
FT embeds author names as markdown links: `[Lauren Fedor](https://www.ft.com/lauren-fedor)`

**Pitfall:** category names also appear as links — `[Middle East war](url)`, `[European banks](url)`, etc. — and will appear first. These are NOT authors.

**Filter pattern: `category name vs person name`**

```python
CATEGORY_BLACKLIST = {
    'Middle East war', 'War in Ukraine', 'European banks', 'Oil & Gas industry',
    'EU defence', 'US gun violence', 'Bolivia', 'Chinese capital controls',
    'FT Magazine', 'Middle war', 'Middle East', 'Europe', 'Asia', 'World',
    'Markets', 'Companies', 'Finance', 'accessibility help', 'Skip to',
}

# Extract all [Name](url) links
all_links = re.findall(r'\[([^\]]+)\]\(https?://www\.ft\.com', raw)

# Filter: starts with capital letter, not in blacklist, looks like Firstname Lastname
filters_out = (
    lambda s: s.strip() not in CATEGORY_BLACKLIST
    and re.match(r'^[A-Z][a-z\']+\s+[A-Z][a-z]', s)
    and len(s) > 4 and not s.startswith('Access') and not s.startswith('Skip')
)
persons = list(dict.fromkeys(s for s in all_links if filters_out(s)))  # ordered unique
authors = ", ".join(persons[:5]) if persons else "FT"
```

Using `dict.fromkeys` preserves insertion order (Python 3.7+) and deduplicates.

Also strip trailing commas from byline-like patterns.

#### Body text
Strip navigation boilerplate and extract clean prose:
```python
SKIP_TOKENS = {
    '[#]', 'Millan', '© ', 'FT montage', 'AFP via', 'Bloomberg', 'Please correct',
    'Register for FT', 'Unlock the', 'Get instant', 'Manage your delivery',
    'Skip to', 'Accessibility help', 'current progress', 'By signing up',
    'help.ft.com', 'Andrew England in', 'in Washington', 'in London',  # location fragments
    'Middle East war', 'European banks', 'Oil & Gas industry',  # category noise
}

def extract_body(raw):
    lines = []
    for line in raw.split('\n'):
        s = line.strip()
        if len(s) < 30:
            continue
        if any(t.lower() in s.lower() for t in SKIP_TOKENS):
            continue
        # Strip markdown links to get prose
        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > 35 and clean not in lines:
            lines.append(clean)
    return ' '.join(lines[:10])
```

---

### Phase 5 — Save Raw Archives

Save per-article raw text and digest archive to a persistent directory:

```
~/.hermes/content/ft-raw/
  ├── 01-Trump-Iran-Hormuz-deal.md        (per-article raw)
  ├── 2026-05-24-digest.md                (daily digest archive)
  ├── 2026-05-17-digest.md
  └── ...
```

**Per-article filename pattern:** `NNN-slug.md` where NNN is a 2–3 digit sequence number. Slugify from the article URL UUID or title.

**Digest archive filename pattern:** `YYYY-MM-DD-digest.md`

**Raw file header:**
```markdown
# {Article Title}

URL: {url}
Date: {date}
Author(s): {authors}
Comments: {comments}

--- RAW ARTICLE TEXT ---

{raw content}
```

**Why:** Later sessions can re-read the raw archive to avoid redundant `web_extract` calls and can compare against the archive to detect new articles without re-fetching every URL.

---

### Phase 6 — Summarise and Format Digest (Signal-Ready)

One digest = one final text response emitted by the cron job, formatted for Signal (plain text, line breaks, no markdown headers):

```
📰 FT DAILY DIGEST — Sunday, May 24, 2026
============================================================

⚠️ SOURCE NOTE: myft.com (FT saved-articles page) is behind a login/paywall and
could not be accessed directly. Today's digest is compiled from the public ft.com
homepage instead. Full raw article text at ~/.hermes/content/ft-raw/.

─────────────────────────────────────────────────────────────

1. {Article Title}
   {Author(s)} · FT.com · {Date} · {N} comments

   {2–3 sentence summary}

─────────────────────────────────────────────────────────────

2. ...
```

**Summary style rules:**
- Lead with the news, not the URL
- 2–3 sentences; aimed at a generalist who skipped the article
- Note the angle / framing if it's opinion / analysis, embed the thesis
- Mention numeric specifics from the article when relevant (rates, quantities, dates)
- For paywalled items: add `[PAYWALL]` header with the teaser only

---

## Known Site-Specific Behaviours

### ft.com (The Financial Times)

| Feature | Behaviour |
|---------|-----------|
| myft.com (saved articles) | Requires active login; blocked without session cookies → HTTP 503 or DNS failure |
| ft.com homepage | Public, ~40,000 chars HTML; article links embed in `/content/{uuid}` URLs |
| Section pages | Same article URL pattern; useful for URL harvesting in tier 2 |
| `web_extract` | Capped at 5,000 chars; long articles truncated mid-body |
| Author embedding | Markdown links: `[Name](https://www.ft.com/author) in City`; byline block sits ~40–100 words in |
| Comment count | `[322]` link with `#comments-anchor`; first such `[N]` link is the comment count |
| Date pattern | `Published May 23 2026` — not consistently ISO format |

### Other Sites (Not Yet Tested)

> New sites should be added to this table when a digest job targeting them is created. See references/ft-com details.md for additional site notes.

---

## Cron Delivery Rules

- **Do not** use `send_message` or any messaging tool to deliver the digest — the cron job infrastructure handles delivery to the configured destination.
- **Do** emit the final formatted digest as a plain text response from the agent.
- **Do not** add "[SILENT]" unless there is genuinely nothing new to report. If an article list is empty but new articles you know about exist, still produce a "no new articles" digest, not [SILENT].
- The cron job delivery target is: read from `hermes cron status` or config to confirm destination type before formatting.

---

## When web_extract Truncates

`web_extract` will silently truncate at ~5000 chars for long articles. The tool result `content` field will be well below source length.

**Detection:**
```python
expected_len = len(data['content'])
actual_reported = actual_reported or sum(1 for ...)
```
There is no direct way to detect truncation programmatically. Workarounds:
1. **Accept truncated body** for summary distillation — sufficient quality for 2–3 sentence summaries when supplemented by homepage teasers
2. **Fetch section pages instead** — scraped headline + teaser often provides the article angle without needing the full body

---

## Common Pitfalls

1. **myft.com requires auth** — never retry the myft.com URL if the first call is blocked; escalate to tier 2 immediately
2. **Category names leak into author list** — capitalise on the `[Name](url)` markdown link pattern but filter against `CATEGORY_BLACKLIST`
3. **Multiple extraction attempts produce duplicate URL sets** — everywhere you fetch URLs, insert them into a `set()` before iterating
4. **Author date parsing fails on `in Washington/London`** — the `Published` date is outside the author link block; don't include author-location lines in date-regex scope
5. **browser_navigate (CDP WebSocket) fails on TLS for ft.com** — this is a known flaky path; prefer `web_extract` for ft.com content
6. **Template-check mismatch on inline scripts** — always write multi-line scripts to files via `write_file` then execute via `terminal`; large `execute_code` blocks can hit quoting and parsing issues

---

## References

- `references/ft-com-details.md` — ft.com site structure, URL patterns, known section pages, and date format notes
- `references/source-fallback-pattern.md` — documented examples of fallback cascades from myft.com to ft.com public pages
