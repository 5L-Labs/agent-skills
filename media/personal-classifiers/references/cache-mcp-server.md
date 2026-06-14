---
name: cache-mcp-server
description: MCP server that exposes the Hermes data cache (playlist metadata, classifier registry, digest archives) as queryable resources and tools. Lets external agents and users browse cached data without shell access.
version: 0.1.0
author: Hermes Agent 01
status: draft
---

# Cache MCP Server

Exposes the Hermes container's cached data as an MCP server so external agents (Codex, Claude Code, Cursor, other Hermes instances) and users can query cached datasets without shell access to the container.

## Data Sources Exposed

| Resource URI | Backing File | Description |
|-------------|--------------|-------------|
| `cache://youtube/metadata` | `/opt/data/content/playlists/cache/video_metadata.json` | 275 YouTube videos with descriptions, durations, channels, tags |
| `cache://youtube/playlists` | `/opt/data/content/playlists/all_videos.txt` | 282 playlist video IDs + titles |
| `cache://classifiers/registry` | *(agent-skills repo)* `references/classifier-registry.json` | Term-based classification data |
| `cache://classifiers/items` | *(separate)* `classifier-items.json` | Per-item classification results |
| `cache://jargon/registry` | *(jargon skill)* `references/jargon-registry.json` | Known jargon terms with definitions |
| `cache://digests/x/latest` | `/tmp/digest_tweets.txt` | Latest X/Twitter digest raw tweets |
| `cache://digests/hn/latest` | `/opt/data/cache/hn-brief/*/formatted-digest.txt` | Latest HN Brief formatted digest |

## Tools

| Tool | Description |
|------|-------------|
| `cache_search(query, source, limit)` | Full-text search across all cached data |
| `cache_get(resource_uri, filters)` | Get data from a specific resource with optional filters |
| `cache_stats()` | Show cache sizes, staleness, last-updated times |
| `cache_classify(item_id, lou, sotw, nfm)` | Manually override a cached item's classification |

## Implementation Approach

Hermes has a built-in MCP server (`hermes mcp serve`). The cache MCP server would be a plugin or wrapper that:

1. Loads registered data sources from config (`~/.hermes/config.yaml` under a `cache_mcp` section)
2. Exposes each source as an MCP resource with the URI scheme above
3. Exposes search and query tools
4. Runs alongside or within the Hermes gateway

The server itself is lightweight — it just reads JSON/text files and serves them over the MCP protocol. No database needed.

## Config (to be added to config.yaml)

```yaml
cache_mcp:
  enabled: true
  port: 8123
  data_sources:
    youtube_metadata: /opt/data/content/playlists/cache/video_metadata.json
    youtube_playlists: /opt/data/content/playlists/all_videos.txt
    classifier_registry: /opt/data/repos/agent-skills/media/personal-classifiers/references/classifier-registry.json
    classifier_items: /opt/data/content/classifiers/cache/items.json
    jargon_registry: /opt/data/repos/agent-skills/research/jargon/references/jargon-registry.json
    digest_logs: /opt/data/logs/digest-runs.jsonl
```

## Usage (from another agent or CLI)

```bash
# Query via MCP
hermes mcp add cache-mcp http://container-host:8123/mcp
hermes chat -q "What YouTube videos in the cache are classified as Novelty 5?"
```

```python
# Via MCP client
client = MCPClient("http://container-host:8123/mcp")
videos = client.call("cache_search", query="novelty sort by likes desc", source="youtube", limit=10)
```

## Next Steps

1. Implement the MCP server (Python, < 200 lines — just reads JSON files and wraps them in MCP resource format)
2. Register data sources in config.yaml
3. Test with external agent queries
4. Add authentication if exposed beyond localhost
