---
name: x-twitter-digest
description: Produces daily thematic digests from X/Twitter lists for the AI High Signal list. Fetches tweets via OAuth2 API, groups by theme, and outputs plain text reports.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [twitter, x, social-media, digest, oauth2, automation]
---

# X/Twitter Digest Automation

## Overview
Produces daily thematic digests from X lists for the AI High Signal list. Fetches tweets via the official `xurl` CLI, groups them by theme, and outputs plain text reports with raw tweet links.

## Tools Used
- `xurl` CLI - Official X/Twitter command-line interface (v2 API)
- `/opt/data/config/x-cli/accounts/` - xurl account configurations
- `/opt/data/logs/digest-runs.jsonl` - Run status tracking

## Workflow Steps

### Step 0: Ensure Authentication
The `xurl` CLI handles authentication automatically via the user's configured accounts. Ensure the account for the AI High Signal list is properly set up. If authentication fails, the `xurl` commands will return errors.

**If authentication fails**: Log error and require manual re-authorization via `xurl --auth oauth2` or `hermes setup`.

### Step 1: Fetch Tweets
```bash
# Full output for LLM processing
xurl --account nickjlange list tweets --list-id 1585430245762441216 --limit 40 > /tmp/digest_tweets.txt

# Links-only output (do NOT let LLM rewrite)
xurl --account nickjlange list tweets --list-id 1585430245762441216 --limit 40 --format json | jq -r '.data[].url' > /tmp/digest_links.txt
```

**Note**: The `--account` flag specifies which xurl account to use. The default account is typically `nickjlange` (personal) or `5L_Labs` (business). Adjust as needed based on which account has access to the AI High Signal list.

### Step 2: Thematic Summary
- Read `/tmp/digest_tweets.txt`
- Skip pure RTs unless they amplify something notable
- Group by THEME (not engagement):
  - Models & Benchmarks (new models, evals, leaderboards)
  - Developer Tools & Code Agents (IDE, workflows, agent tooling)
  - ML Research (papers, loss functions, architectures, training)
  - Infrastructure & Compute (chips, datacenters, scaling)
  - Community & Events (hackathons, launches, meetups)
  - Hot Takes & Discourse (opinions, debates, controversy)
- Write short paragraph per theme with author @handles
- Format: Plain text only, no markdown, no emoji dividers, conversational tone
- Date header: "AI High Signal Digest — [Current Date]"

### Step 3: Links Section
After prose, add blank line, then "Links", then append `/tmp/digest_links.txt` verbatim. Do NOT rewrite, reorder, or reformat.

### Step 4: Validation
```bash
# Check that we have valid URLs
if [ -s /tmp/digest_links.txt ]; then
    echo "Links file is valid and non-empty"
else
    echo "ERROR: Links file is empty or missing"
    exit 1
fi
```

### Step 5: Logging
Append JSONL entry to `/opt/data/logs/digest-runs.jsonl`:
```json
{"ts": "ISO_TIMESTAMP", "status": "ok|broken|error", "urls_total": N, "urls_valid": N, "urls_broken": N, "note": "brief description"}
```

### Step 6: Delivery
Post the digest to Discord channel `#x-tweet-digests` using the `send_message` tool or appropriate delivery mechanism.

## Cron Configuration
- Runs daily at 09:00 UTC
- Delivers to `discord:#x-tweet-digests`
- Silent mode: output `[SILENT]` if nothing new to report

## Critical Pitfalls & Fixes

### xurl Account Configuration
Ensure the xurl account is properly configured with OAuth2 tokens. The account can be set up using:
```bash
xurl --auth oauth2
```
or via the Hermes setup process.

### Handling Authentication Failures in Headless Environments
**Critical:** The xurl CLI requires a browser for OAuth2 authentication. In headless environments (like this server), you must use **app-only authentication** (`--auth app`) which does not require user interaction.

If you encounter 401 Unauthorized errors when using `--auth oauth2`, switch to `--auth app` and ensure your app credentials are properly registered.

### App-Only Authentication Setup
1. Register an app with X Dev Platform:
   ```bash
   xurl auth apps add my-app --client-id YOUR_CLIENT_ID --client_SECRET YOUR_CLIENT_SECRET
   ```
2. Use app-only auth for API requests:
   ```bash
   xurl --auth app /2/lists/1585430245762441216/tweets
   ```

### Multiple Account Support
- xurl supports multiple accounts (personal, business, etc.)
- Specify accounts with `--account` flag (e.g., `--account 5L_Labs`)
- Default account is typically `nickjlange`

### Fallback When API is Unavailable
1. Check xurl authentication status first
2. If API calls fail, log "error" status in JSONL
3. Do NOT post automated digest with stale/missing data
4. Require manual intervention to re-authorize
