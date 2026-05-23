---
name: x-digest
description: Fetch and summarize X/Twitter list feeds into a digest format. Uses the xapi.py wrapper for OAuth2-authenticated API calls.
version: 3.0.0
author: Hermes Agent 01
metadata:
  hermes:
    tags: [twitter, x, social-media, digest]
---

# x-digest — X/Twitter List Digest

Fetches tweets from X lists and formats them as a readable digest. Uses the OAuth2 token stored at `/opt/data/config/x-oauth2-tokens.json`.

## High Level Daily Objectives

1.) Minimize API costs
2.) Cache Indiviual Tweets for 30d
3.) Cache bookmarks and list-tweets for 30m
4.) Only Fetch Tweets within the relevant time bucket
5.) Group and Summarize using our research/unified-digest-themes/ skill - do not invent your pown
6.) Format the digest and actual links using current guidance
7.) Record New Jargon to Memory using our research/learn-jargon/  skill - skip if you can't find the skill
8.) Post to our preconfigured discord channel

## High Level Weekly Objectives
1.) Scan all cached tweets within the specified weekly time interval - should not need to hit the network
2.) Group and Summarize using our research/unified-digest-themes/ skill - do not invent your pown
3.) Format the digest and actual links using current guidance                                             
4.) Record New Jargon to Memory using our research/learn-jargon/  skill - skip if you can't find the skill
5.) Post to our preconfigured discord channel


## Prerequisites

- Working OAuth2 token in `/opt/data/config/x-oauth2-tokens.json`
- Python 3 (urllib, json — stdlib only, no pip deps)
- Skills: `research/unified-digest-themes` (grouping + summarization) — skip if not found
- Skills: `research/learn-jargon` (jargon recording) — skip if not found

## Wrapper API

`/opt/data/scripts/xapi.py` provides:

| Command | Description |
|---------|-------------|
| `list-tweets LIST_ID [--max N] [--json] [--links-only] [--fresh]` | Tweets from an X list |
| `search "query" [--max N] [--json] [--links-only]` | Search recent tweets |
| `bookmarks [--max N] [--json] [--links-only]` | User bookmarks |
| `user USERNAME` | Look up user by handle |
| `user-id USER_ID` | Look up user by ID |
| `timeline USER_ID [--max N]` | User timeline |
| `digest-validate FILE` | Validate URLs in a digest file (exit 0=pass, 1=fail) |
| `refresh-token` | Refresh OAuth2 bearer token (expires every 2h). Only needed for `--fresh` fetches. |

## Caching Strategy (API Cost Minimization)

Two-layer caching to balance freshness and API costs:

| Cache Layer | TTL | What It Stores | Purpose |
|-------------|-----|----------------|---------|
| List-tweets / bookmarks API responses | 30 minutes | Full API response for a list/bookmarks call | New posts appear quickly; repeated calls within 30m hit cache |
| Individual tweet data | 30 days | Tweet content, metrics, timestamps | Once fetched, tweet data is static — no need to re-fetch |

**Rules:**
- Daily cron runs do NOT use `--fresh` — the 30m TTL on list-tweets ensures new posts appear within 30m, and cached individual tweets persist for 30 days
- `--fresh` is reserved for manual/on-demand overrides: "I need the very latest right now"
- `refresh-token` is only needed before a `--fresh` fetch (token expires every 2h)
- Weekly runs filter cached tweets by time interval — no network calls needed
- If a fetch fails (network/auth error), fall back to any existing cache — stale content is better than no content

## Known Lists

| Name | List ID | Recommended Max |
|------|---------|-----------------|
| AI High Signal | 1585430245762441216 | 50 (100 with --all) |
| Concentrate | 207282755 | 50 (100 with --all) |
| High-Level Work Related | 204414139 | 50 (100 with --all) |

**Note:** For comprehensive digests, use `--max 100`. If timeout issues occur (common in headless environments), reduce to `--max 50-60` for reliable execution.

## Daily Digest Workflow

### Step 1: Fetch tweets within time bucket (last 24h)

Do NOT use `--fresh`. The 30m cache TTL means the X API is only hit once per 30 minutes — subsequent runs within that window reuse cached data.

```bash
# Full output for the LLM to read
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 100 --all > /tmp/digest_tweets.txt

# Links-only output — NEVER let the LLM touch this
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 100 --all --links-only > /tmp/digest_links.txt
```

After fetching, filter to only tweets from the last 24h (the relevant time bucket). Discard older tweets.

If API returns 401/403 on initial (cached) fetch:
1. Refresh token once: `python3 /opt/data/scripts/xapi.py refresh-token`
2. Retry with `--fresh`: `python3 /opt/data/scripts/xapi.py list-tweets <LIST_ID> --max 100 --all --fresh > /tmp/digest_tweets.txt`
3. The `--links-only` endpoint may still 401 even after a successful refresh — in this case, extract URLs from the full-text output programmatically (see `references/xapi-parsing.md`)
4. If the fresh fetch also fails, log the error and skip posting

