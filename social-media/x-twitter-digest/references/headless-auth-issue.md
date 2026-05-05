# Headless Authentication Issue with xurl CLI

## Problem
When running xurl commands in a headless environment (no browser available), OAuth2 authentication fails because xurl attempts to open a browser window for user interaction.

## Symptoms
- `xurl --auth oauth2 /2/lists/...` triggers a browser authorization URL
- Command hangs waiting for user interaction
- Eventually times out with no response

## Root Cause
xurl's default OAuth2 flow requires a web browser to complete the authorization code grant. In headless servers, there is no browser available.

## Solution
Use **app-only authentication** (`--auth app`) which uses client credentials grant and does not require user interaction.

### Steps to Implement

1. **Register an App** (if not already done):
   ```bash
   xurl auth apps add my-app --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
   ```

2. **Use App-Only Auth** for API requests:
   ```bash
   xurl --auth app /2/lists/1585430245762441216/tweets
   ```

## Important Notes
- App-only auth only has access to public data (which includes public X lists)
- The AI High Signal list is public, so app-only auth is sufficient
- Ensure the app has the correct scopes: `tweet.read`, `users.read`, `list.read`

## Verification
Check auth status to confirm app credentials are loaded:
```bash
xurl auth status
```

Should show the app with oauth2: ✓ and bearer: ✓ tokens.

## Prevention
When setting up xurl in any headless environment, immediately configure app-only authentication instead of user OAuth2.

## Related Files
- Token storage: `~/.xurl` (YAML format)
- App configuration: `~/.xurl/apps.yaml`
- Default app: `~/.xurl/default-app`

## Session Reference
- Date: 2026-05-04
- Task: Test x-twitter-digest automation
- Error: OAuth2 browser flow timeout
- Fix: Switched to app-only authentication