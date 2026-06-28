---
name: superhuman_mcp
description: Interacts with the Superhuman Mail MCP server to create, update, and manage email drafts, send emails, and schedule events.
version: 1.0.0
---

# Superhuman Mail MCP Skill

This skill provides programmatic access to the Superhuman Mail MCP server, allowing you to compose, update, send, and manage email drafts or schedule calendar events.

## Configuration Requirements

To use this skill, the following environment variables must be defined in your `.env` file:
*   `SUPERHUMAN_URL`: The HTTP/SSE endpoint of the Superhuman MCP server (e.g., `https://mcp.mail.superhuman.com/mcp`).
*   `SUPERHUMAN_AUTH`: The active OAuth Bearer token (e.g., `Bearer eyJ...`).

## Usage

You can draft emails by invoking the script:

```bash
python research/superhuman_mcp/scripts/draft_email.py --to "recipient@example.com" --subject "Subject Line" --body "Email body content"
```

### Options
*   `--to`: Recipient email address
*   `--subject`: Email subject line
*   `--body`: HTML body content (fallback direct write)
*   `--instructions`: AI instructions for writing style (optional)
