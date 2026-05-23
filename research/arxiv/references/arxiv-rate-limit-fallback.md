# arXiv API Rate-Limiting Fallback Patterns

## Session history
- **Date**: 2026-05-22 cron job
- **Symptom**: `export.arxiv.org/api/query` returned HTTP 429 immediately and consistently, even after sleeps of 30 s, 60 s, and 120 s between retries. Approx. 5 retries with varying user-agents all produced `Rate exceeded.` in a 14-byte response body.

## Effective fallback

1. **Scrape the category listings page** — stable, no auth, no rate-limit in practice:
   ```bash
   # pages of 50 entries; available skip offsets for cs.CL as of 2026-05-22
   https://arxiv.org/list/cs.CL/recent           # skip=0,  show=50
   https://arxiv.org/list/cs.CL/recent?skip=50&show=50
   https://arxiv.org/list/cs.CL/recent?skip=103&show=50
   ...
   https://arxiv.org/list/cs.CL/recent?skip=551&show=50
   ```
   Pages are HTML; parse with `web_extract` which returns structured content.

2. **Identify matching papers** from the listing (title already visible), then fetch individual abstract pages:
   ```bash
   web_extract(urls=[
     "https://arxiv.org/abs/2605.xxxxx",
     "https://arxiv.org/abs/2605.yyyyy",
   ])
   ```
   Abstract pages return clean HTML with title, authors, date, abstract, PDF link, categories.

3. **Combine listings pages**: If a listing page content is truncated (it often is — `web_extract` caps at 5 k chars), follow the "skip=N" pagination links until you have enough candidate papers, then parallel-fetch their abstract pages.

## Lessons

- `web_extract` abstracts for individual papers are fully reliable and not rate-limited for short sessions (< ~50 fetches).
- The listings page page size is 50 entries by default; use `?skip=N&show=100` to expand if you need to page through fast.
- For scheduled cron jobs, **set `maximum=100`** in `web_extract` options if available, so the full listing page returns without truncation.
- When the arXiv API is known-down, the listings page is a reliable secondary source for title/ID/metadata; abstract-level details still come from `web_extract(urls=["https://arxiv.org/abs/ID"])`.
- **Do not retry the API continuously** — even 120-second delays were insufficient in this session. Switch to the listings page immediately on the first 429.
