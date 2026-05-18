# Parsing the arXiv Category Listings Page

## When to use

Use this technique when the arXiv REST API is unavailable — HTTP 429 rate limits,
Python `urllib` SSL errors (`SSLEOFError`), or environment-specific connectivity
issues. The listings pages are plain HTML and are reliably served by `curl`.

## URL patterns

| Page | URL |
|------|-----|
| New submissions (cs.CL) | `https://arxiv.org/list/cs.CL/new` |
| Recent submissions | `https://arxiv.org/list/cs.CL/recent` |
| Cross-lists | `https://arxiv.org/list/cs.CL/new#item59` |
| Any category | `https://arxiv.org/list/<cat>/new` |

Replace `cs.CL` with any arXiv category.

## HTML structure

Each paper appears as an `<a>` anchor whose `id` is the bare arXiv number
(e.g. `2605.13919`). Two occurrences of that ID exist in the document — the
second one is inside the `<a href="/abs/…">` link. The block surrounding the
second occurrence contains what you need:

```
<span class='descriptor'>Title:</span>   <span class='list-title mathjax'>  <vanilla title> </span>
<div class='list-authors'>   <a href="…?query=Lee,+K">Lee, K</a>  …
<div class='mathjax'>          ABSTRACT PARAGRAPH HERE            </p>
```

## Extraction strategy

1. **Collect all arXiv IDs**: `re.findall(r'id="(\d+\.\d+)"', html)` — deduplicate
   to get one entry per paper.
2. **Locate the paper block**: find the *second* occurrence of each ID and grab
   4000+ chars of surrounding context, or use a fixed-width split on `\[N]`
   markers from the numbered list.
3. **Parse title**: strip `class='descriptor'>Title:</span>` HTML wrapper and
   remove LaTeX delimiters (`\\[a-zA-Z]+\{.*?\}`).
4. **Parse authors**: extract all `query=Lastname,+F` URL params; sort and
   deduplicate.
5. **Parse abstract**: find `class='mathjax'>(.*?)</p>` and strip remaining
   HTML tags.
6. **Filter**: match `'large language model'` or `'large language models'`
   (case-insensitive) against the combined title + abstract text.

## Known quirks

- **Two `id="2605.13919"` occurrences per paper** — the first is at the top of
  the block (anchor header); the second is inside the link. Referencing the
  first occurrence gives you ~200 chars of title; referencing the second gives
  you authors and abstract.
- **LaTeX in titles**: some titles embed `\operatorname{…}`, `\mathcal{…}` etc.
  Strip with `re.sub(r'\\[a-zA-Z]+\{.*?\}', '', text)` before display.
- **XXE protection**: arXiv's HTML is straightforward; no special handling
  needed. Avoid over-parsing — you need just title, authors, and one paragraph.

## Verified results (this session)

On `cs.CL/new` (May 13 2026, 194 entries), the regex block parser identified
32 LLM-relevant papers. The top 5 by listing order (most-recent first) were
confirmed by fetching individual abstract pages via `web_extract`. All five
returned clean metadata with no API calls.
