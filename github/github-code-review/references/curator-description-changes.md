# Curator-Generated Description Changes in Nightly PRs

When reviewing nightly update or auto-sync PRs on agent-skills repos, you may see dozens of one-line `description:` changes in SKILL.md frontmatter files. These come from the **Hermes Curator** — an internal system that aligns our forked skill descriptions with upstream (NousResearch/hermes-agent) format.

## Pattern

Each change is a YAML frontmatter `description:` field being shortened:

```
-description: Very long verbose description of what this tool does and when to use it...
+description: "Short concise tool summary."
```

The shortened versions always match upstream's `description:` exactly.

## When this matters

- **These changes are noise**, not substantive updates. They don't change skill behavior.
- If main already received an earlier nightly PR with the same changes, the PR is proposing redundant changes (both sides have identical content — merge will be clean).
- Always check if the description changes are already in `main` using the merge-base technique before flagging them as review concerns.

## How to detect

```bash
# Find merge base
MERGE_BASE=$(git merge-base origin/main origin/$PR_BRANCH)
# Check if description changes are already in main
for file in $(git diff $MERGE_BASE...HEAD --name-only | grep SKILL.md); do
  desc_pr=$(git show HEAD:"$file" | grep "^description:" 2>/dev/null)
  desc_main=$(git show origin/main:"$file" | grep "^description:" 2>/dev/null)
  if [ "$desc_pr" = "$desc_main" ]; then
    echo "REDUNDANT (already in main): $file"
  fi
done
```
