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

OAuth2 tokens expire after 7200s (2 hours). To refresh:

```python
import urllib.request, urllib.parse, json, base64

with open('/opt/data/config/x-oauth2-tokens.json') as f:
    tokens = json.load(f)

data = urllib.parse.urlencode({
    'grant_type': 'refresh_token',
    'refresh_token': tokens['refresh_token'],
    'client_id': tokens['client_id'],
}).encode()

creds = base64.b64encode(f"{tokens['client_id']}:{tokens['client_secret_app32749964']}".encode()).decode()
req = urllib.request.Request('https://api.x.com/2/oauth2/token', data=data,
    headers={'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Basic {creds}'})
new_tokens = json.loads(urllib.request.urlopen(req).read())

# Update stored tokens
tokens['access_token'] = new_tokens['access_token']
if 'refresh_token' in new_tokens:
    tokens['refresh_token'] = new_tokens['refresh_token']
with open('/opt/data/config/x-oauth2-tokens.json', 'w') as f:
    json.dump(tokens, f, indent=2)
```

## Primary API Interface

`/opt/data/scripts/xapi.py` is the primary way to call X APIs. Do NOT use `xurl --auth oauth2` — its config parser doesn't pick up manually-injected tokens. The wrapper reads tokens from `/opt/data/config/x-oauth2-tokens.json` directly.

## Cron Jobs

The `ai-high-signal-digest` cron job runs daily at 09:00 UTC, delivering thematic summaries to `discord:#x-tweet-digests`.

Format preference: plain conversational summaries grouped by theme, with raw tweet links at the end. No fancy markdown, no emoji section dividers.

## Pitfalls

- Token expires every 2 hours — refresh before expiry or on 401 errors
- List endpoint max is 100 tweets per request, pagination via `pagination_token`
- Retweets show original author_id but the text includes "RT @user:" prefix
- Rate limits: 900/15min for app-only, 900/15min for user auth on most endpoints
- Bookmarks endpoint requires actual user_id (e.g. `43469078`), NOT `me` — `/users/me/bookmarks` returns 400. The wrapper handles this automatically by reading user_id from the token file.
- Token file corruption: the token file at `/opt/data/config/x-oauth2-tokens.json` may get truncated or redacted (values replaced with `...`). If xapi.py returns 401 AND token refresh also returns 401 ("unauthorized_client" or "Missing valid authorization header"), the token file is corrupted. The file's raw bytes must be inspected — `json.load()` looks fine but the stored tokens may be incomplete. To detect: check that access_token length is ~100+ chars and refresh_token is ~90+ chars with base64 content, not literal `...`. If corrupted, the API credentials need to be regenerated via a fresh OAuth2 flow using `xurl auth login`.

## Diagnosing 401 Errors

When xapi.py returns HTTP 401:
1. First try: refresh the token using the refresh_token grant
2. If refresh also returns 401 with "unauthorized_client": the client_id/client_secret pair is invalid or the app has been revoked — need to register a new app in the X developer portal
3. If refresh returns 401 but client credentials are OK: the refresh_token itself is expired/revoked — need a full re-auth flow via `xurl auth login` or browser-based OAuth2 authorization
4. Inspect the raw token file bytes, not just `json.load()` output — the file can appear valid JSON while containing truncated token values
5. Do NOT use `xurl --auth oauth2` for API calls — it tries interactive browser auth even when tokens exist. Always use xapi.py which reads the token file directly
