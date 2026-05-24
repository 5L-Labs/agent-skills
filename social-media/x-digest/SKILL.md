---
name: x-digest
description: Fetch and summarize X/Twitter list feeds into a digest format. Uses the xapi.py wrapper for OAuth2-authenticated API calls. After fetching, logs detected jargon terms via the jargon skill.
version: 3.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [twitter, x, social-media, digest]
    related_skills: [unified-digest-themes, jargon]
---

# x-digest — X/Twitter List Digest

Fetches tweets from X lists and formats them as a readable digest. Uses the OAuth2 token stored at `/opt/data/config/x-oauth2-tokens.json`.

## Prerequisites

- Working OAuth2 token in `/opt/data/config/x-oauth2-tokens.json`
- Python 3 (urllib, json — stdlib only, no pip deps)

## Quick Start

```bash
# Fetch latest from AI High Signal list
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 20

# Fetch bookmarks
python3 /opt/data/scripts/xapi.py bookmarks --max 10

# Search
python3 /opt/data/scripts/xapi.py search "AI agents" --max 10

# JSON output for programmatic use
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 20 --json

# Links-only output (for appending to digests)
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 20 --links-only

# Validate a digest for broken URLs
python3 /opt/data/scripts/xapi.py digest-validate /path/to/digest.txt
```

## Wrapper API

`/opt/data/scripts/xapi.py` provides:

| Command | Description |
|---------|-------------|
| `list-tweets LIST_ID [--max N] [--json] [--links-only]` | Tweets from an X list |
| `search "query" [--max N] [--json] [--links-only]` | Search recent tweets |
| `bookmarks [--max N] [--json] [--links-only]` | User bookmarks |
| `user USERNAME` | Look up user by handle |
| `user-id USER_ID` | Look up user by ID |
| `timeline USER_ID [--max N]` | User timeline |
| `digest-validate FILE` | Validate URLs in a digest file (exit 0=pass, 1=fail) |

## Quick Start

```bash
# Fetch latest from AI High Signal list (comprehensive)
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 50

# Fetch ALL tweets from the list (multiple pages)
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 100 --all

# Fetch bookmarks
python3 /opt/data/scripts/xapi.py bookmarks --max 10

# Search
python3 /opt/data/scripts/xapi.py search "AI agents" --max 10

# JSON output for programmatic use
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 50 --json

# Links-only output (for appending to digests)
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 50 --links-only
```

## Known Lists

| Name | List ID | Recommended Max |
|------|---------|-----------------|
| AI High Signal | 1585430245762441216 | 50 (100 with --all) |
| Concentrate | 207282755 | 50 (100 with --all) |
| High-Level Work Related | 204414139 | 50 (100 with --all) |

**Note:** For comprehensive digests, use `--max 100`. If timeout issues occur (common in headless environments), reduce to `--max 50-60` for reliable execution.

## Cost Optimization

Tweet fetching has two cost layers — X API calls (per-request rate limits/plan quota) and LLM inference tokens (processing tweet content into summaries). Both scale with `--max` and pagination.

### Minimize X API Calls

1. **Prefer cache over fresh fetches.** xapi.py caches list-tweets for 30 minutes by default. For a once-daily cron (09:00 UTC), this means every run makes fresh API calls. **Extend the cache TTL** in xapi.py (`CMD_TTL` dict, line 36-43) to 86400 (24h) so daily runs read yesterday's cache:
   ```python
   CMD_TTL = {
       "list-tweets": 86400,   # 24h — daily cron doesn't need 30min freshness
       "bookmarks": 1800,
       "search": 2592000,
       "user": 2592000,
       "user-id": 2592000,
       "timeline": 2592000,
   }
   ```
2. **Avoid `--all` for routine runs.** `--all` paginates through every page (3-4 API calls for 300+ tweets). For daily digests, a single page of 50-100 tweets is sufficient. Reserve `--all` for first-time setup or when explicitly requested.
3. **Use `--fresh` sparingly.** When you absolutely need up-to-the-minute data, pass `--fresh` to bypass cache. Never use `--fresh` in cron jobs.
4. **Cap `--max` at 50-60 for daily runs.** 50 tweets = 1 API call vs 100 tweets = 1-2 API calls. Also reduces LLM token burn (~50 fewer tweets to read).