### Step 2: Group and summarize using unified-digest-themes skill

Load the `unified-digest-themes` skill for theme-based grouping and summarization. If the skill does not exist, group manually by these common themes:

- Models & Benchmarks
- Developer Tools & Code Agents
- ML Research
- Infrastructure & Compute
- Community & Events
- Hot Takes & Discourse

Write a short paragraph per theme. Mention author handles. Skip pure RTs unless they amplify something notable.

### Step 3: Append programmatic links section

**CRITICAL: The Links section must be generated by Python, NOT by the LLM.**

Try to use the `--links-only` output from `/tmp/digest_links.txt` verbatim as the Links section. Do NOT rewrite, reorder, or reformat these URLs. The `--links-only` output is authoritative and guaranteed correct.

**If `--links-only` fails (401)**: Extract link URLs programmatically from the full-text output instead. See `references/xapi-parsing.md` for the output format and extraction pattern. Only use `https://x.com/i/status/NNNNN` canonical URLs — never rewrite or construct tweet URLs from scratch.

### Step 4: Validate before posting

```bash
python3 /opt/data/scripts/xapi.py digest-validate /tmp/digest_output.txt
```

If validation fails (exit code 1), fix the broken URLs before posting. If validation passes, post the digest.

### Step 5: Record new jargon

Load the `learn-jargon` skill. If it exists, pass new/interesting terms and definitions to memory. If it does not exist (not found), skip this step silently.

### Step 6: Log the run

Append a JSONL entry to `/opt/data/logs/digest-runs.jsonl`:

```json
{"ts": "ISO_TIMESTAMP", "status": "ok|error", "tweets_fetched": N, "tweets_filtered": N, "note": "brief description"}
```

### Step 7: Post

Deliver the digest to the preconfigured Discord channel.

## Weekly Digest Workflow

### Step 1: Scan cached tweets

Read from the existing xapi.py cache files. The 30-day TTL on individual tweets means all tweets from the past week are still in cache. Scan for tweets within the last 7 days.

Do NOT hit the X API. If insufficient cached data exists, fall back to a daily-style fresh fetch with `--fresh`.

### Step 2: Group and summarize (same as daily)

Load `unified-digest-themes` skill. Group by theme across the full week.

### Step 3: Append links (same as daily)

### Step 4: Validate (same as daily)

### Step 5: Record new jargon (same as daily)

### Step 6: Log the run (same as daily)

### Step 7: Post

## Format Preference (important)

User prefers Fun TEXT digests:
- Markdown headers (#) for sections
- Emoji section dividers for visual separation
- Bold (**) for emphasis
- Easy to read, conversational tone
- Simple date header, blank lines between sections
- Raw links section at the end, grouped by themes/sub-themes

## Primary API Interface

`/opt/data/scripts/xapi.py` is the primary way to call X APIs. Do NOT use `xurl --auth oauth2` — its config parser doesn't pick up manually-injected tokens. The wrapper reads tokens from `/opt/data/config/x-oauth2-tokens.json` directly.

## Pitfalls

- Token expires every 2 hours — only refresh when doing `--fresh` fetches. For normal cached runs, the token was valid when the cache was written.
- List endpoint max is 100 tweets per request, pagination via `pagination_token`
- Retweets show original author_id but the text includes `"RT @user:"` prefix
- Rate limits: 900/15min on most endpoints — 30m cache TTL keeps us well under limits
- Bookmarks endpoint requires actual user_id (e.g. `43469078`), NOT `me`. The wrapper handles this automatically.
- NEVER let the LLM construct or rewrite tweet URLs — always use `--links-only` output verbatim
- **`--links-only` endpoint may 401 when `--fresh` succeeds**: The `--links-only` endpoint can return 401 even after a successful token refresh that works for the regular list-tweets call. Workaround: extract URLs programmatically from the full-text output instead. See `references/xapi-parsing.md`.
- **Dual caching (2026-05-22)**: List-tweets/bookmarks API calls have a 30m TTL. Individual tweet data has a 30d TTL. The script handles both transparently. Cron jobs should NOT use `--fresh` — it defeats caching and increases API costs.
- If `digest-validate` fails with many broken URLs, consult `references/xapi-debugging.md` for common issues and fixes.
- For detailed caching architecture (CMD_TTL, cache key design, `--all` pagination field fix), consult `references/xapi-caching.md`.
- For raw output format parsing (when `--links-only` is unavailable), consult `references/xapi-parsing.md`.

## Fallback for API unavailability

When the X API is unavailable (e.g., 401/403 or network issues):
- Log the error with timestamp and status "error"
- If any cached data exists (even if slightly stale), use it with a note: "Based on cached data from [timestamp]"
- Do NOT post if no cached data exists at all
- Require manual intervention to resolve credentials
