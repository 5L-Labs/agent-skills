---
name: x-digest
description: Fetch and summarize X/Twitter list feeds into a digest format. Prefers Hermes v0.14+ built-in x_search tool (xAI-backed) when xAI credentials are configured; falls back to the xapi.py OAuth2 wrapper.
version: 3.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [twitter, x, social-media, digest]
    related_skills: [unified-digest-themes]
requires_env: [x_search_available]
---

# x-digest — X/Twitter List Digest

Fetches tweets from X lists and formats them as a readable digest. Uses the OAuth2 token stored at `/opt/data/config/x-oauth2-tokens.json`.

## Authentication — Two Paths

x-digest supports two authentication backends. **Prefer xAI when available** — it is faster, built into Hermes, and costs nothing extra if you have a SuperGrok subscription.

### Path A: xAI / x_search (preferred — Hermes v0.14+)

Uses Hermes' built-in `x_search` tool (backed by xAI's native X search via grok-4.20-reasoning). No custom scripts, no token refresh, no API credit costs.

**Setup:**
```bash
# Option 1: SuperGrok OAuth (free with subscription — recommended)
hermes auth add xai-oauth

# Option 2: xAI API key (per-token cost)
# Add to ~/.hermes/.env:
# XAI_API_KEY=your_key_here

# Enable the toolset
hermes tools enable x_search
```

**Caching note:** x_search results are auto-cached by xAI. For additional cost savings, cache full digests on disk at `/opt/data/cache/x-digest/` (30-day TTL).

### Path B: Legacy Twitter OAuth2 (fallback)

Uses the xapi.py wrapper with OAuth2 tokens at `/opt/data/config/x-oauth2-tokens.json`.

**Setup:** Tokens stored at `/opt/data/config/x-oauth2-tokens.json`. Token expires every 2 hours — Step 0 handles refresh.

### Prerequisites

- **For x_search**: Either SuperGrok OAuth (`hermes auth list` shows xai-oauth) or `XAI_API_KEY` in .env
- **For xapi.py fallback**: Working OAuth2 token in `/opt/data/config/x-oauth2-tokens.json`
- Python 3 (urllib, json — stdlib only, no pip deps for fallback)

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

## Digest Workflow (x_search preferred, xapi.py fallback)

### Step 0: Pre-flight — choose backend & check cache

Check which auth path is available:
1. If `x_search` toolset is enabled AND xAI credentials are configured (`hermes auth list` shows xai-oauth or `XAI_API_KEY` is set): use **x_search backend** (preferred).
2. If xAI not available but OAuth2 token exists at `/opt/data/config/x-oauth2-tokens.json`: use **xapi.py fallback**.
3. If neither is available: log error, skip posting, require manual auth.

For xapi.py fallback: always refresh the OAuth2 token before fetching. Token expires every 2 hours.

Regardless of backend: check if tweets are already cached on disk. If a fresh cache exists (less than 30 days old), use it instead of making API calls to reduce costs.

### Step 1: Fetch tweets

**x_search backend (preferred — use when available):**

The `x_search` tool is a first-class Hermes tool — do NOT use terminal/scripts for it. Call it naturally: search for tweets from the AI High Signal list handles, with date filtering for the current digest period. The tool handles auth, rate limits, and retries automatically.

```python
# Example: search for recent tweets from key accounts
# (use x_search tool in conversation, not via terminal)
```

For lists: if `x_search` supports handle-based filtering, use `allowed_x_handles` to scope to list members. If exact membership isn't available, do a broader search and post-filter.

When x_search is used, cache the structured JSON results at `/opt/data/cache/x-digest/YYYY/MM/DD/`.

**xapi.py fallback (when x_search unavailable):**

```bash
# Full output for the LLM to read
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 50 > /tmp/digest_tweets.txt

# Links-only output — NEVER let the LLM touch this
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 50 --links-only > /tmp/digest_links.txt
```

If API returns 401/403, log the auth error and skip automated posting. Notify operator to refresh credentials.

### Step 2: Write thematic summary

