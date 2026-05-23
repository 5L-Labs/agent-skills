# xapi.py Debugging Reference

## Common Digest Failures

### 401 Unauthorized (Token Expired)
**Symptom**: `API Error 401: {"title": "Unauthorized", "detail": "Unauthorized"}`

**Fix**: Run `refresh-token` first:
```bash
python3 /opt/data/scripts/xapi.py refresh-token
```
Token expires every 2 hours. Only needed before `--fresh` fetches. Cached data was written with a valid token and is safe to read.

### Stale Digest (Same Tweets Every Day)
**Symptom**: Identical tweets appearing across multiple daily digests.

**Check cache freshness first:**
```bash
ls -la /opt/data/cache/xapi/  # check mtimes on cache files
python3 -c "import time; print(f'Now: {time.time() - 1800}s ago = 30m ago')"  # is cache < 30m old?
```

**If cache is old:** The 30m TTL should have expired. Run a manual fetch with `--fresh`:
```bash
python3 /opt/data/scripts/xapi.py refresh-token
python3 /opt/data/scripts/xapi.py list-tweets 1585430245762441216 --max 100 --all --fresh
```

**If cache is fresh (within 30m):** Wait 30m for the next API call, or use `--fresh` for an immediate hit.

**Historical note (fixed 2026-05-22):** The original 30-day TTL caused 7+ consecutive daily digests from the same cached data. The system now uses dual TTLs (30m for list-tweets/bookmarks, 30d for static tweet data). Daily cron runs do NOT use `--fresh` — the 30m TTL handles freshness automatically.

### API returns 400 on bookmarks
**Symptom**: Bookmarks endpoint returns 400 Bad Request.

**Fix**: The wrapper handles this automatically by reading `user_id` from the token file. If it still fails, check that the token file has a valid `user_id` field.

### Token Refresh Fails (HTTP 400)
**Symptom**: `Token refresh failed (HTTP 400)`

**Possible causes:**
1. Refresh token expired (irrecoverable — needs full re-auth via `hermes setup`)
2. Client secret changed or rotated in X Developer Portal
3. Network connectivity issue

**Recovery**: Re-run `hermes setup` to get fresh credentials.

### `--all` Fetch Returns Tweets Without Timestamps
**Symptom**: Multi-page fetches show empty author brackets `[]` and no date line per tweet.

**Root cause (fixed 2026-05-22):** The `--all` pagination path was missing `tweet.fields`, `expansions`, and `user.fields` params. Single-page fetches had them but not paginated ones.

**Fix**: Already applied. Re-fetch with the same command — new cache keys are generated and data will include timestamps.

## Cache Location

Cache files live at `/opt/data/cache/xapi/` as pickle blobs keyed by MD5 hash. To inspect:
```bash
ls -lt /opt/data/cache/xapi/ | head -10  # most recent 10 cache entries
```

For details on the dual TTL system, see `references/xapi-caching.md`.
