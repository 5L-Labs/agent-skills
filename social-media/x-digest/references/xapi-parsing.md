# xapi.py Tweet Output Parsing

When `--links-only` is unavailable (e.g., 401 on that endpoint only), extract tweet data from the full-text output format.

## Raw Output Format

Each tweet block is separated by `------------------------------------------------------------`:

```
[@handle (Display Name)] RT @original_author: tweet text...
  ♥42 🔁7 💬3
  2026-05-22T08:53:48.000Z | https://x.com/i/status/2057746738400973008
------------------------------------------------------------
```

**Non-original-tweet block:**
```
[@handle (Display Name)] Tweet text with embedded https://t.co/ links
  ♥13495 🔁645 💬200
  2026-05-22T14:45:00.000Z | https://x.com/i/status/2057515035472380237
------------------------------------------------------------
```

## Key Parsing Rules

1. **Author**: Parse from `[@handle (Display Name)]` on the first line
2. **Retweets**: First line contains `RT @user:` — strip this prefix for display text, but note the original author
3. **Timestamps**: Last line before separator, format `%Y-%m-%dT%H:%M:%S.000Z | <url>`
4. **Engagement**: Line with ♥ 🔁 💬 emojis — parse digits after each
5. **Links**: The `https://x.com/i/status/<id>` URL in the timestamp line is the canonical tweet link. Do NOT use `t.co` shortlinks in the Links section — always use the full `x.com/i/status/` URL
6. **Fresh fetch headers**: When `--fresh` is used, the output starts with lines like `Fresh fetch for list-tweets (page: ...) — bypassing cache`. Skip these lines during parsing

## Python Extraction Pattern

```python
import re

# Split blocks
blocks = content.split('------------------------------------------------------------')

for block in blocks:
    lines = block.strip().split('\n')
    if not lines:
        continue
    
    # Skip fresh-fetch headers
    if lines[0].startswith('Fresh fetch'):
        continue
    
    # Author from first line
    am = re.search(r'\[@(\w+)\s*\(([^)]+)\)\]', lines[0])
    handle = am.group(1) if am else 'unknown'
    
    # Is it a retweet?
    is_rt = 'RT @' in lines[0]
    
    # Timestamp and link from last lines
    for line in lines:
        if re.match(r'^2\d{3}-\d{2}-\d{2}T', line):
            ts_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)', line)
            link = re.search(r'(https://x\.com/i/status/\d+)', line)
            break
    
    # Engagement
    for line in lines:
        em = re.search(r'♥(\d+)', line)
        rm = re.search(r'🔁(\d+)', line)
        # hearts = int(em.group(1)), rt_count = int(rm.group(1))
```

## Filtering by Time Bucket

Parse ISO timestamps and compare against `datetime.now(timezone.utc) - timedelta(hours=24)` for daily digests or `timedelta(days=7)` for weekly digests.

## Edge Cases

- Some blocks may have no text content (pure image tweets) with only engagement + URL — handle gracefully
- The `--fresh` output includes pagination header lines that are NOT tweet content
- When the API returns 401/403 but no cache exists, check `/opt/data/scripts/xapi.py` cache directory for any stale data before giving up
- `t.co` links in tweet text are shortened forms — always extract the full `https://x.com/i/status/NNN` URL from the timestamp line for the Links section
