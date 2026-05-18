---
name: nightly-upstream-sync
description: Nightly git sync that only commits local modifications and new files vs an upstream repo, opens PRs, and auto-merges on green.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [git, github, ci, sync, upstream, fork]
status: stable
---

# Nightly Upstream Sync

## Problem

Maintaining a repo that's a subset/customization of an upstream project. You only want to commit files that are **new** or **modified** vs upstream — not re-commit everything from upstream every night.

## Architecture

```
/opt/data/upstream-hermes-agent/   # Read-only clone (separate path)
/opt/data/skills/                  # Our repo (only custom files go in PRs)
/opt/data/repos/agent-memories/    # Another repo (no upstream, commits everything)
```

**Two-repo model:**
- **With upstream** (e.g., agent-skills): compare file-by-file, only commit diffs
- **Without upstream** (e.g., agent-memories): commit everything

## Key Design Decisions

### Use a separate clone, NOT a remote

```bash
# DON'T: upstream remote in same repo — risk of accidental push
git remote add upstream git@github.com:NousResearch/hermes-agent.git

# DO: read-only clone at separate path
git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /opt/data/upstream-hermes-agent
```

Why: keeps upstream completely isolated. No risk of `git push upstream main` by accident.

### Don't delete/rebuild repos

The initial commit may contain all upstream files. Don't try to strip them — too risky. Instead, the nightly script only stages files that are new or modified vs upstream. The bulk upstream content in history is inert.

### Filter gitignored files

```python
for f in new_files + modified_files:
    _, _, rc = run(["git", "check-ignore", "-q", f], cwd=path, check=False)
    if rc == 0:
        continue  # skip gitignored
    run(["git", "add", f], cwd=path)
```

## Implementation

### File comparison logic

```python
# Build upstream map: relative path -> file content bytes
upstream_map = {}
for root, dirs, files in os.walk(upstream_skills_dir):
    for f in files:
        rel = os.path.relpath(os.path.join(root, f), upstream_skills_dir)
        upstream_map[rel] = Path(os.path.join(root, f)).read_bytes()

# Compare local files
new_files = []
modified_files = []
for root, dirs, files in os.walk(local_path):
    for f in files:
        rel = os.path.relpath(os.path.join(root, f), local_path)
        our_content = Path(full).read_bytes()

        if rel not in upstream_map:
            new_files.append(rel)
        elif our_content != upstream_map[rel]:
            modified_files.append(rel)
```

### Nightly flow

1. `git fetch --depth 1 origin main` on upstream clone
2. Compare files against upstream map, classify into two groups:
   - **new_files** (files that don't exist upstream -- our custom additions)
   - **modified_files** (files that exist in both but differ -- upstream changes to sync)
3. **Split into two PRs:**
   - **Upstream sync** (`update/upstream-YYYY-MM-DD`): only modified_files. Auto-merges on green. Title: `Upstream sync {date}`
   - **Local customizations** (`update/local-YYYY-MM-DD`): only new_files. Needs human review. Title: `Local customizations {date}`
4. Each branch: stage files, commit, push with --force, open PR via GitHub API
5. Auto-merge workflow handles upstream PRs automatically (skips local PRs -- see `github-auto-merge-workflow` skill)
6. Deliver summary to user in chat

### Why split?

| Before (one PR) | After (two PRs) |
|-----------------|-----------------|
| One giant PR mixing upstream changes with new custom skills | Clean separation |
| 60+ one-line description changes drown out the 3 new skills | Upstream PR merges silently |
| Reviewer has to sift through noise to find the signal | Local PR shows only what needs review |
| Auto-merge on everything or nothing | Upstream auto-merges, local waits |

### Cron job

```
Schedule: 0 3 * * * (03:00 UTC)
Deliver: origin (to current chat)
```

## Pitfalls

- **Stale merge base**: A nightly PR branched from an older `main` will show changes already present in current `main` (e.g. description-line edits from a prior nightly sync). Git resolves them cleanly (same content on both sides), but the diff is noisy. Fix: rebase branch onto latest `main` before pushing, or just note it in the PR body.
- **Don't use `git remote add upstream`** in the same repo -- separate clone is safer
- **Don't delete upstream files** from your repo to "clean up" -- just let the nightly script skip them
- **`os.path.reljoin` doesn't exist** -- use `os.path.relpath`
- **`git rm -rf .` on 400+ files can timeout** -- avoid bulk operations, use targeted `git add` for custom files only
- **`git add` fails on gitignored files** -- always check with `git check-ignore -q` first
- **Branch protection needs GitHub Pro for private repos** -- use `workflow_run` auto-merge instead
- **Selective auto-merge**: The auto-merge workflow needs a branch-name guard to skip local-only PRs. See the `github-auto-merge-workflow` skill for implementation.

## Script Location

`/opt/data/scripts/nightly-repo-sync.py`

## Related Skills

- `github-auto-merge-workflow` — handles the merge-on-green step