- Read ALL tweet content from `/tmp/digest_tweets.txt` — skip pure RTs unless they amplify something notable
- Group by THEME using the **unified cross-platform theme system** (canonical source: load the `unified-digest-themes` skill). The 7 themes and 5 AI & ML Research sub-themes are defined there — do not duplicate them inline.
- Write a short paragraph per theme summarizing what's discussed and why it matters. Mention author handles.

### Step 3: Append programmatic links section

**CRITICAL: The Links section must be generated by Python, NOT by the LLM.**

- If using **xapi.py fallback**: append contents of `/tmp/digest_links.txt` verbatim as the Links section. The `--links-only` output is authoritative and guaranteed correct.
- If using **x_search backend**: extract tweet URLs from the x_search JSON results programmatically via a Python script. Never let the LLM construct or rewrite tweet URLs.

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

**Preferred (v0.14+):** Use Hermes' built-in `x_search` tool — a first-class tool that appears in the tool list when xAI credentials are configured. No scripts, no manual token management. Enable with `hermes tools enable x_search`.

**Fallback:** `/opt/data/scripts/xapi.py` is the legacy way to call X APIs. Do NOT use `xurl --auth oauth2` — its config parser doesn't pick up manually-injected tokens. The wrapper reads tokens from `/opt/data/config/x-oauth2-tokens.json` directly.

## Cron Jobs

The `ai-high-signal-digest` cron job runs daily at 09:00 UTC, delivering thematic summaries to `discord:#x-tweet-digests`. The cron job loads `x-digest` + `unified-digest-themes` skills.

The cron job checks both auth backends and prefers x_search when available. See Step 0 for the decision logic.

Format preference: plain conversational summaries grouped by theme, with raw tweet links at the end. No fancy markdown, no emoji section dividers.

## x_search Configuration (optional)

Add to `~/.hermes/config.yaml` to customize x_search behavior:

```yaml
x_search:
  model: "grok-4.20-reasoning"     # cheaper: "grok-3.10-reasoning"
  timeout_seconds: 180
  retries: 2                        # number of retries on 5xx/transient errors
```

## Pitfalls

### x_search-specific
- x_search requires xAI credentials (SuperGrok OAuth or XAI_API_KEY) — check `hermes auth list` and `hermes tools list | grep x_search`
- If x_search is not available (no xAI creds), x-digest silently falls back to xapi.py — the cron job should log which backend it used
- x_search uses the grok-4.20-reasoning model by default — configure via `x_search.model` in config.yaml to save cost with a cheaper model
- x_search rate limits follow xAI API limits — handle 429 via retry with backoff
- x_search returns structured JSON with `answer`, `citations`, and `inline_citations` — use citations for tweet URL extraction

### xapi.py fallback-specific
- Token expires every 2 hours — refresh before every run (Step 0)
- List endpoint max is 100 tweets per request, pagination via `pagination_token`
- Retweets show original author_id but the text includes `"RT @user:"` prefix
- Rate limits: 900/15min for app-only, 900/15min for user auth on most endpoints
- Bookmarks endpoint requires actual user_id (e.g. `43469078`), NOT `me` — `/users/me/bookmarks` returns 400. The wrapper handles this automatically by reading user_id from the token file.

### General
- NEVER let the LLM construct or rewrite tweet URLs — always extract programmatically
- **Caching**: Responses are cached to disk for **30 days** to reduce API costs. See Step 0 for cache-check procedure.
- If `digest-validate` fails with many broken URLs, check the broken URLs manually — common causes are expired tweet IDs, suspended accounts, or rate-limit blocks on the validation endpoint.

## Fallback for API unavailability

When either backend is unavailable:

- **x_search fails**: retry with exponential backoff (2 retries default). If still failing, fall back to xapi.py if OAuth2 token is available. If also unavailable, log error and skip.
- **xapi.py fails (401/403)**: log the auth error and skip automated posting. Do NOT fall back to x_search (it was already tried first or not available).
- **Both backends unavailable**: use cached recent snapshot if available and acceptable. Require manual intervention to resolve credentials.

Log every run to `/opt/data/logs/digest-runs.jsonl` with the backend used so cost/comparison tracking is possible.
