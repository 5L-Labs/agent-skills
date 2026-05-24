---
name: jargon
description: Jargon detection, classification, and bi-directional translation pipeline. Extracts domain-specific acronyms/terms from text, classifies by theme and sophistication level, translates bidirectionally between levels. Uses local Ollama models (qwen2.5:7b default, qwen3.6:27b heavy). Themes loaded at runtime from unified-digest-themes.
version: 1.0.1
author: Hermes Agent
metadata:
  hermes:
    tags: [jargon, classification, nlp, translation, ollama]
    related_skills: [unified-digest-themes, x-digest, entities]
---

# Jargon Skill

## What Is Jargon

Jargon = domain-specific words (usually acronyms) that carry precise meaning for experts but are opaque to outsiders. Examples: DPO, GRPO, Mamba-2, LoRA, MoE, HBM, AGI.

This skill does NOT classify common tech words (API, GPU, CPU, app, code, data, server, cloud, web, email) or common abbreviations (vs, eg, ie, etc).

## Models

All inference runs on local Ollama at `http://host.containers.internal:11434`. CPU only — no GPU available.

| Mode | Model | Params | Latency | Use Case |
|------|-------|--------|---------|----------|
| Default (fast) | `qwen2.5:7b` | 7.6B | ~10-60s per chunk | Daily digest classification |
| `--heavy` | `qwen3.6:27b` | 27.8B | ~5-10 min | Deeper analysis, batch jobs |

**Endpoint:** `/api/generate` for classification (handles Qwen thinking models correctly).  
**Why not `/v1/chat/completions`:** Qwen thinking models (qwen3.x family) output their reasoning in a `reasoning` field and may truncate the real answer. The `/api/generate` endpoint returns both `thinking` and `response` fields cleanly.  
**Why not qwen3:4b/qwen3.5:4b:** These are thinking models — they consume 3000+ tokens just on reasoning before any output, making them impractical for CPU. qwen2.5:7b has no thinking mode and is faster despite being larger.

## Scripts

All scripts at `scripts/`. Dependencies: stdlib only (urllib, json, argparse, subprocess).

| Script | Purpose |
|--------|---------|
| `classify.py` | Single-text classification. Reads text, calls Ollama, updates registry. |
| `decode.py` | Translate a jargon term to plainspeak at target level. |
| `encode.py` | Reverse lookup: find jargon term from plainspeak description. |
| `ingest.py` | Bulk pipeline: chunk long text, classify each chunk, merge into registry. |
| `backfill-levels.py` | Add new sophistication levels to existing registry terms. |

### classify.py

```
python3 scripts/classify.py --text "DPO and GRPO are SOTA for RLHF" --source "@karpathy"
python3 scripts/classify.py --file /tmp/digest.txt --source "X:AI High Signal" --verbose
python3 scripts/classify.py --file /tmp/digest.txt --dry-run    # Don't save
python3 scripts/classify.py --file /tmp/deep.txt --heavy         # Use 27B model
```

Returns JSON with `jargon_terms[]`, `new`, `updated`, `total_terms_in_registry`.

### ingest.py (preferred for digests)

```
python3 scripts/ingest.py --file /tmp/tweets.txt --source "X:AI High Signal" --max-chars 4000
python3 scripts/ingest.py --file /tmp/deep.txt --heavy
cat /tmp/tweets.txt | python3 scripts/ingest.py
```

Chunks text at `--max-chars` (default 5000), runs classify on each, merges results.

### decode.py

```
python3 scripts/decode.py --term "DPO" --target-level "kindergarten"
python3 scripts/decode.py --term "LoRA" --list-levels            # Show available levels
python3 scripts/decode.py --term "UnknownTerm" --heavy           # LLM fallback
```

Registry lookup first; falls back to LLM if term not found.

### encode.py

```
python3 scripts/encode.py --description "comparing two outputs to train AI preferences"
python3 scripts/encode.py --description "quantized model format" --theme "Developer Tools"
```

