---
name: web-session-authentication
description: Automated web-based content extraction for paywalled or login-protected services.
---

# Web Session Authentication & Extraction

Use this skill when a task requires navigating to a site that is protected by a login wall (e.g., Financial Times, private dashboards).

## Workflow

1. **Check for existing session cookies:** Look for `/<path>/<site>-cookies.txt`.
2. **Setup Injection:** In your cron/task job, use a command to read and inject the cookie file into the browser session before navigation.
3. **Handle Silent Failures:** If extraction fails after cookie injection, ensure the process produces a clear error or a `[SILENT]` indicator as per the cron guidelines.

## References
- `references/ft-login-workaround.md` - Details on handling FT.com session cookies.
