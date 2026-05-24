# x_search Tool Reference

The `x_search` tool is Hermes' built-in interface to xAI's Responses API with the `x_search` tool enabled. It reads tweets via xAI's infrastructure and returns a prose summary with inline citations — no raw tweet JSON.

## Location

- Tool source: `/opt/hermes/tools/x_search_tool.py`
- Credential resolver: `/opt/hermes/tools/xai_http.py`
- Default model: `grok-4.20-reasoning`
- API endpoint: `https://api.x.ai/v1/responses`

## Enabling

```bash
hermes tools enable x_search
# Takes effect after /reset (new session)
```

## Credential Resolution Order

1. SuperGrok OAuth (`hermes auth add xai-oauth` — device code flow)
2. `resolve_xai_http_credentials()` (auto-refreshes OAuth access token)
3. `XAI_API_KEY` from `~/.hermes/.env` or process environment

The registered `check_fn` returns `False` if none of these paths yield a usable bearer token.

## Function Signature

```python
def x_search_tool(
    query: str,                                    # Required. Natural language search.
    allowed_x_handles: Optional[List[str]] = None,  # Max 10 handles. Scopes results.
    excluded_x_handles: Optional[List[str]] = None,  # Max 10 handles. Filters out.
    from_date: str = "",                            # ISO 8601 date, inclusive start.
    to_date: str = "",                              # ISO 8601 date, inclusive end.
    enable_image_understanding: bool = False,        # Grok sees image attachments.
    enable_video_understanding: bool = False,        # Grok sees video attachments.
) -> str:  # JSON-encoded response
```

Constraints:
- `allowed_x_handles` and `excluded_x_handles` are mutually exclusive (raises tool_error)
- Handles strip leading `@` automatically
- Max 10 handles per filter
- query must be non-empty

## Response Format

### Success

```json
{
  "success": true,
  "provider": "xai",
  "credential_source": "xai",
  "tool": "x_search",
  "model": "grok-4.20-reasoning",
  "query": "the original query",
  "answer": "Prose summary with inline citations like [[1]](https://x.com/user/status/123)...",
  "citations": [],
  "inline_citations": [
    {"url": "https://x.com/user/status/123", "title": "1", "start_index": 0, "end_index": 61},
    {"url": "https://x.com/user/status/456", "title": "2", "start_index": 300, "end_index": 361}
  ]
}
```

- `answer`: The summary text. Contains markdown citation markers `[[N]](url)` inline.
- `inline_citations`: Array of URL + position. Use these for the safe links section.
- `model`: Configurable via `x_search.model` in config.yaml.

### Error

```json
{
  "success": false,
  "error": "error message string",
  "tool": "x_search"
}
```

Common error codes:
- `403`: xAI account has no credits. Fund at https://console.x.ai.
- `401`: Token expired or invalid. Re-auth with `hermes auth add xai-oauth`.
- No credentials: Run `hermes auth add xai-oauth` or set `XAI_API_KEY`.

## Cost

- ~$0.10 per call (xAI API credits, varies by model and output length)
- Each call collapses: X tweet reading + summary generation
- Daily digest (1-2 calls): ~$0.10-0.20
- Compare to xapi.py path: $0.50-5.00 per digest (X API quota + LLM inference on raw tweets)

The `x_search` tool is **not a direct replacement** for `xapi.py` — it returns a summary, not raw data. Use it when:
- You want a ready-to-read digest with inline citations
- Cost minimization matters more than raw tweet access
- The query scope is well-defined (handles, dates)

Use `xapi.py` when:
- You need full tweet text, metrics (likes/RTs), and timestamps
- You're doing programmatic analysis or jargon classification on raw tweets
- You need precise control over tweet count and pagination

## Pitfalls

- **No `--max` parameter**: The model decides how many tweets to include. Cannot control output length.
- **No raw tweet data**: Only the summary text + citation URLs. Cannot extract metrics, timestamps, or full text.
- **Handles are NOT list IDs**: `allowed_x_handles` takes @handles, not X list IDs. To scope to a list's members, you need to know their handles.
- **From_date/to_date are inclusive**: Both dates are inclusive. If you set `from_date=today`, you get today's tweets.
- **DTO (date-time offset)**: The xAI API internally uses UTC for date filtering.
- **Mutual exclusion**: `allowed_x_handles` + `excluded_x_handles` together returns an error. Use one or the other.
- **Grok model cost**: The default `grok-4.20-reasoning` is a reasoning model — it consumes thinking tokens before generating the answer. This is included in the ~$0.10/call figure but is worth noting for cost prediction.
- **No cache**: Unlike xapi.py, the x_search tool does not cache responses. Every call is a fresh API request.