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
2. `git fetch origin main` + `git pull` on local repo
3. Compare files against upstream map
4. If changes: create branch `update/YYYY-MM-DD`, stage only custom files, commit, push
5. Open PR via GitHub API
6. Auto-merge workflow handles the rest (see `github-auto-merge-workflow` skill)
7. Deliver diff report to user in chat

### Cron job

```
Schedule: 0 3 * * * (03:00 UTC)
Deliver: origin (to current chat)
```

## Pitfalls

- **Don't use `git remote add upstream`** in the same repo — separate clone is safer
- **Don't delete upstream files** from your repo to "clean up" — just let the nightly script skip them
- **`os.path.reljoin` doesn't exist** — use `os.path.relpath`
- **`git rm -rf .` on 400+ files can timeout** — avoid bulk operations, use targeted `git add` for custom files only
- **`git add` fails on gitignored files** — always check with `git check-ignore -q` first
- **Branch protection needs GitHub Pro for private repos** — use `workflow_run` auto-merge instead

## Script Location

`/opt/data/scripts/nightly-repo-sync.py`

## Related Skills

- `github-auto-merge-workflow` — handles the merge-on-green step
