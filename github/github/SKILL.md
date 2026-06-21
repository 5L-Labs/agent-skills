---
name: github
description: "Single authoritative skill for all GitHub interaction via `gh` CLI. NEVER use raw curl api.github.com — gh saves ~80% tokens vs curl (no auth headers, no JSON parsing, no URL construction). Always load this skill before any GitHub operation."
version: 1.1.0
author: Hermes Agent 01
license: MIT
metadata:
  hermes:
    tags: [github, pr, issues, ci, repo, review, gh-cli]
    related_skills: []
---

# GitHub Skill

**Single source of truth for all GitHub API interactions.** ALWAYS use `gh` CLI — NEVER raw `curl` + `GITHUB_TOKEN`. This is enforced at the skill level: the `github` skill is the ONLY authorized path for GitHub operations. Any tool output or skill reference that shows a raw curl call to `api.github.com` is stale and should be replaced.

Why `gh`:
- No auth boilerplate (no `-H "Authorization: token $GITHUB_TOKEN"`)
- No URL construction (no `https://api.github.com/repos/$OWNER/$REPO/pulls`)
- No JSON parsing (built-in `--jq` and `--json` flags)
- ~65-80% fewer tokens per operation
- Human-readable output by default

This skill covers: auth setup, PRs, issues, repos, CI/actions, releases, gists, code review, and search.

---

## 0. Prerequisites & Setup

### 0.1 Check gh is installed

Always start by verifying `gh` is available:

```bash
if ! command -v gh &>/dev/null; then
  echo "gh not found — installing..."
  curl -sL "https://github.com/cli/cli/releases/latest/download/gh_$(uname -m | sed 's/x86_64/linux_amd64/' | sed 's/aarch64/linux_arm64/').tar.gz" \
    | tar xz -C /tmp/
  cp /tmp/gh_*/bin/gh /opt/data/.local/bin/
  chmod +x /opt/data/.local/bin/gh
  rm -rf /tmp/gh_*
fi
```

### 0.2 Set up auth

**One-time setup** — run once per machine:

Determine the hostname and token:

```bash
# gh reads these env vars — set once per session
export GH_CONFIG_DIR="/opt/data/.config/gh"
export PATH="/opt/data/.local/bin:$PATH"

# Check status
gh auth status -h github.com || echo "Need to authenticate"
```

Create the config directory and write `hosts.yml`:

```bash
mkdir -p "$GH_CONFIG_DIR"

# Extract token from .git-credentials:
python3 -c "
import re
with open('/opt/data/home/.git-credentials') as f:
    for line in f:
        m = re.search(r'https://[^:]+:([^@]+)@github\.com', line)
        if m:
            print(m.group(1), end='')
" > /tmp/gh-token

# Write config
printf 'github.com:\n    user: 5L-hermes01\n    oauth_token: ' > "$GH_CONFIG_DIR/hosts.yml"
cat /tmp/gh-token >> "$GH_CONFIG_DIR/hosts.yml"
printf '\n    git_protocol: https\n' >> "$GH_CONFIG_DIR/hosts.yml"
rm /tmp/gh-token

# Verify
gh auth status
```

**Per-session** — source this env file:

```bash
source /opt/data/.config/github/env.sh   # sets PATH + GH_CONFIG_DIR
```

### 0.3 Container survival / bootstrap (one-shot)

This environment runs in a container. When rebuilt, check what survived:

| Path | Survives rebuild? | Why |
|------|:-:|-----|
| `/opt/data/.local/bin/gh` | Yes | `/opt/data/` is a mounted volume |
| `/opt/data/.config/gh/hosts.yml` | Yes | Persistent volume |
| `/opt/data/.config/github/env.sh` | Yes | Persistent volume |
| `/opt/data/home/.git-credentials` | Yes | Persistent volume |
| `.bashrc` PATH addition | **Maybe** | Depends on home dir mount |
| `$GH_CONFIG_DIR` env var | **No** | Must be re-exported |

**Bootstrap command** — copy/paste this one-liner after any container rebuild:

