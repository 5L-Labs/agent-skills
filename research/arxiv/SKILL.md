---
name: arxiv
description: "Search arXiv papers by keyword, author, category, or ID."
version: 1.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Research, Arxiv, Papers, Academic, Science, API]
    related_skills: [ocr-and-documents]
---

# arXiv Research

Search and retrieve academic papers from arXiv via their free REST API or by scraping listing pages.

## ⚠️ Known Environment Issues

| Problem | Symptom | Workaround |
|---------|---------|------------|
| TLS failure to `export.arxiv.org` | `UNEXPECTED_EOF_WHILE_READING` from curl/python urllib | Use `web_search` + `web_extract` on `arxiv.org/abs/ID` pages |
| Script path | Skill docs say `python scripts/search_arxiv.py` | Call with full path: `python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py` |
| Script itself uses `urllib` | Hits same TLS failure as direct API calls | Treat script as reference/parser; primary access via web tools |
| `wget`, `ping` not installed | Commands not found | Use `curl` or `urllib` only |

**When the API is unreachable**, see the **Web-Scraping Fallback** section below.

## Quick Reference

| Action | Command |
|--------|---------|
| Search papers (API) | `curl "https://export.arxiv.org/api/query?search_query=all:QUERY&max_results=5"` |
| Get specific paper (API) | `curl "https://export.arxiv.org/api/query?id_list=2402.03300"` |
| Get specific paper (script) | `python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py --id 2402.03300` |
| Search by category (script) | `python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py --category cs.CL --max 10 --sort date` |
| Read abstract (web — works even when API is down) | `web_extract(urls=["https://arxiv.org/abs/2402.03300"])` |
| Read full paper (PDF → markdown) | `web_extract(urls=["https://arxiv.org/pdf/2402.03300"])` |

## Searching Papers

The API returns Atom XML. Parse with `grep`/`sed` or pipe through `python3` for clean output.

### Basic search

```bash
curl -s "https://export.arxiv.org/api/query?search_query=all:GRPO+reinforcement+learning&max_results=5"
```

### Clean output (parse XML to readable format)

```bash
curl -s "https://export.arxiv.org/api/query?search_query=all:GRPO+reinforcement+learning&max_results=5&sortBy=submittedDate&sortOrder=descending" | python3 -c "
import sys, xml.etree.ElementTree as ET
ns = {'a': 'http://www.w3.org/2005/Atom'}
root = ET.parse(sys.stdin).getroot()
for i, entry in enumerate(root.findall('a:entry', ns)):
    title = entry.find('a:title', ns).text.strip().replace('\n', ' ')
    arxiv_id = entry.find('a:id', ns).text.strip().split('/abs/')[-1]
    published = entry.find('a:published', ns).text[:10]
    authors = ', '.join(a.find('a:name', ns).text for a in entry.findall('a:author', ns))
    summary = entry.find('a:summary', ns).text.strip()[:200]
    cats = ', '.join(c.get('term') for c in entry.findall('a:category', ns))
    print(f'{i+1}. [{arxiv_id}] {title}')
    print(f'   Authors: {authors}')
    print(f'   Published: {published} | Categories: {cats}')
    print(f'   Abstract: {summary}...')
    print(f'   PDF: https://arxiv.org/pdf/{arxiv_id}')
    print()
"
```

## Search Query Syntax

| Prefix | Searches | Example |
|--------|----------|---------|
| `all:` | All fields | `all:transformer+attention` |
| `ti:` | Title | `ti:large+language+models` |
| `au:` | Author | `au:vaswani` |
| `abs:` | Abstract | `abs:reinforcement+learning` |
| `cat:` | Category | `cat:cs.AI` |
| `co:` | Comment | `co:accepted+NeurIPS` |

### Boolean operators

```
# AND (default when using +)
search_query=all:transformer+attention

# OR
search_query=all:GPT+OR+all:BERT

# AND NOT
search_query=all:language+model+ANDNOT+all:vision

# Exact phrase
search_query=ti:"chain+of+thought"

# Combined
search_query=au:hinton+AND+cat:cs.LG
```

## Sort and Pagination

| Parameter | Options |
|-----------|---------|
| `sortBy` | `relevance`, `lastUpdatedDate`, `submittedDate` |
| `sortOrder` | `ascending`, `descending` |
| `start` | Result offset (0-based) |
| `max_results` | Number of results (default 10, max 30000) |

```bash
# Latest 10 papers in cs.AI
curl -s "https://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=10"
```

## Fetching Specific Papers

```bash
# By arXiv ID
curl -s "https://export.arxiv.org/api/query?id_list=2402.03300"

# Multiple papers
curl -s "https://export.arxiv.org/api/query?id_list=2402.03300,2401.12345,2403.00001"
```

