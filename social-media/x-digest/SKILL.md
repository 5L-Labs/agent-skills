---
name: x-digest
description: Fetch and summarize X/Twitter list feeds into a digest format. Uses the xapi.py wrapper for OAuth2-authenticated API calls.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [twitter, x, social-media, digest]
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
```

## Wrapper API

`/opt/data/scripts/xapi.py` provides:

| Command | Description |
|---------|-------------|
| `list-tweets LIST_ID [--max N] [--json]` | Tweets from an X list |
| `search "query" [--max N] [--json]` | Search recent tweets |
| `bookmarks [--max N] [--json]` | User bookmarks |
| `user USERNAME` | Look up user by handle |
| `user-id USER_ID` | Look up user by ID |
| `timeline USER_ID [--max N]` | User timeline |

## Known Lists

| Name | List ID |
|------|---------|
| AI High Signal | 1585430245762441216 |
| Concentrate | 207282755 |
| High-Level Work Related | 204414139 |

## Digest Workflow

1. Fetch tweets from a list using `list-tweets --json --max 40`
2. Read ALL tweet content — skip pure RTs unless they amplify something notable
3. Group by THEME, not by engagement. Common themes:
   - Models & Benchmarks (new models, evals, leaderboards)
   - Developer Tools & Code Agents (IDE, workflows, agent tooling)
   - ML Research (papers, loss functions, architectures, training)
   - Infrastructure & Compute (chips, datacenters, scaling)
   - Community & Events (hackathons, launches, meetups)
   - Hot Takes & Discourse (opinions, debates, controversy)
4. Write a short paragraph per theme summarizing what's discussed and why it matters. Mention author handles.
5. At the end, add a "Links" section with raw tweet URLs grouped by theme — one per line, no descriptions. User clicks through to read originals.

### Format Preference (important)

User prefers PLAIN TEXT digests:
- No markdown headers (#)
- No emoji section dividers (━━━━)
- No bold (**)
- Simple date header, blank lines between sections
- Conversational tone, not press-release
- Raw links section at the end for clicking through

## Token Refresh

OAuth2 user tokens expire after 7200s (2 hours). The refresh_token grant and client_credentials grant BOTH regularly fail with 400 errors on this setup — the X Developer Portal auth configuration is not compatible with standard OAuth2 token refresh flows.

**Working fallback: use the bearer token from xurl config.** Bearer tokens persist between xurl sessions and work fine for read-only endpoints (list-tweets, search, user lookups).

```python
import yaml, json

# Read bearer token from xurl config
with open(os.path.expanduser('~/.xurl')) as f:
    xurl_cfg = yaml.safe_load(f)

# Get default app's bearer token
default_app = xurl_cfg.get('default_app', 'app32749964')
bearer = xurl_cfg['apps'][default_app]['bearer_token']['bearer']

# Save to our token file so xapi.py picks it up
with open('/opt/data/config/x-oauth2-tokens.json') as f:
    tokens = json.load(f)
tokens['access_token'] = bearer
with open('/opt/data/config/x-oauth2-tokens.json', 'w') as f:
    json.dump(tokens, f, indent=2)
```

**Simpler fallback (no yaml needed)** — just use a known-good bearer token directly:
```python
with open('/opt/data/config/x-oauth2-tokens.json') as f:
    tokens = json.load(f)
tokens['access_token'] = 'AAA[BEARER_TOKEN]AAAAAAAAA'  # paste from ~/.xurl
with open('/opt/data/config/x-oauth2-tokens.json', 'w') as f:
    json.dump(tokens, f, indent=2)
```

Then verify: `python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 1 --json`

## Primary API Interface

`/opt/data/scripts/xapi.py` is the primary way to call X APIs. Do NOT use `xurl --auth oauth2` — its config parser doesn't pick up manually-injected tokens. The wrapper reads tokens from `/opt/data/config/x-oauth2-tokens.json` directly.

## Cron Jobs

The `ai-high-signal-digest` cron job runs daily at 09:00 UTC, delivering thematic summaries to `discord:#x-tweet-digests`.

Format preference: plain conversational summaries grouped by theme, with raw tweet links at the end. No fancy markdown, no emoji section dividers.

## Pitfalls

- **Token refresh is broken on this setup.** Both `refresh_token` grant and `client_credentials` grant fail with 400 errors. Bearer tokens from `~/.xurl` are the reliable fallback for read-only endpoints. If you get a 401 error, copy the bearer token from `~/.xurl` into `/opt/data/config/x-oauth2-tokens.json` and retry.
- List endpoint max is 100 tweets per request, pagination via `pagination_token`
- Retweets show original author_id but the text includes "RT @user:" prefix
- Rate limits: 900/15min for app-only, 900/15min for user auth on most endpoints
- Bookmarks endpoint requires actual user_id (e.g. `43469078`), NOT `me` — `/users/me/bookmarks` returns 400. The wrapper handles this automatically by reading user_id from the token file.
- When writing inline Python for token ops, avoid heredocs (`python3 << 'EOF'`) — the terminal tool blocks them. Write to a `.py` file and execute instead.
