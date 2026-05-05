---
name: fetch-restricted-social-content
description: Workflow for fetching social media content when primary API access is blocked or restricted, with fallback strategies
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [xurl, web_extract, browser_navigate, web_search]
metadata:
  hermes:
    tags: [social-media, twitter, x, content-fetching, fallback, restricted-access]
---

# Fetching Restricted Social Media Content

When direct API access to social media platforms (like X/Twitter) fails due to authentication issues, rate limiting, or blocking, use this fallback workflow to attempt content retrieval.

## Workflow Steps

### 1. Try Official API CLI First

Start with the platform's official CLI tool (e.g., `xurl` for X/Twitter):

```bash
# Verify installation and auth
xurl --help
xurl auth status

# If auth shows issues, fix default app:
xurl auth default <app-name-with-tokens>

# Try to read content
xurl read <POST_ID_or_URL>
```

### 2. Fallback to Web Extraction

If API fails, try web extraction (works for some sites):

```bash
web_extract --urls "["https://x.com/user/status/123"]"
```

### 3. Try Mobile Site with Browser Tools

If web extraction fails or is unsupported, use browser tools on mobile site:

```bash
browser_navigate --url "https://mobile.twitter.com/user/status/123"
browser_snapshot --full true
# or
browser_vision --question "What is the text content of this tweet?"
```

### 4. Try Alternative Frontends

If the main site blocks automation, try privacy-focused frontends:

- nitter.net (for Twitter/X)
- Example: `https://nitter.net/Teknium/status/2047093325774385358`

### 5. Use Web Search for Snippets

As a last resort, search for the content:

```bash
web_search --query "full text of tweet by username about topic"
# or search for unique phrases from the tweet if known
```

### 6. Ask User for Content

If all automated methods fail, ask the user to provide the text content directly.

## Troubleshooting Common Issues

### Authentication Failures (401/403)
- Verify `xurl auth status` shows valid tokens for the default app
- If default app shows `oauth2: (none)`, run `xurl auth default <working-app>`
- Never share or paste credentials in agent sessions

### Site Blocking/Scraping Prevention
- Twitter/X actively blocks automated access
- Mobile site may work better than desktop
- Alternative frontends (nitter) often have less blocking
- Add delays between requests if doing multiple fetches

### Rate Limiting (429)
- Wait and retry after rate limit period
- Reduce frequency of requests

## When to Use This Workflow

- You need to read/process social media posts but API access fails
- Web scraping returns "Website Not Supported" errors
- Browser navigation times out or shows empty pages
- You get authentication errors despite having tokens configured

## Safety Notes

- Never attempt to bypass authentication by passing secrets in agent sessions
- All auth operations (`xurl auth oauth2`) must be done by user outside agent
- Respect platform terms of service and rate limits
- If consistently blocked, consider whether manual user provision of content is better

## Example Session

When trying to fetch tweets:
1. `xurl read 2047093325774385358` → 401 Unauthorized
2. `web_extract` → "Website Not Supported"
3. `browser_navigate` to mobile.twitter.com → timeout
4. `browser_navigate` to nitter.net → success or alternative path
5. If still failing, `web_search` for tweet text
6. If all fail, ask user to copy/paste tweet text

## Related Skills

- `xurl`: Official X/Twitter API CLI
- `web_search`: Find information when direct access fails
- `browser_vision`: Extract text from screenshots when text-based methods fail