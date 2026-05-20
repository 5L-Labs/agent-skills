# arxiv skill — session notes: TLS failure & ar5iv fallback

## Environment constraint (2026-05-19)

`export.arxiv.org`, `arxiv.org`, and `api.semanticscholar.org` all fail with:
```
SSL: UNEXPECTED_EOF_WHILE_READING
```
curl return code 35 on all HTTPS connections to those hosts.  
`github.com`, `google.com`, `httpbin.org` succeed — DNS works, the
failure is specific to those hosts.

## Workaround confirmed working

- `web_search` + `web_extract` on `ar5iv.org` successfully fetched full paper
  abstracts for 5 consecutive papers (2605.15613, 2605.11744, 2605.09063,
  2605.05676, 2605.03299).
- Use `web_search(query="site:arxiv.org cs.CL \"large language model\" 2026")`
  to discover IDs when the API is blocked.
- Read the abstract with `https://ar5iv.org/html/{id}v1` — omit the `v1`
  suffix if reading the latest version.

## Newspaper listing pages

`https://arxiv.org/list/cs.CL/YYYY-MM?skip=N&show=500` also returns 500-long
paginated listings in the browse format. Worth a try for broad discovery
before individual lookups.
