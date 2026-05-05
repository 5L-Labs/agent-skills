# FT.com Login Workaround

When automating access to myFT saved articles, the site redirects to a login page if no valid session cookie is found.

## Solution

1. Store cookies in `/opt/data/config/ft-cookies.txt`.
2. Inject into cron task prompt:
   ```bash
   # In job prompt
   2. Inject cookies: $(cat /opt/data/config/ft-cookies.txt)
   ```
3. **If this fails (including [SILENT] returns or 403 errors):** The Cloudflare bot protection is likely blocking the automated environment entirely, even with valid session cookies. The `__cf_bm` token is a critical component for these sessions and must be included in the cookie file.
4. If injection fails, the current strategy of simple automated navigation is insufficient. The environment's IP is likely blacklisted by the FT/Cloudflare WAF, requiring either a headless browser proxy or a more robust scraping service.