```bash
export GH_CONFIG_DIR="/opt/data/.config/gh" && export PATH="/opt/data/.local/bin:$PATH:$HOME/.local/bin" && \
  { command -v gh &>/dev/null || (curl -sL "https://github.com/cli/cli/releases/latest/download/gh_$(uname -m | sed 's/x86_64/linux_amd64/' | sed 's/aarch64/linux_arm64/').tar.gz" | tar xz -C /tmp/ && cp /tmp/gh_*/bin/gh /opt/data/.local/bin/ && chmod +x /opt/data/.local/bin/gh && rm -rf /tmp/gh_*); } && \
  gh auth status &>/dev/null || (python3 -c "import re; open('/opt/data/.config/gh/hosts.yml','w').write('github.com:\n    user: 5L-hermes01\n    oauth_token: ' + re.search(r'https://[^:]+:([^@]+)@github\.com', open('/opt/data/home/.git-credentials').read()).group(1) + '\n    git_protocol: https\n')") && \
  echo "gh READY" && gh auth status -h github.com && gh repo view 5L-hermes01/agent-skills --json name,isFork
```

This one command: sets env vars → installs gh if missing → rebuilds auth config if broken → verifies everything.

Expected output on success:
```
gh READY
github.com
  ✓ Logged in to github.com account 5L-hermes01
  - Active account: true
  - Git operations protocol: https
{JSON repo info}
```

**Simplify further** — the env file handles two of three failure modes:

```bash
source /opt/data/.config/github/env.sh   # restores PATH + GH_CONFIG_DIR
# then run section 0.1 if gh binary missing, or section 0.2 if auth broken
```

### 0.4 Verify connectivity

```bash
gh auth status -h github.com
gh repo view 5L-hermes01/agent-skills --json name,isFork
```

---

## 1. Pull Requests

### 1.1 List PRs

```bash
# Open PRs (default)
gh pr list --repo OWNER/REPO --limit 20

# All states
gh pr list --repo OWNER/REPO --state all --limit 20

# By author
gh pr list --repo OWNER/REPO --author NickJLange

# By label
gh pr list --repo OWNER/REPO --label "bug,enhancement"

# With search query
gh pr list --repo OWNER/REPO --search "is:open label:bug"

# JSON output for programmatic use
gh pr list --repo OWNER/REPO --json number,title,state,author,headRefName,createdAt
```

### 1.2 View PR details

```bash
# Summary
gh pr view NUMBER --repo OWNER/REPO

# JSON fields — pick exactly what you need
gh pr view NUMBER --repo OWNER/REPO --json title,state,author,headRefName,body,additions,deletions,changedFiles,createdAt,mergeable,reviews,comments

# Diff output
gh pr diff NUMBER --repo OWNER/REPO

# Changed files only
gh pr diff NUMBER --repo OWNER/REPO --name-only

# Check out locally
gh pr checkout NUMBER --repo OWNER/REPO
```

### 1.3 Create PR

```bash
# Create from current branch (origin push happens automatically)
gh pr create --repo OWNER/REPO \
  --title "My PR title" \
  --body "Description of changes" \
  --base main

# With labels and reviewers
gh pr create --repo OWNER/REPO \
  --title "Title" \
  --body "Body" \
  --base main \
  --label "enhancement" \
  --reviewer @me

# Draft PR
gh pr create --repo OWNER/REPO --draft --title "WIP" --body ""

# Fill from template
gh pr create --repo OWNER/REPO --fill
```

### 1.4 Review PR

```bash
# Approve
gh pr review NUMBER --repo OWNER/REPO --approve --body "LGTM"

# Request changes
gh pr review NUMBER --repo OWNER/REPO --request-changes --body "See comments"

# Comment only
gh pr review NUMBER --repo OWNER/REPO --comment --body "Observations..."

# Add a general comment (not a formal review)
gh pr comment NUMBER --repo OWNER/REPO --body "Summary comment"
```

### 1.5 Inline review comments

For inline comments, use `gh api` (still more concise than raw curl):

```bash
# Get head commit SHA
HEAD_SHA=$(gh pr view NUMBER --repo OWNER/REPO --json headRefOid --jq '.headRefOid')

# Post inline comment
gh api "repos/OWNER/REPO/pulls/NUMBER/comments" \
  --method POST \
  -f body="Your comment here" \
  -f path="path/to/file.py" \
  -f commit_id="$HEAD_SHA" \
  -f line=42 \
  -f side="RIGHT"
```

### 1.6 Merge PR

