# Headless OAuth — SSH Tunnel Pattern

When setting up OAuth providers in Hermes Agent on a **headless server** (no browser), the standard auth flow fails because:
1. The server starts a local HTTP callback listener
2. It prints an auth URL for you to open in a browser
3. The browser redirects to `http://127.0.0.1:<port>/callback` — on YOUR machine, not the server
4. The callback never reaches the server

## Solution: SSH Port Forwarding

### One-shot approach

1. On your local machine, establish an SSH tunnel forwarding the callback port:
   ```bash
   ssh -L <port>:localhost:<port> <user>@<server>
   ```
   Where `<port>` matches the callback port the server printed (e.g., 56121, 41247).

2. Keep the SSH session open. In another terminal or your browser on the local machine, open the auth URL the server printed.

3. The browser redirects to `localhost:<port>` on your machine, which the SSH tunnel forwards to the server's `localhost:<port>`.

4. The server's OAuth handler receives the authorization code and exchanges it for tokens.

### Pitfalls

- **"Connection reused" error**: Previous tunnel instance is still holding the port. Either:
  - Kill it: `pkill -f "ssh -L <port>"` on your local machine, or just close the terminal
  - Use a different port if the server starts a new listener on a different port
- **"Connection refused"**: The server-side listener was killed before the tunnel was established. Restart the OAuth flow first, then set up the tunnel.
- **Tunnel port mismatches**: Make sure both sides of `-L` use the SAME port number. `-L 56121:localhost:56121` only works if the server is listening on 56121.

### Manual redirect URL extraction (fallback)

If the tunnel approach fails, the authorization code can be extracted manually:

1. Open the auth URL in your local browser.
2. Authorize the app. The browser will try to redirect to `http://127.0.0.1:<port>/callback?code=...&state=...` and fail.
3. **Copy the full failing URL from the browser's address bar** — it contains the `code` query parameter.
4. The code can be exchanged for tokens via the provider's token endpoint. Implementation depends on the specific OAuth provider's token exchange protocol.

## Supported OAuth Providers Requiring This Pattern

| Provider | Auth Command | Notes |
|----------|-------------|-------|
| xAI / SuperGrok | `hermes auth add xai-oauth` | Callback port printed by CLI |
| Nous Portal | `hermes login --provider nous` | Uses portal OAuth flow |
| xAPI OAuth2 | `xapi.py` setup | Token file at `/opt/data/config/x-oauth2-tokens.json` |
| GitHub Copilot | `hermes model` → GitHub Copilot | Device code flow — may work without tunnel |

## Verification

After completing OAuth:
```bash
# Check stored credentials
hermes auth list | grep <provider>

# Verify tool availability (if applicable)
hermes tools list | grep <tool_name>
```

If credentials are stored but the tool still shows as disabled, run:
```bash
hermes tools enable <tool_name>
/reset  # new session to pick up the tool
```