Keyword-matches against registry plainspeak; falls back to LLM.

## Data Model

Registry at `jargon-registry.json`:

```json
{
  "config": {
    "version": 1,
    "default_levels": ["doctor", "lawyer", "high-school", "kindergarten"]
  },
  "terms": {
    "AGI": {
      "theme": "AI & ML Research",
      "source_level": "doctor",
      "plainspeak": {
        "doctor": "Artificial General Intelligence...",
        "kindergarten": "Really smart computer..."
      },
      "first_seen": "2026-05-23T16:19:00Z",
      "last_seen": "2026-05-23T16:19:00Z",
      "seen_count": 1,
      "sources": [{"author": "X:AI High Signal", "date": "2026-05-23"}]
    }
  }
}
```

## Theme Loading

Themes are loaded from the `unified-digest-themes` skill at runtime, cached to `references/themes-cache.json`. The cache expires daily. Refresh by calling:

```
skill_view('unified-digest-themes')
```

Then the next classify/ingest run picks up the fresh themes. The scripts read the cache file directly — the agent must refresh it via `skill_view`.

## Quality & Known Issues

### Noise Filtering (Important)
The 7B model sometimes classifies non-jargon as jargon:
- **Company names** (fal, Modal, Cerebras — misclassified as jargon when they're proper nouns)
- **Product features** (goal mode, Appshots — feature names, not domain terms)
- **Common words used in context** (reconciliation, extraction, retrieval)
- **Over-eager acronym detection** (xAI classified as Security jargon)

**Mitigation:** Post-process the output. The `source_level` field being a dict (instead of a string) is a signal that the model is confused about the term. Noise terms should be deleted from the registry.

### malformed JSON from LLM
The model occasionally returns `source_level` as a dict of `{level: description}` instead of a string. This happens when the model thinks the term itself IS the level description. The classify.py does not validate this — check the registry after each run and fix any entries where `source_level` is a dict.

### Chunking
- Default chunk: 5000 chars (classify.py hardcoded limit at `text[:6000]`)
- Each chunk takes ~10-60s on qwen2.5:7b depending on how many terms are found
- A 10K char digest = 2-3 chunks = ~30-180s total
- Use `--max-chars 4000` in ingest.py if timeouts occur

## Integration with Digest Skills

The `x-digest` skill calls ingest at Step 1.5. Any future digest skill (hn-brief, arxiv, weekly AI news) should add a similar step after fetching content:

```bash
python3 scripts/ingest.py \
  --file /tmp/raw_content.txt \
  --source "HN Brief:2026-05-23" \
  --max-chars 4000
```

This is a fire-and-forget step — failures should not block the digest itself.

## Agent Speech Level Configuration

Configure per agent/profile in config.yaml:

```yaml
jargon:
  speaking_level: high-school
  expert_themes: [AI & ML Research]
```

Not yet implemented in the agent runtime — this is the future design. The decode.py script provides the building block.

## Pitfalls

- Always run classification BEFORE writing digest prose — you need the raw text
- Theme cache expires daily. If `unified-digest-themes` was updated, delete `references/themes-cache.json` and re-run `skill_view()`
- Empty classification output means the model ran out of tokens during thinking — increase `FAST_PREDICT` (classify.py) or use `--heavy` with the 27B model
- The 27B model (qwen3.6:27b) generates 15000+ chars of thinking before answering. Allocate 600s+ timeout
- Do NOT use `qwen3:4b` or `qwen3.5:4b` for classification — they are thinking models that consume all tokens on reasoning
- If Ollama is down, all scripts fail with connection errors. Check `curl http://host.containers.internal:11434/api/tags`
- Chunk 2+ may miss cross-chunk context — terms spanning chunk boundaries are classified independently
- The `entities` skill (people/places/things) is a separate fork with different classification — do not cross-pollinate registries