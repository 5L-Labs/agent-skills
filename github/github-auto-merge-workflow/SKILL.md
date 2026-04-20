---
name: github-auto-merge-workflow
description: Auto-merge PRs on private repos without GitHub Pro using workflow_run trigger instead of branch protection.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [GitHub, CI/CD, auto-merge, private-repo]
status: stable
---

# GitHub Auto-Merge for Private Repos

## Problem

Branch protection rules (requiring status checks before merge) require GitHub Pro for private repos. The API returns 403: "Upgrade to GitHub Pro or make this repository public to enable this feature."

## Solution

Use `workflow_run` trigger to auto-merge after CI passes — same effect, no Pro needed.

## Implementation

### 1. CI Workflow (e.g., smoke-tests.yml)

```yaml
name: Smoke Tests
on:
  pull_request:
    branches: [main]
jobs:
  smoke-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: echo "Tests passed"
```

### 2. Auto-Merge Workflow

```yaml
name: Auto-merge
on:
  workflow_run:
    workflows: ["Smoke Tests"]
    types: [completed]
permissions:
  contents: write
  pull-requests: write
jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.event.workflow_run.conclusion == 'success'
    steps:
      - name: Merge PR on green
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          HEAD_SHA="${{ github.event.workflow_run.head_sha }}"
          PR_NUMBER=$(gh pr list --head "$HEAD_SHA" --json number --jq '.[0].number // empty')
          if [ -z "$PR_NUMBER" ]; then exit 0; fi
          gh pr merge "$PR_NUMBER" --squash --delete-branch
```

## How It Works

1. PR opened → CI workflow runs
2. CI completes → `auto-merge` workflow triggers via `workflow_run`
3. Checks `conclusion == 'success'` — does nothing on failure
4. Finds PR by head SHA, squash-merges, deletes branch

## Pitfalls

- **Do NOT add a `pull_request` trigger to the auto-merge workflow.** It causes a second run that tries `gh pr merge` outside the `workflow_run` context and fails with "Enable auto-merge for PR | failure". Only use `workflow_run`.
- The `workflow_run` trigger fires on ALL runs of the CI workflow, including pushes to main. The `if: conclusion == 'success'` guard handles this — it skips non-PR runs because `gh pr list --head` finds nothing.

## Limitations

- Only works for same-repo PRs (not forks)
- No reviewer requirements (needs branch protection / Pro)
- Multiple PRs with same head SHA: only first is merged
- Public repos can just use branch protection instead (no Pro needed)

## Use Cases

- Nightly commit/PR workflows (skill-versioning, memory exports)
- Bot-driven PRs that should auto-merge on green
- Any private repo workflow needing "merge on green" without Pro
