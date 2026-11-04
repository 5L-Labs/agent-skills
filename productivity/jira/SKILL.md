---
name: jira
description: "Use when working with Jira/Atlassian MCP on terraalpha."
version: 1.0.0
author: Hermes Agent 01
license: MIT
---

# Jira (Atlassian MCP)

## When to use
Any interaction with the Atlassian instance at terraalpha.atlassian.net. Project HOMEWORK is the shared work queue for Nick and the editors; the Daily Open Work Reminder cron reads it.

## Connection
- Tools live under `mcp__atlassian__*` (41 tools: searchJiraIssuesUsingJql, createJiraIssue, getVisibleJiraProjects, ...).
- cloudId: `1ad9038f-7601-4cfd-ad22-9f24cb1fc0f4` (the site URL terraalpha.atlassian.net also works as cloudId).
- Health check: call getAccessibleAtlassianResources + atlassianUserInfo (both take no args) to confirm auth and scopes (read:jira-work, write:jira-work).

## Query the work queue
- mcp__atlassian__searchJiraIssuesUsingJql(cloudId, jql, fields, maxResults).
- Standard queue JQL: `project = HOMEWORK AND status not in (Done, Closed, Canceled) ORDER BY priority DESC, created ASC`
- Default fields cover summary/status/issuetype/priority/assignee/reporter/created/updated/resolution/project; pass `fields` explicitly when you need comments/labels/components.
- Empty results are a valid answer: report "no open issues" — never fabricate items.

## Create issues
- mcp__atlassian__createJiraIssue(cloudId, projectKey, issueTypeName, summary, description?, additional_fields?).
- Priority goes in additional_fields: `{"priority": {"name": "High"}}`. Scheme names: Highest/High/Medium/Low/Lowest.
- Label items migrated from legacy lists `"stub"` so they can be audited later.
- Leave assignee unset for collaborative queue work (anyone picks up); assign via assignee_account_id only when asked.
- HOMEWORK issue types: Task (default for queue items), Bug, Story, Epic, Feature, Subtask.

## Priority tiers (shared convention)
- High/Highest -> HIGH PRIORITY | Medium -> MEDIUM | Low/Lowest -> LOW

## Reminder cron integration
- Job "Daily Open Work Reminder" (find by name via cronjob_manage list; 09:00 UTC daily; delivers to Signal "Daily Notices") runs an LLM prompt that calls searchJiraIssuesUsingJql directly, then formats plain-text, phone-width, grouped by tier, ending with `To stop or manage this job, send me a new message.`
- MCP tools are auto-injected into platform toolsets, so cron LLM jobs can call them without a script. After editing any cron prompt that depends on an MCP tool, fire the job once to confirm the tools resolve in the job session.

## Pitfalls
- Batching several issue creations in one tool_call: EVERY entry needs both "name" and "arguments" — an entry missing "name" fails the whole batch's JSON parse with a generic error. Build each entry fully.
- Verify creation and priority with a follow-up search (fields: priority, status) rather than trusting create responses alone.
- Do not hardcode the cron job's id in this skill — resolve it by name at use time.
