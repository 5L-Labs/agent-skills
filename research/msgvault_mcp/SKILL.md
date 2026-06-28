---
name: msgvault_mcp
description: Interacts with the MsgVault MCP server to search emails, retrieve message details, and read inbound feeds.
version: 1.0.0
---

# MsgVault MCP Skill

This skill provides programmatic access to the MsgVault MCP server, allowing you to search archived inbound emails and retrieve detailed messages (e.g. from Mozmail).

## Configuration Requirements

To use this skill, the following environment variables must be defined in your `.env` file:
*   `MSGVAULT_URL`: The HTTP/SSE endpoint of the MsgVault MCP server (e.g., `https://lunarbeacon.newyork.nicklange.family:9443/mcp`).
*   `MSGVAULT_PASSWORD`: The access password/token for the MsgVault service.

## Usage

You can search inbound emails by invoking the script:

```bash
python research/msgvault_mcp/scripts/search_vault.py --query "Toyota Sienna" --limit 5
```

### Options
*   `--query`: The search term or query string (e.g., `is:unread "Lexus"`)
*   `--limit`: Maximum number of messages to return (default 5)
