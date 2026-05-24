# xapi.py Cache Reference

The xapi.py wrapper (at `/opt/data/scripts/xapi.py`) caches all API responses to disk to reduce redundant X API calls and control costs.

## Cache Location

```
/opt/data/cache/xapi/
```

Files are named by MD5 hash of `{command}:{params_string}:{page_token}`. Format: Python pickle.

## Per-Command TTLs

Configured in `CMD_TTL` dict (xapi.py lines 36-43):

| Command | TTL | Rationale |
|---------|-----|-----------|
| `list-tweets` | 1800s (30 min) | Short for real-time monitoring |
| `bookmarks` | 1800s (30 min) | Bookmarks change frequently |
| `search` | 2592000s (30 days) | Historical search results are static |
| `user` | 2592000s (30 days) | User profile data rarely changes |
| `user-id` | 2592000s (30 days) | Same as user |
| `timeline` | 2592000s (30 days) | Historical timeline is static |

## Tuning for Daily Cron

The `ai-high-signal-digest` cron runs once daily at 09:00 UTC. With the default 30-min TTL for `list-tweets`, every run makes fresh API calls (costing API quota + wasting tokens reading 300+ tweets).

### Recommended: 24h TTL

```python
CMD_TTL = {
    "list-tweets": 86400,   # 24 hours
    "bookmarks": 1800,
    "search": 2592000,
    "user": 2592000,
    "user-id": 2592000,
    "timeline": 2592000,
}
```

With 24h TTL, each daily run reads yesterday's cache. The API is only called when the cache is empty (first run, or after a gap > 24h).

### Trade-off: Staleness

A 24h cache means tweets in the digest are up to 24 hours old. For a daily summary this is acceptable — the cron runs at 09:00 and pulls tweets from the previous 24h period. If a user wants fresh tweets mid-day, they can use `--fresh` on the command line.

## Cache Invalidation

- **Automatic**: Cache entries older than their TTL are deleted on access
- **`--fresh` flag**: Pass `--fresh` to `list-tweets` to bypass cache entirely
- **Manual**: `rm /opt/data/cache/xapi/*` to clear all cache

## Cost Impact

| Scenario | API calls per run | Tweets fetched | Est. X API quota |
|----------|------------------|----------------|-------------------|
| 30-min TTL, `--max 100 --all` | 3-4 | 300+ | 90-120/month |
| 24h TTL, `--max 50` | 0 (cache hit) | 50 | 0/day (re-uses cached) |
| 24h TTL, `--max 100` | 0 (cache hit) | 100 | 0/day |
| Fresh `--max 50` | 1 | 50 | 30/month |

**Rule of thumb**: If the cron has run successfully in the last 24h, the cache has yesterday's data. No API calls needed.