# Large PR Review — Parallel Subagent Workflow

Use this when reviewing PRs with 10+ files or 500+ lines. Reading the full diff inline wastes context — split across subagents instead.

## Signal: When to use parallel delegation

| Metric | Threshold | Why |
|--------|-----------|-----|
| Files changed | 10+ | Agent can't hold all file contexts simultaneously |
| Diff lines | 500+ | Full diff exceeds context window for deep reasoning |
| Skills/features | 2+ distinct modules | Each module needs different domain expertise |
| Diff size | `gh pr diff --name-only` shows unrelated paths | Natural split points exist |

## Workflow

### 1. Get the overview

```bash
# Understand scope before splitting
gh pr view $PR --repo $REPO --json title,body,additions,deletions,changedFiles,headRefName
gh pr diff $PR --repo $REPO --name-only
```

### 2. Identify natural split points

Group changed files by:
- **Skill/module** — each `media/waytoagi-reader/` and `media/translate/` gets its own reviewer
- **Layer** — backend vs frontend, source vs tests, docs vs code
- **Concern** — security changes, dependency bumps, feature work, refactoring

### 3. Delegate to parallel subagents

Use `delegate_task` with `tasks=[...]` (up to 3 concurrent per user config).

Each subagent needs:
- **Goal**: "Review the [module] skill in PR #N on [org/repo]"
- **Context**: The relevant diff slice + the review checklist from Section 8 of this skill
- **Toolsets**: `["terminal", "file"]` (for fetching the diff and reading files)

Example structure:

```python
delegate_task(
    tasks=[
        {
            "goal": "Review module A in PR #50...",
            "context": "Focus on correctness, security, code quality...",
            "toolsets": ["terminal", "file"]
        },
        {
            "goal": "Review module B in PR #50...",
            "context": "Focus on architecture, test coverage...",
            "toolsets": ["terminal", "file"]
        }
    ]
)
```

### 4. Synthesize results

Each subagent returns a structured review. Synthesize into a unified comment:
- Group findings that apply to both modules under cross-cutting concerns
- Keep module-specific findings in their own section
- Flag contradictions between reviewers (rare, but catch them)
- Apply consistent severity labels (Critical / Warning / Suggestion / Looks Good)

### 5. Post review

```bash
gh pr comment $PR --repo $REPO --body "## Review: PR #N\n\n...synthesized content..."
```

### 6. Request AI tool reviews

```bash
gh pr comment $PR --repo $REPO --body "Can we get a review pass from cubic and CodeRabbit on this? /review"
```

## Pitfalls

- **Subagents have no memory of your conversation** — pass all context (diff slice, file paths, constraints) in the `context` field
- **Subagent summaries are self-reports** — verify claims if they make strong assertions about code behavior
- **Nested delegation is OFF** (max_spawn_depth=1) — subagents are leaf workers, they cannot spawn their own subagents
- **3 concurrent subagent limit** — for very large PRs with 4+ modules, run in batches
- **Race conditions** — subagents may report contradictory findings. The synthesis step resolves these
- **PR diff may change** while subagents are reviewing — use the PR HEAD SHA in context to pin the review version