See `references/caching.md` for full cache TTL documentation and tuning guidance.

### Dual Auth: x_search (preferred) vs xapi.py (fallback)

Two auth paths exist, tried in preference order. The key difference is cost — `x_search` collapses fetch + summarize into one xAI API call, while xapi.py makes separate X API calls + LLM inference for the summary.

| Aspect | `x_search` (xAI) | `xapi.py` (X API) |
|--------|-------------------|-------------------|
| Auth | `XAI_API_KEY` or SuperGrok OAuth | OAuth2 bearer token |
| Setup | `hermes tools enable x_search` | Token at `/opt/data/config/x-oauth2-tokens.json` |
| Output | Prose summary + inline tweet URLs | Raw tweet JSON (author, text, metrics) |
| LLM cost | Included in xAI call (grok summarizes) | Separate — need LLM to read raw tweets + write summary |
| API cost | ~$0.10/call (xAI credits) | Free tier: 1500 tweets/mo; Basic: $100/mo for 10K |
| Daily digest cost | $0.10-0.20 (1-2 calls) | $0.50-5.00 (API quota + LLM tokens for 50-300 tweets) |

**Preference order:** `x_search` (cheaper, single step) → `xapi.py` OAuth2 (fallback).

### Setting up x_search

1. **Enable the toolset:** `hermes tools enable x_search` (takes effect on `/reset`)
2. **Provide credentials** (one of):
   - `XAI_API_KEY` in `~/.hermes/.env` (paid xAI API key)
   - `hermes auth add xai-oauth` for SuperGrok subscription (device code OAuth flow)
3. **Fund the account:** xAI account needs credits at https://console.x.ai. Without them, the API returns 403.

### Using x_search

The tool lives at `/opt/hermes/tools/x_search_tool.py`. Function signature:

```python
def x_search_tool(
    query: str,
    allowed_x_handles: Optional[List[str]] = None,  # Only from these handles
    excluded_x_handles: Optional[List[str]] = None,  # Exclude these handles
    from_date: str = "",                              # ISO date, start
    to_date: str = "",                                # ISO date, end
    enable_image_understanding: bool = False,
    enable_video_understanding: bool = False,
) -> str:  # Returns JSON string
```

Response format:

```json
{
  "success": true,
  "answer": "Prose summary with inline citations...",
  "inline_citations": [
    {"url": "https://x.com/user/status/123", "title": "1", ...}
  ]
}
```