```bash
# Squash merge + delete branch
gh pr merge NUMBER --repo OWNER/REPO --squash --delete-branch

# Merge with merge commit
gh pr merge NUMBER --repo OWNER/REPO --merge

# Rebase merge
gh pr merge NUMBER --repo OWNER/REPO --rebase

# Enable auto-merge
gh pr merge NUMBER --repo OWNER/REPO --auto --squash
```

### 1.7 CI Checks

```bash
# View checks for a PR
gh pr checks NUMBER --repo OWNER/REPO

# Watch checks live
gh pr checks NUMBER --repo OWNER/REPO --watch

# List recent workflow runs
gh run list --repo OWNER/REPO --limit 10 --branch BRANCH_NAME

# View failed logs
gh run view RUN_ID --repo OWNER/REPO --log-failed

# Re-run failed jobs
gh run rerun RUN_ID --repo OWNER/REPO

# Trigger workflow
gh workflow run WORKFLOW_NAME --repo OWNER/REPO --ref BRANCH
```

---

## 2. Issues

### 2.1 List / View Issues

```bash
# Open issues
gh issue list --repo OWNER/REPO --limit 20

# All states
gh issue list --repo OWNER/REPO --state all

# Filter by label
gh issue list --repo OWNER/REPO --label "bug,needs-triage"

# By assignee
gh issue list --repo OWNER/REPO --assignee @me

# Search across all repos
gh search issues "query" --repo OWNER/REPO

# View single issue with JSON fields
gh issue view NUMBER --repo OWNER/REPO --json title,state,labels,assignees,body,comments
```

### 2.2 Create / Update Issues

```bash
# Create
gh issue create --repo OWNER/REPO \
  --title "Issue title" \
  --body "Description" \
  --label "bug" \
  --assignee @me

# Close
gh issue close NUMBER --repo OWNER/REPO --comment "Fixed in #XXX"

# Reopen
gh issue reopen NUMBER --repo OWNER/REPO

# Add comment
gh issue comment NUMBER --repo OWNER/REPO --body "This is a comment"

# Add labels (note: replace not append — use gh api for additive labels)
gh issue edit NUMBER --repo OWNER/REPO --add-label "wontfix"

# Remove label
gh issue edit NUMBER --repo OWNER/REPO --remove-label "bug"

# Change assignee
gh issue edit NUMBER --repo OWNER/REPO --add-assignee "@me"

# Edit title/body
gh issue edit NUMBER --repo OWNER/REPO --title "New title" --body "New body"
```

### 2.3 Bulk Operations

```bash
# Bulk close issues matching label (figlet-style)
gh issue list --repo OWNER/REPO --label "stale" --json number \
  | gh issue close --repo OWNER/REPO --comment "Closing stale issue" -R OWNER/REPO --id -
```

---

## 3. Repository Management

### 3.1 View / Search Repos

```bash
# View repo info
gh repo view OWNER/REPO --json name,owner,description,isFork,parent,forkCount,defaultBranch,createdAt

# View fork parent
gh repo view OWNER/REPO --json parent

# List your repos
gh repo list OWNER --limit 50 --json name,isFork,description

# Search repos
gh search repos "keyword" --owner OWNER --limit 20

# Get remote URL
gh repo view OWNER/REPO --json url,sshUrl
```

### 3.2 Create / Fork / Template

```bash
# Create repo
gh repo create REPO_NAME --public --description "Description"

# Create repo in org
gh repo create ORG/REPO_NAME --public --description "Desc"

# Create from template
gh repo create NEW_REPO --template OWNER/TEMPLATE_REPO --public

# Fork a repo
gh repo fork OWNER/REPO --clone
```

### 3.3 Branch Protection / Topics

```bash
# View branch protection (via API — gh doesn't have native branch protection commands)
gh api "repos/OWNER/REPO/branches/main/protection"

# Enable branch protection
gh api "repos/OWNER/REPO/branches/main/protection" \
  --method PUT \
  --input - <<< '{"required_status_checks":{"strict":true,"contexts":[]},"enforce_admins":true,"required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1},"restrictions":null}'

# Set topics
gh api "repos/OWNER/REPO/topics" \
  --method PUT \
  -f names='["topic1","topic2","topic3"]'
```

### 3.4 Secrets