## BibTeX Generation

After fetching metadata for a paper, generate a BibTeX entry:

{% raw %}
```bash
curl -s "https://export.arxiv.org/api/query?id_list=1706.03762" | python3 -c "
import sys, xml.etree.ElementTree as ET
ns = {'a': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
root = ET.parse(sys.stdin).getroot()
entry = root.find('a:entry', ns)
if entry is None: sys.exit('Paper not found')
title = entry.find('a:title', ns).text.strip().replace('\n', ' ')
authors = ' and '.join(a.find('a:name', ns).text for a in entry.findall('a:author', ns))
year = entry.find('a:published', ns).text[:4]
raw_id = entry.find('a:id', ns).text.strip().split('/abs/')[-1]
cat = entry.find('arxiv:primary_category', ns)
primary = cat.get('term') if cat is not None else 'cs.LG'
last_name = entry.find('a:author', ns).find('a:name', ns).text.split()[-1]
print(f'@article{{{last_name}{year}_{raw_id.replace(\".\", \"\")},')
print(f'  title     = {{{title}}},')
print(f'  author    = {{{authors}}},')
print(f'  year      = {{{year}}},')
print(f'  eprint    = {{{raw_id}}},')
print(f'  archivePrefix = {{arXiv}},')
print(f'  primaryClass  = {{{primary}}},')
print(f'  url       = {{https://arxiv.org/abs/{raw_id}}}')
print('}')
"
```
{% endraw %}

## Reading Paper Content

After finding a paper, read it:

```
# Abstract page (fast, metadata + abstract)
web_extract(urls=["https://arxiv.org/abs/2402.03300"])

# Full paper (PDF → markdown via Firecrawl)
web_extract(urls=["https://arxiv.org/pdf/2402.03300"])
```

For local PDF processing, see the `ocr-and-documents` skill.

## Common Categories

| Category | Field |
|----------|-------|
| `cs.AI` | Artificial Intelligence |
| `cs.CL` | Computation and Language (NLP) |
| `cs.CV` | Computer Vision |
| `cs.LG` | Machine Learning |
| `cs.CR` | Cryptography and Security |
| `stat.ML` | Machine Learning (Statistics) |
| `math.OC` | Optimization and Control |
| `physics.comp-ph` | Computational Physics |

Full list: https://arxiv.org/category_taxonomy

## Helper Script

The `scripts/search_arxiv.py` script handles XML parsing and provides clean output. **Use the full path** — the script lives inside the skill directory:

```bash
python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py "GRPO reinforcement learning"
python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py "transformer attention" --max 10 --sort date
python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py --author "Yann LeCun" --max 5
python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py --category cs.AI --sort date --max 10
python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py --id 2402.03300
python3 /opt/hermes/skills/research/arxiv/scripts/search_arxiv.py --id 2402.03300,2401.12345
```

No dependencies except Python stdlib. ⚠️ The script calls `urllib.request.urlopen` directly — it will fail with TLS errors in environments where `export.arxiv.org` is blocked. See **Known Environment Issues** above.

---

## Semantic Scholar (Citations, Related Papers, Author Profiles)

arXiv doesn't provide citation data or recommendations. Use the **Semantic Scholar API** for that — free, no key needed for basic use (1 req/sec), returns JSON.

### Get paper details + citations

```bash
# By arXiv ID
curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.03300?fields=title,authors,citationCount,referenceCount,influentialCitationCount,year,abstract" | python3 -m json.tool

# By Semantic Scholar paper ID or DOI
curl -s "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1234/example?fields=title,citationCount"
```

### Get citations OF a paper (who cited it)

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.03300/citations?fields=title,authors,year,citationCount&limit=10" | python3 -m json.tool
```

### Get references FROM a paper (what it cites)

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.03300/references?fields=title,authors,year,citationCount&limit=10" | python3 -m json.tool
```

### Search papers (alternative to arXiv search, returns JSON)

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=GRPO+reinforcement+learning&limit=5&fields=title,authors,year,citationCount,externalIds" | python3 -m json.tool
```

### Get paper recommendations

```bash
curl -s -X POST "https://api.semanticscholar.org/recommendations/v1/papers/" \
  -H "Content-Type: application/json" \
  -d '{"positivePaperIds": ["arXiv:2402.03300"], "negativePaperIds": []}' | python3 -m json.tool
