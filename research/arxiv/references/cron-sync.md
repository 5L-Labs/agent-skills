# Cron Job ↔ Skill Workflow Sync

When a skill documents a cron-ready workflow (like arXiv's "Daily Digest Workflow (Cron)" section), the production cron job config can drift out of sync if only the skill is updated during one session but the cron job is forgotten until the next.

## Check Pattern

After updating any cron workflow section in a skill, verify alignment:

1. **List cron jobs**: `cronjob action='list'` — find the matching job by name or delivery channel
2. **Check skills list**: does the cron job load all skills the workflow uses? E.g. if the workflow says "load unified-digest-themes and jargon alongside arxiv", the cron job's `skills` array must include them
3. **Check prompt**: does the cron job's prompt match the workflow's max_results, format instructions, and steps?
4. **Check model/toolsets**: any model override or enabled_toolsets constraints should match what the workflow expects

## Common Drift Patterns

| Signal | Fix |
|--------|-----|
| Skill says max_results=10, cron says 5 | Update prompt in `cronjob action='update'` |
| Skill lists 3 supporting skills, cron loads 1 | Add missing skills to the `skills` array |
| Skill expects `web` + `terminal` toolsets, cron has none | Set `enabled_toolsets: ["web", "terminal", "file"]` |
| Skill documents a new feature (jargon, themes), cron prompt is stale | Rewrite prompt to reference the full workflow |

## Why This Happens

Skills are updated mid-conversation when new requirements emerge. The cron job that consumes the skill is typically not examined in the same session unless the user specifically asks about it. The drift goes unnoticed until:
- The next scheduled run produces unexpected output
- Someone runs a manual test and compares against the skill docs

## Remedy

When updating a cron-referenced skill, always call `cronjob action='list'` and inspect any job whose `skill` or `skills` field references the skill being changed. Fix what's stale.