```bash
# Get public key for a repo
gh api "repos/OWNER/REPO/actions/secrets/public-key" --jq '{key_id,key}'

# Set a secret (requires libsodium)
gh api "repos/OWNER/REPO/actions/secrets/MY_SECRET" \
  --method PUT \
  -f encrypted_value="BASE64_ENCRYPTED" \
  -f key_id="KEY_ID"

# List secrets
gh api "repos/OWNER/REPO/actions/secrets"
```

---

## 4. Releases

```bash
# List releases
gh release list --repo OWNER/REPO --limit 10

# View release
gh release view TAG --repo OWNER/REPO --json tagName,name,body,assets

# Create release
gh release create TAG --repo OWNER/REPO \
  --title "v1.0.0" \
  --notes "Release notes" \
  path/to/asset.tar.gz

# Upload asset to existing release
gh release upload TAG path/to/asset --repo OWNER/REPO

# Download release asset
gh release download TAG --repo OWNER/REPO --pattern "*.tar.gz"
```

---

## 5. Gists

```bash
# Create gist
gh gist create path/to/file.py --desc "Description" --public

# List gists
gh gist list --limit 20

# View gist
gh gist view GIST_ID

# Edit gist
gh gist edit GIST_ID path/to/file.py
```

---

## 6. Authentication & Config

```bash
# Check auth status
gh auth status

# View current user
gh api user --jq '.login'

# Refresh token scopes
gh auth refresh -h github.com

# List configured hosts
gh config list -h github.com
```

---

## 7. Workflows & Actions

```bash
# List workflows
gh workflow list --repo OWNER/REPO

# List runs for a workflow
gh run list --repo OWNER/REPO --workflow WORKFLOW_NAME --limit 10

# View run
gh run view RUN_ID --repo OWNER/REPO

# View failed logs
gh run view RUN_ID --repo OWNER/REPO --log-failed

# Re-run
gh run rerun RUN_ID --repo OWNER/REPO

# Re-run failed jobs only
gh run rerun RUN_ID --repo OWNER/REPO --failed

# Dispatch workflow
gh workflow run workflow.yml --repo OWNER/REPO --ref main -f param=value

# Cancel run
gh run cancel RUN_ID --repo OWNER/REPO
```

---

## 8. Code Review Workflow

Full end-to-end PR review process using gh exclusively:

### Step 1: Gather PR context

```bash
# PR summary
gh pr view $PR --repo $REPO

# Changed files list
gh pr diff $PR --repo $REPO --name-only

# PR details as JSON
gh pr view $PR --repo $REPO --json title,body,additions,deletions,changedFiles,reviews,comments
```

### Step 2: Check out locally

```bash
gh pr checkout $PR --repo $REPO
```

### Step 3: Read the diff

```bash
gh pr diff $PR --repo $REPO
```

### Step 4: Inspect files

Use `read_file` on each changed file for full context around the diff.

### Step 5: Check CI

```bash
gh pr checks $PR --repo $REPO
gh run list --repo $REPO --branch $(gh pr view $PR --repo $REPO --json headRefName --jq '.headRefName')
```

### Step 6: Post review

```bash
# Approve
gh pr review $PR --repo $REPO --approve --body "Reviewed. Clean code, good tests."

# Request changes — with inline comments via gh api
HEAD_SHA=$(gh pr view $PR --repo $REPO --json headRefOid --jq '.headRefOid')
gh pr review $PR --repo $REPO --request-changes --body "Found issues — see inline comments."
gh api "repos/$REPO/pulls/$PR/comments" \
  --method POST \
  -f body="Fix this" \
  -f path="src/file.py" \
  -f commit_id="$HEAD_SHA" \
  -f line=42 \
  -f side="RIGHT"
```

### Step 7: Clean up

```bash
git checkout main
git branch -D pr-$PR 2>/dev/null
```

---

## 9. Token Efficiency Comparison

| Operation | curl (tokens) | gh (tokens) | Savings |
|-----------|:---:|:---:|:---:|
| PR list | `curl -s -H "Authorization: token \$GITHUB_TOKEN" https://api.github.com/repos/\$OWNER/\$REPO/pulls` | `gh pr list --repo \$REPO` | ~65% |
| PR view (JSON) | curl + python3 parse | `gh pr view --json ... --jq ...` | ~70% |
| Create PR | curl POST + python body | `gh pr create --title "..."` | ~75% |
| Auth setup | 3-5 lines token resolution + curl | `gh auth status` | ~80% |
| Issue comment | curl POST + auth header + URL | `gh issue comment -b "..."` | ~80% |