```

### Author profile

```bash
curl -s "https://api.semanticscholar.org/graph/v1/author/search?query=Yann+LeCun&fields=name,hIndex,citationCount,paperCount" | python3 -m json.tool
```

### Useful Semantic Scholar fields

`title`, `authors`, `year`, `abstract`, `citationCount`, `referenceCount`, `influentialCitationCount`, `isOpenAccess`, `openAccessPdf`, `fieldsOfStudy`, `publicationVenue`, `externalIds` (contains arXiv ID, DOI, etc.)

---

## Complete Research Workflow

1. **Discover**: `python scripts/search_arxiv.py "your topic" --sort date --max 10`
2. **Assess impact**: `curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:ID?fields=citationCount,influentialCitationCount"`
3. **Read abstract**: `web_extract(urls=["https://arxiv.org/abs/ID"])`
4. **Read full paper**: `web_extract(urls=["https://arxiv.org/pdf/ID"])`
5. **Find related work**: `curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:ID/references?fields=title,citationCount&limit=20"`
6. **Get recommendations**: POST to Semantic Scholar recommendations endpoint
7. **Track authors**: `curl -s "https://api.semanticscholar.org/graph/v1/author/search?query=NAME"`


### Troubleshooting API Rate Limits
If the arXiv API returns "Rate exceeded", use a `sleep` interval (at least 3-5 seconds between requests) or include a user-agent string to improve compliance with access policies:
```bash
curl -s -A "Mozilla/5.0" "https://export.arxiv.org/api/query?..."
```

### TLS / Complete API Failure
If `export.arxiv.org` is unreachable with `UNEXPECTED_EOF_WHILE_READING`, the API and `urllib`-based tools are blocked at the TLS layer. Use the web-scraping workflow below instead — `web_search` + `web_extract` bypass TLS restrictions because the web tool routes through a proxy.

## Web-Scraping Fallback (API Down)

When `export.arxiv.org` or `urllib` calls fail, use this pattern:

```python
# Step 1: Find candidate papers with web_search
web_search(query="large language model site:arxiv.org/abs cs.CL", limit=10)
# Returns: list of {url, title, description}

# Step 2: Get full abstracts with web_extract
web_extract(urls=[
    "https://arxiv.org/abs/2605.20170",
    "https://arxiv.org/abs/2605.20179",
])
# Returns: {title, content} per URL — content includes abstract text

# Step 3: For bulk listing discovery, scrape the category listing pages
web_extract(urls=["https://arxiv.org/list/cs.CL/recent?skip=0&show=100"])
# Lists recent papers with IDs, titles, and authors (no full abstracts)
```

### arXiv Listing Pages for Bulk Discovery

| URL | What it shows |
|-----|--------------|
| `https://arxiv.org/list/cs.CL/new` | Papers submitted today (split by section: new / cross-lists / replacements) |
| `https://arxiv.org/list/cs.CL/recent` | Last few days of submissions, paginated |
| `https://arxiv.org/list/cs.CL/current` | All papers in the current month, paginated |
| `https://arxiv.org/list/cs.CL/2026-05` | All papers in a specific month |

Use `?skip=N&show=100` to paginate (0-based `skip`, up to 2000 entries). The listing page shows titles/authors/categories but not full abstracts — extract paper IDs from `arXiv:NNNN.NNNNN` links, then call `web_extract` on each `https://arxiv.org/abs/ID` for the full abstract.

### Finding Papers by Keyword in Listings

Listing pages don't support server-side keyword search. Options:
1. **`web_search` with site filter**: `site:arxiv.org/abs cs.CL "large language model" 2026`
2. **Scan listing page titles manually**: pull the listing with `web_extract`, then grep titles for your term
3. **Combine**: search for `site:arxiv.org/abs cs.CL "exact phrase"` to get paper IDs directly from search index


| API | Rate | Auth |
|-----|------|------|
| arXiv | ~1 req / 3 seconds | None needed |
| Semantic Scholar | 1 req / second | None (100/sec with API key) |

## Notes

- arXiv returns Atom XML — use the helper script or parsing snippet for clean output
- Semantic Scholar returns JSON — pipe through `python3 -m json.tool` for readability
- arXiv IDs: old format (`hep-th/0601001`) vs new (`2402.03300`)
- PDF: `https://arxiv.org/pdf/{id}` — Abstract: `https://arxiv.org/abs/{id}`
- HTML (when available): `https://arxiv.org/html/{id}`
- For local PDF processing, see the `ocr-and-documents` skill

## ID Versioning

- `arxiv.org/abs/1706.03762` always resolves to the **latest** version
- `arxiv.org/abs/1706.03762v1` points to a **specific** immutable version
- When generating citations, preserve the version suffix you actually read to prevent citation drift (a later version may substantially change content)
- The API `<id>` field returns the versioned URL (e.g., `http://arxiv.org/abs/1706.03762v7`)

## Withdrawn Papers

Papers can be withdrawn after submission. When this happens:
- The `<summary>` field contains a withdrawal notice (look for "withdrawn" or "retracted")
- Metadata fields may be incomplete
- Always check the summary before treating a result as a valid paper
