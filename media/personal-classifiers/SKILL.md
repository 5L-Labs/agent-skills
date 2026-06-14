---
name: personal-classifiers
description: "Three classifiers (level-of-understanding, state-of-the-world, novelty-for-me) for tagging all data sources. Iteratively developed, versioned in git."
version: 1.0.0
author: Hermes Agent 01
---

# Personal Classifiers

Three classifiers that tag every piece of data flowing through the digest pipeline.
The goal is to answer three questions for every item:

1. **Level of Understanding** — How much does the reader need to know already?
2. **State of the World** — What's the broader context this item fits into?
3. **Novelty-for-Me** — How new is this information to the user personally?

## The Three Axes

### 1. Level of Understanding (LoU)

How much domain expertise is needed to get value from this item.

| Level | Label | Meaning | Treatment |
|-------|-------|---------|-----------|
| 1 | General Audience | No technical background needed. Mainstream news, culture, broad concepts. | Full context + explanations |
| 2 | Curious Observer | Some tech literacy. Needs definitions and guardrails. | Explain what matters and why |
| 3 | Practitioner | Working knowledge of the domain. Show the context, then the delta. | Medium handholding |
| 4 | Expert | Deep domain expertise. Just show what changed. | Delta only, skip the primer |
| 5 | Researcher | Frontier knowledge. Raw findings, papers, code, benchmarks. | Minimal framing, raw signal |

**Default assignment heuristics (when no prior signal exists):**
- Link to paper/code → Level 5
- Uses 3+ jargon terms → Level 4
- Uses 1-2 jargon terms → Level 3
- General news/policy/culture → Level 1-2

### 2. State of the World (SotW)

Where does this item sit in the lifecycle of its domain?

| State | Meaning | Example |
|-------|---------|---------|
| emerging | New trend/tech just appearing. Signal is weak. | First paper in a new direction |
| active_development | Rapidly evolving, many players, weekly changes. | LLM benchmarks, agent frameworks |
| mature | Established, well-understood, incremental. | Kubernetes, React, Python |
| disrupting | Something is changing the landscape. | Open-weight models competing with closed |
| regulatory | Laws, rules, governance catching up. | EU AI Act, export controls |
| deploying | Moving from research to production. | Product launches, API releases |
| speculative | Theoretical, not yet validated. | AGI timelines, alignment theory |

### 3. Novelty-for-Me (NfM)

How new is this to the user specifically?

| Level | Label | Meaning | Action |
|-------|-------|---------|--------|
| 1 | known_stale | Already seen or understood. Don't re-surface. | Filter out |
| 2 | incremental | Small update on something familiar. Low urgency. | Digest summary |
| 3 | notable | Worth a scan. May be useful. | Surface in daily digest |
| 4 | novel | New development. Deserves attention. | Highlight in digest |
| 5 | breakthrough | Major shift. Immediate attention. | Priority alert |

**Novelty decay:** Each time a concept appears in a digest without the user engaging with it, NfM drops by 1. When NfM hits 1, the concept stops being surfaced for that topic until the user explicitly marks it interesting again.

**Novelty override:** User can manually set a `novelty_override` on any term (e.g. "I've seen enough RLHF content, mark it NfM=1 even though it's new to the system").

## Registry Format

Single file: `references/classifier-registry.json`

```json
{
  "version": 1,
  "last_updated": "2026-06-14T18:00:00Z",
  "terms": {
    "Cohere Command A+": {
      "level_of_understanding": 3,
      "state_of_the_world": "deploying",
      "novelty_for_me": 3,
      "first_seen": "2026-05-20",
      "last_seen": "2026-06-14",
      "seen_in": ["x:2066071673359524014", "x:2057120818551734589"],
      "notes": "Major open-weight release, LoU 3 because it needs ML context"
    }
  },
  "items": {}
}
```

Each item gets stored keyed by its source+ID, with assigned LoU/SotW/NfM and the matched terms.

## Classification Pipeline

```
Input (title + description/body + source + URL)
  → Scan text against known terms in registry
  → For each matched term, inherit its LoU/SotW/NfM
  → Aggregate:
    - LoU = max of matched term LoU (hardest term wins)
    - SotW = most common SotW among matched terms
    - NfM = highest NfM among matched terms, decayed by time since last seen
  → If no term matches, use heuristics (jargon density, source type, URL depth)
  → Store result in items section
  → Update last_seen on matched terms
```

## Iterative Development Process

1. Seed initial terms from existing data (jargon registry topics, digest themes)
2. Run a test batch (50 items from cache) → surface to user for review
3. User corrects misclassifications → update registry
4. Re-run batch with corrections → commit to git
5. Repeat until classification quality is acceptable
6. Add more terms, refine existing ones
7. Eventually wire into digest pipeline for automatic tagging on ingest

## Data Sources to Classify (Regressively)

| Source | Items | Cache Location |
|--------|-------|----------------|
| YouTube playlists | 275 video descriptions | `/opt/data/content/playlists/cache/video_metadata.json` |
| X/Twitter digests | ~46/day | cron digest output |
| HN Brief | ~30/day | `/opt/data/cache/hn-brief/` |
| arXiv papers | ~10/day | cron digest output |
| AI News (smol.ai) | ~5/day | cron digest output |

All items get classified retroactively when the pipeline runs.
