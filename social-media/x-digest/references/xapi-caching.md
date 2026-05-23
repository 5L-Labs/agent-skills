# xapi.py Caching Architecture

## Dual TTL System

`xapi.py` uses a per-command TTL dictionary (`CMD_TTL`) instead of a single cache TTL:

```
CMD_TTL = {
    "list-tweets": 1800,   # 30 minutes — new posts appear quickly
    "bookmarks":   1800,   # 30 minutes
    "search":      2592000,# 30 days — static query results
    "user":        2592000,# 30 days — profile data doesn't change
    "user-id":     2592000,# 30 days
    "timeline":    2592000,# 30 days
}
DEFAULT_TTL = 1800  # fallback 30m
```

**Why this split:** List-tweets and bookmarks need to show new posts within minutes. But once a tweet's content, metrics, and timestamp are fetched, that data is static — no need to hit the API again for 30 days.

## How `--fresh` Works

The `fresh=False` flag in `api_get()` controls cache bypass:

```python
def api_get(endpoint, params=None, token=None, cmd=None, page_token=None, fresh=False):
    if cmd and not fresh:
        cache_key = get_cache_key(cmd, params, page_token)
        cached = get_from_cache(cache_key, cmd=cmd)
        if cached is not None:
            return cached  # cache HIT
    if fresh:
        print("Fresh fetch — bypassing cache")
    # ... hit live API ...
    if cmd and cache_key:
        set_cache(cache_key, data)  # always write to cache
```

**Rules:**
- Daily cron runs: do NOT use `--fresh`. The 30m TTL means the API is hit at most once per 30 minutes.
- Manual override: use `--fresh` when you need the absolute latest data right now.
- Token refresh: only needed before `--fresh` fetches. Cached data was written with a valid token.

## Expired Cache Cleanup

`get_from_cache()` removes expired entries automatically:

```python
def get_from_cache(key, cmd=None):
    cache_file = os.path.join(CACHE_DIR, key)
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        ttl = CMD_TTL.get(cmd, DEFAULT_TTL)
        if time.time() - mtime < ttl:
            return pickle.load(f)     # still fresh
        else:
            os.remove(cache_file)     # expired — remove
    return None
```

Cache lives at `/opt/data/cache/xapi/` as pickle files keyed by MD5 hash of (cmd + params + page_token).

## Known Bug: `--all` Pagination Missing Fields

**Fixed 2026-05-22**

**Bug:** The `--all` (multi-page) path in `list_tweets()` used bare params:
```python
# BUGGED — no tweet.fields or expansions
params = {"max_results": max_results}
```

This meant multi-page fetches returned tweets **without timestamps** (no `created_at`), **without author data** (no `includes.users`), and **without metrics**. The single-page path had the correct fields.

**Fix:** The `--all` pagination loop now includes the same field expansions as the single-page fetch:
```python
common_params = {
    "max_results": max_results,
    "tweet.fields": "created_at,author_id,text,public_metrics,entities",
    "expansions": "author_id",
    "user.fields": "name,username",
}
```

**Why it matters:** Without `created_at`, you cannot filter tweets by time bucket (last 24h for daily digest, last 7 days for weekly). Without `author_id` expansions, output shows empty brackets `[]` instead of `@handle (Name)`.

## Cache Key Design

Cache keys are MD5 hashes of: `f"{cmd}:{str(params)}:{page_token}"`. This means:
- Different commands → different cache namespace
- Different params (e.g., `--max 10` vs `--max 100`) → different cache entries
- Different pages → separate cache entries each with their own TTL clock
- Adding fields to params → new cache key (old data remains but expires on its own TTL)

This is why the `--all` pagination fix didn't need a cache flush — the new params produce new cache keys, and old data expires in 30m.
