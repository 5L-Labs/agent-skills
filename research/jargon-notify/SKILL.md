---
name: jargon-notify
description: Poll the jargon registry for new terms and post them to a Discord channel. Maintains a persistent state file so only genuinely new terms trigger notifications.
version: 1.0.0
author: Hermes Agent 01
license: MIT
metadata:
  hermes:
    tags: [jargon, notify, discord, automation, cron]
    related_skills: [jargon, unified-digest-themes]
---

# Jargon Notify

Watches the jargon registry for new terms and posts kindergarten-level definitions to a designated Discord channel. Designed to run as a cron job — stateless between runs, with all tracking in a persistent state file.

## Architecture

```
Registry (write source)      State file (read source)      Discord (output)
        │                           │                          │
┌───────▼────────┐          ┌───────▼──────────┐       ┌───────▼──────┐
│ jargon-registry │          │ posted-terms.json │       │ channel ID   │
│ .json           │          │ (NOT git-tracked) │       │ 15151903...  │
└───────┬────────┘          └───────┬──────────┘       └───────▲──────┘
        │                           │                          │
        └───────────┬───────────────┘                          │
                    │ DIFF                                      │
              ┌─────▼─────┐                                    │
              │ NEW TERMS? │──── yes ────► format + post ───────┘
              └─────┬─────┘
                    │ no
                 [SILENT]
```

## State File

Location: `<jargon-skill>/references/posted-terms.json`

IMPORTANT: this file is NOT git-tracked. The agent-skills repo gitignores `**/posted-terms.json` and deliberately untracked runtime state files (commit 33b3090, "chore: untrack runtime state files from git"). Write it to both the repo working tree and the consumption dir; never attempt `git add` (it will be refused by .gitignore, which is correct). The repo copy is primary for reads; a fresh clone starts with an empty/missing state file, and the first-run seed logic in Step 1 handles that by seeding all registry terms without notifying.

```json
{
  "version": 1,
  "last_checked": "2026-06-13T18:00:00Z",
  "posted_terms": {
    "BERT": "2026-06-13T18:00:00Z",
    "DPO": "2026-06-13T18:00:00Z"
  }
}
```

Each entry maps `term` → ISO timestamp when it was first posted to Discord. Terms not in this map are "new" and trigger a notification.

## Workflow

### Step 1: Load both sources

Load the jargon registry from the consumption directory:
```
/opt/data/skills/research/jargon/references/jargon-registry.json
```

Load the posted-terms state from the agent-skills repo (primary source of truth):
```
/opt/data/repos/agent-skills/research/jargon/references/posted-terms.json
```

If the state file doesn't exist (first run), create it with an empty posted_terms object and seed it with whatever terms are in the registry.

### Step 2: Diff

```python
import json, os
registry_terms = set(registry["terms"].keys())
posted_terms = set(state["posted_terms"].keys())
# Exclude terms the user has marked as known (jargon-blocklist.json)
blocklist_path = "/opt/data/skills/research/jargon/references/jargon-blocklist.json"
blocked = set()
if os.path.exists(blocklist_path):
    blocked = set(json.load(open(blocklist_path)).get("blocked_terms", []))
new_terms = (registry_terms - posted_terms) - blocked
```

If no new terms: [SILENT] — do nothing, do not send any message. Exit. (Blocked terms in jargon-blocklist.json are excluded from new_terms even when absent from state.)

### Step 3: Post new terms to Discord

For each new term, extract the kindergarten-level plainspeak definition from the registry entry:
```
registry["terms"][term]["plainspeak"]["kindergarten"]
```

Format as a Discord message:
```
🆕 New jargon: **TERM** — Full Name — kindergarten-level explanation
```

Example:
```
🆕 New jargon: **VPO** — Vector Policy Optimization — Teaching AI to come up with lots of different good ideas instead of just one
```

Post using the Hermes CLI — there is no in-tool `send_message` available in cron/headless mode:

```bash
hermes send --to discord:jargon-watch "🆕 New jargon: **TERM** — Full Name — kindergarten-level explanation"
```

Channel `discord:jargon-watch` resolves to `discord:1515190329832374272`. Group all new terms into a single message (one term per line). If more than 10 new terms, split into multiple messages. Check the command exit code (0 = delivered) before marking terms as posted.

### Step 4: Update state file

Add each newly posted term to `posted_terms` with current ISO timestamp. Update `last_checked`.

Write the updated state to BOTH locations:
1. `/opt/data/repos/agent-skills/research/jargon/references/posted-terms.json` (git repo, primary)
2. `/opt/data/skills/research/jargon/references/posted-terms.json` (consumption dir, immediate availability for next cron run)

### Step 5: No git commit

Do NOT commit the state file — the repo intentionally gitignores `**/posted-terms.json` (runtime state, never in source control). Writing to both locations in Step 4 is the entire persistence story. If you find yourself tempted to `git add -f`, stop: repo policy is explicit. The edge-case table below already documented the fallback; this is not a failure to work around, it is the design.

## Cron Job

Schedule: every 4 hours (can be tightened or relaxed)

```
cron: 0 */4 * * *
skills: [jargon-notify]
prompt: Run jargon-notify workflow to check for new jargon terms and post them to Discord.
deliver: origin
```

The cron prompt is intentionally minimal since the skill encodes all the logic.

### Dry-run mode

Set to `deliver: local` instead of `origin` to test without notifying the user. The cron still posts to Discord but the job output goes to local files only.

## Dependencies

- **jargon skill**: must have `jargon-registry.json` in its references directory
- **send_message tool**: required for Discord posting (available by default)
- **write_file tool**: required for state file updates
- **terminal tool**: required for the diff computation and CLI send
- **agent-skills repo**: must be cloned at `/opt/data/repos/agent-skills/` (state file lives in its working tree, NOT in git)

## Discord Channel

Default: `discord:1515190329832374272`

To change, update the send_message target in Step 3.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No new terms | [SILENT] — no message, no state update |
| State file missing | Create seeded with all current registry terms (no notification) |
| Registry missing | Error — log and exit, don't touch state |
| Registry term deleted | Nothing — we only detect additions, not removals |
| Discord send fails | Log error, don't update state (term will retry next run) |
| git add attempted | Refused by .gitignore — correct, do not force. Step 4 write is the whole persistence story |
| Consumption dir stale | State is read from agent-skills repo working tree as primary source of truth |

## Pitfalls

- The consumption directory (`/opt/data/skills/`) is rebuilt nightly from upstream + agent-skills originals. Writing state to the consumption dir is a convenience copy — the agent-skills repo working tree holds the real state (a fresh clone of the repo will NOT contain posted-terms.json; first-run seed logic handles that).
- New terms enter the registry via digest pipelines (x-digest, hn-brief-digest, arxiv). If those pipelines aren't running, no new terms will appear here.
- The registry uses the term acronym as the JSON key (e.g., `"BERT"`, not lowercase). The diff is case-sensitive — `"Bert"` won't match `"BERT"`.
- If a term is added to the registry and the cron fires before the state file diff picks it up, no problem — it'll get posted on the next tick.

## Version History

- 1.1.0 (2026-10-11): Corrected persistence model — posted-terms.json is NOT git-tracked (repo gitignores runtime state files by design since 33b3090). Removed the git-commit step; state lives in the repo working tree + consumption dir.
- 1.0.0 (2026-06-13): Initial skill. Polls jargon registry, diffs against posted-terms.json, posts new terms to Discord.
