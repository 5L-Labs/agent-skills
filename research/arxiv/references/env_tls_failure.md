# TLS Failure to export.arxiv.org — Session Notes

## Symptom
All `urllib`, `curl`, and `wget` calls to `https://export.arxiv.org/api/query` and `https://arxiv.org/list/...` fail with:
```
TLS connect error: error:0A000126:SSL routines::unexpected eof while reading
```

Python `urllib.request.urlopen` raises:
```
ssl.SSLError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1029)
```

## What still works
- `web_search()` — routes through Hermes web proxy
- `web_extract(urls=[...])` — routes through Hermes web proxy
- `browser_navigate` — **also failed** with the same TLS error

## Confirmed workaround pattern (May 2026)

```python
# 1. Find paper IDs via search
web_search(query="site:arxiv.org/abs cs.CL large language model", limit=10)

# 2. Extract abstracts
web_extract(urls=[
    "https://arxiv.org/abs/2605.20170",
    "https://arxiv.org/abs/2605.20179",
])

# 3. Bulk listing scrape for recent papers in a category
web_extract(urls=["https://arxiv.org/list/cs.CL/recent?skip=0&show=100"])
```

## Listing page pagination
ArXiv listing pages accept `?skip=N&show=100` where:
- `skip` = 0-based page offset
- `show` = entries per page (max 2000)
- `/new` = today's submissions  
- `/recent` = last few days
- `/current` = full current month
- `/current?skip=50&show=100` = page 2 of the month (0-based, so skip 50 gets items 51–150)

## Script path
The `search_arxiv.py` helper script is located at:
`/opt/hermes/skills/research/arxiv/scripts/search_arxiv.py`
Not at `/opt/data/scripts/search_arxiv.py` as earlier skill drafts suggested.