---

## 10. Verification / Health Check

Run this single command to verify everything is operational:

```bash
source /opt/data/.config/github/env.sh 2>/dev/null; \
echo "=== gh binary ===" && command -v gh && gh --version && \
echo "=== auth ===" && gh auth status -h github.com && \
echo "=== API ===" && gh api rate_limit --jq '.rate.remaining' | xargs echo "API calls remaining:" && \
echo "=== repos ===" && gh repo view 5L-hermes01/agent-skills --json name,isFork,parent && \
echo "=== PR access ===" && gh pr list --repo 5L-Labs/agent-skills --limit 3 --json number,title,state && \
echo "ALL GREEN"
```

### What each step tests

| Step | Tests | Failure mode |
|------|-------|-------------|
| `command -v gh` | Binary exists in PATH | gh not installed → run 0.1 |
| `gh auth status` | Token valid & config readable | Needs auth → run 0.2 |
| `gh api rate_limit` | API credentials work | Token expired or revoked |
| `gh repo view ...` | Can read our repos | Token scope too narrow |
| `gh pr list ...` | Can access PR endpoints | Missing `repo` scope |

### Common failure modes & fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `gh: command not found` | Binary missing or PATH wrong | `source /opt/data/.config/github/env.sh` or run section 0.1 |
| `You are not logged into any GitHub hosts` | `GH_CONFIG_DIR` not set or hosts.yml missing | `source env.sh` then section 0.2 |
| `error validating token: missing required scope 'read:org'` | Token doesn't have org scope | This is a WARNING — most operations still work. Ignore unless you need org access. |
| `Not Found (404)` on repo or PR | Token scope doesn't include the repo | Check token has `repo` scope |
| `401 Bad credentials` | Token expired or revoked | Update PAT in `/opt/data/config/github/.pat` and `/opt/data/home/.git-credentials` |

### Enforcement: how we guarantee gh over curl

The `github` skill is the ONLY authorized path for GitHub operations. Here's how we enforce that:

1. **Skill-level** — this SKILL.md's header states "NEVER use raw curl." The skill description is checked by `skill_view` before any session runs GitHub operations.
2. **Memory** — the persistent memory entry says "ALL GitHub API calls use gh CLI (never raw curl). Load the `github` skill for any GitHub op."
3. **Audit trail** — the existing `github/github-auth`, `github/github-code-review`, `github/github-pr-workflow`, `github/github-issues`, `github/github-repo-management` skills are flagged as "contains curl — should be migrated to gh."
4. **Self-test** — this verification section. Run it after any container rebuild to confirm gh is operational. If it fails, gh is broken and curl is the fallback (which will be caught and flagged as tech debt in the next session).

- **GH_CONFIG_DIR** must be set — gh defaults to `~/.config/gh/` which may not resolve to `/opt/data/.config/gh/` depending on `$HOME`.
- **Inline comments** still need `gh api` (no native `gh pr review --inline` flag). But `gh api` is still more concise than raw curl — no auth header, shorter URL.
- **gh auth login** validates token scopes strictly. If the token lacks `read:org`, write `hosts.yml` manually instead of running `gh auth login`.
- **gh merge** without `--squash`/`--rebase`/`--merge` will prompt interactively. Always specify the merge method.
- **Labels**: `gh issue edit --add-label` only appends. There's no native remove+add in one command.
- **Secrets**: gh doesn't natively support encryption (libsodium). Use `gh api` or the GitHub CLI extension `gh secret set`.
- **Token saved at**: `/opt/data/config/github/.pat` and `/opt/data/home/.git-credentials`
- **Auth config**: `/opt/data/.config/gh/hosts.yml`
- **PATH**: gh is at `/opt/data/.local/bin/gh` — add to PATH with `export PATH="/opt/data/.local/bin:$PATH"`
- **After creating this skill**: the existing `github/github-auth`, `github/github-code-review`, `github/github-pr-workflow`, `github/github-issues`, `github/github-repo-management`, `github/github-auto-merge-workflow` skills still contain curl-based commands. This skill is the replacement — future edits to those skills should replace curl blocks with their `gh` equivalents from this reference.
