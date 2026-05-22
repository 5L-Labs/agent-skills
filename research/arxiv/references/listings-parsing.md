# Parsing arXiv Listing Pages

## Goal

When the arXiv API is rate-limited or unavailable (common in cron / automated contexts), scrape the category new/recent listings page instead.

## URLs

| Page | URL |
|------|-----|
| New submissions (today) | `https://arxiv.org/list/cs.CL/new?skip=0&show=500` |
| Recent submissions | `https://arxiv.org/list/cs.CL/recent` |
| All (all categories) | `https://arxiv.org/list/cs.CL/new?skip=0&show=1000` |

Valid `show` values: 25, 50, 100, 250, 500, 1000, 2000.

Use `-A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"` to avoid 403s.

## HTML Structure

Each entry uses this structure:

```html
arXiv:2605.20191
<span class='descriptor'>Title:</span>
  Paper Title Here
<span class='descriptor'>Authors:</span>
<a href="...searchtype=author&amp;query=Last,+F,...">F Last</a>
```

## Parsing Snippet (save-then-parse pattern)

```python
import re

with open('/tmp/cscl_new.html') as f:
    content = f.read()

# Split by arXiv ID marker keeps title+authors+abstract together
parts = re.split(r'(arXiv:\d{4}\.\d{4,5})', content)
entries = []
for i in range(1, len(parts), 2):
    eid = parts[i].replace('arXiv:', '').strip()
    rest = parts[i + 1] if i + 1 < len(parts) else ''

    title_m = re.search(r"<span class='descriptor'>Title:</span>\n\s*(.*?)\n", rest, re.DOTALL)
    title = title_m.group(1).strip() if title_m else 'Unknown'

    author_links = re.findall(r"searchtype=author&amp;query=([^&\"',\.]+?),", rest)
    authors = ', '.join(a.replace('+', ' ') for a in author_links) if author_links else 'Unknown'

    entries.append((eid, title, authors))

# Filter by keyword
llm_kw = ['large language', 'llm', 'gpt', 'transformer language']
llm_entries = [(eid, t, a) for eid, t, a in entries
               if any(kw in t.lower() for kw in llm_kw)]
```

## Notes

- The listings page may be truncated by `web_extract`. Use `curl -o` to save the full HTML locally and parse from the file.
- Abstract snippets appear inline for each entry near the beginning of its `rest` chunk; scan for just the first paragraph if you need abstracts without visiting each `arxiv.org/abs/` page.
- Date info: the listing page section headers (e.g., `### Thu, 21 May 2026`) tell you what submission date all IDs in that section share.