**Key difference from xapi.py:** x_search returns a pre-written AI summary with weaved-in tweet URLs — it doesn't return raw tweet objects. There's no separate "fetch raw tweets" step; the grok model reads and summarizes in one pass. This means:
- No `--links-only` file needed — inline_citations provides the URLs
- No separate LLM summary step — the `answer` field IS the summary
- No `--max` parameter — the model decides how many tweets to include
- Use `allowed_x_handles` to scope results to specific handles (like a list's members)

### Query patterns for digests

For a daily digest from a known set of handles:

```python
from tools.x_search_tool import x_search_tool
import json

result = x_search_tool(
    query="latest posts about AI research and tools",
    allowed_x_handles=["handle1", "handle2", "handle3"],
)
parsed = json.loads(result)
summary = parsed["answer"]
citations = parsed["inline_citations"]
```

For a time-bound daily digest:

```python
from datetime import datetime, timezone, timedelta
yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
result = x_search_tool(
    query="AI agent posts",
    allowed_x_handles=[...],
    from_date=yesterday,
    to_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
)
```

The `answer` text already contains inline citation markers like `[[1]](url)`. For the digest output, use the `answer` as the prose body and append the inline_citations as a link list at the bottom, following the safe-links pattern (never let the LLM rewrite URLs).

See `references/x_search_tool.md` for the full API reference and troubleshooting.

## Digest Workflow (hardened + fallback for API issues)

Two workflows exist depending on which auth path is available. Try `x_search` first (cheaper, single step), fall back to `xapi.py` OAuth2.

### A) x_search workflow (preferred — cheaper, single pass)

1. **Call x_search_tool** with handles from the target list and a query scoped to the digest timeframe.
2. **Parse the response:** extract `answer` (the prose summary with inline citations) and `inline_citations` (tweet URLs).
3. **Format the digest:** use the `answer` text as the thematic body. Append the `inline_citations` URLs as a links section — never let the LLM rewrite these URLs.
4. **Post** to the digest destination.
5. **Log the run** (Step 5 below).

No separate fetch, summary, or validation steps needed — x_search does all of that in one API call. The model handles thematic grouping internally.

### B) xapi.py workflow (fallback — more expensive, multi-step)

### Step 0: Pre-flight — refresh token & check cache

Always refresh the OAuth2 token before fetching tweets. Token expires every 2 hours.

If refresh fails (network/invalid tokens), fall back to locally cached recent tweets or mark task as requiring manual auth. Do NOT proceed with stale/missing data if freshness is required.

**Cache check:** xapi.py caches responses per-command with different TTLs (list-tweets: 30 min, search/user: 30 days). Check the cache first — if a valid entry exists (within its TTL), use it instead of making an API call. For daily cron runs, the default 30-min TTL for list-tweets means every run fetches fresh; consider extending it (see Cost Optimization section). Use `--fresh` to bypass cache when up-to-the-minute data is required.

Dual auth: prefer the Hermes built-in `x_search` tool when available (no per-call X API quota cost). Fall back to xapi.py OAuth2.

### Step 1: Fetch tweets (full + links-only)

```bash
# Full output for the LLM to read
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 50 > /tmp/digest_tweets.txt

# Links-only output — NEVER let the LLM touch this
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 50 --links-only > /tmp/digest_links.txt
```

If API returns 401/403, log the auth error and skip automated posting. Notify operator to refresh credentials.

### Step 1.5: Log jargon from raw tweets

After fetching tweets, run jargon classification on the raw tweet text to build the jargon registry.

```bash
# Classify jargon from the fetched tweet content (uses local qwen2.5:7b, ~10s)
python3 /opt/data/skills/research/jargon/scripts/ingest.py \
  --file /tmp/digest_tweets.txt \
  --source "X:AI High Signal" \
  --max-chars 4000
```

This updates `jargon-registry.json` with any new jargon terms found, their themes, and plainspeak translations at all 4 sophistication levels. The default model (qwen2.5:7b) classifies in ~10s. For deeper analysis, add `--heavy` to use the 27B model (slower, ~5-10 min).

Failures in this step should NOT block the digest itself — it's auxiliary logging. Wrap in a try/catch or run as background.

See the `jargon` skill (research/jargon) for details, decode, and encode tools.

### Step 2: Write thematic summary

- Read ALL tweet content from `/tmp/digest_tweets.txt` — skip pure RTs unless they amplify something notable
- Group by THEME using the **unified cross-platform theme system** (canonical source: load the `unified-digest-themes` skill). The 7 themes and 5 AI & ML Research sub-themes are defined there — do not duplicate them inline.
- Write a short paragraph per theme summarizing what's discussed and why it matters. Mention author handles.

### Step 3: Append programmatic links section

**CRITICAL: The Links section must be generated by Python, NOT by the LLM.**

After writing the prose, append the contents of `/tmp/digest_links.txt` verbatim as the Links section. Do NOT rewrite, reorder, or reformat these URLs. The `--links-only` output is authoritative and guaranteed correct.

### Step 4: Validate before posting

```bash
# Write your full digest to a temp file, then validate
python3 /opt/data/scripts/xapi.py digest-validate /tmp/digest_output.txt
```

If validation fails (exit code 1), fix the broken URLs before posting. If validation passes, post the digest.

### Step 5: Log the run

Append a JSONL entry to `/opt/data/logs/digest-runs.jsonl`:

```json
{"ts": "ISO_TIMESTAMP", "status": "ok|broken|error", "urls_total": N, "urls_valid": N, "urls_broken": N, "note": "brief description"}
```

This enables success rate tracking over time.

### Format Preference (important)

User prefers PLAIN TEXT digests:
- No markdown headers (#)
- No emoji section dividers (━━━━)
- No bold (**)
- Simple date header, blank lines between sections
- Conversational tone, not press-release
- Raw links section at the end for clicking through

## Primary API Interface

`/opt/data/scripts/xapi.py` is the primary way to call X APIs. Do NOT use `xurl --auth oauth2` — its config parser doesn't pick up manually-injected tokens. The wrapper reads tokens from `/opt/data/config/x-oauth2-tokens.json` directly.

## Cron Jobs

The `ai-high-signal-digest` cron job runs daily at 09:00 UTC, delivering thematic summaries to `discord:#x-tweet-digests`.

Format preference: plain conversational summaries grouped by theme, with raw tweet links at the end. No fancy markdown, no emoji section dividers.

## Pitfalls

### x_search-specific

- **x_search requires funded xAI account.** API returns 403 if the xAI team has no credits. Fund at https://console.x.ai.
- **No raw tweet data from x_search.** The tool returns a pre-written summary, not raw JSON. Cannot extract metrics, timestamps, or full tweet text. Use xapi.py for programmatic analysis.
- **x_search has no `--max` control.** The model decides how many tweets to include. Can't target an exact tweet count.
- **Handles, not list IDs.** `allowed_x_handles` takes @handles. Can't pass an X list ID directly.
- **`allowed_x_handles` and `excluded_x_handles` are mutually exclusive.** Passing both returns an error.
- **No caching.** Every x_search call is a fresh API request. Unlike xapi.py, there's no disk cache.
- **Handles must be bare @names.** Strip the leading `@` — the tool does this automatically but be aware that `@user` and `user` are equivalent.

### xapi.py-specific

- Token expires every 2 hours — refresh before every run (Step 0)
- List endpoint max is 100 tweets per request, pagination via `pagination_token`
- Retweets show original author_id but the text includes `"RT @user:"` prefix
- Rate limits: 900/15min for app-only, 900/15min for user auth on most endpoints
- Bookmarks endpoint requires actual user_id (e.g. `43469078`), NOT `me` — `/users/me/bookmarks` returns 400. The wrapper handles this automatically by reading user_id from the token file.
- NEVER let the LLM construct or rewrite tweet URLs — always use `--links-only` output verbatim
- **Cache TTL mismatch**: Default list-tweets TTL is 30 min, but the cron runs daily. Every cron run fetches fresh API data. Extend to 24h in xapi.py to avoid redundant calls. See `references/caching.md`.
- **`--all` is expensive**: Paginating all pages makes 3-4 API calls per run and feeds 300+ tweets to the LLM. Stick to `--max 50` (no `--all`) for routine daily digests.
- **`--fresh` never caches**: Using `--fresh` bypasses disk cache entirely. Never use in cron jobs — it doubles API spend.
- If `digest-validate` fails with many broken URLs, consult `references/xapi-debugging.md` for common issues and fixes.
- **Jargon classification**: the ingest step (Step 1.5) uses local qwen2.5:7b by default (~10s). The `--heavy` flag switches to qwen3.6:27b (CPU-only, ~5-10 min). Failures here should not block the digest.
- **Themes canonical source**: always load `unified-digest-themes` skill at the start of a digest session. Do not rely on inlined theme lists — they drift.

## Fallback for API unavailability

When the X API is unavailable (e.g., 401/403 or network issues):
- Log the error with timestamp and status "error"
- Do NOT post an automated digest
- Optionally use a cached/recent snapshot if acceptable to the user
- Require manual intervention to resolve credentials or accept a delayed digest
