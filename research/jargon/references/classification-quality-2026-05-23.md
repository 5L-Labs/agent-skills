# Classification Quality Report

Based on real test run: 60 tweets (10.8K chars) from X:AI High Signal, classified with qwen2.5:7b.

## Hit Rate

- **14 clean terms** extracted from 60 tweets
- **2 noise terms** filtered post-hoc (reconciliation, fal) = ~12% noise
- **3 borderline** company-name terms (Cerebras models, Command A+) kept because they have legitimate domain meaning

## Terms Found

### Correct (14)
AGI, HBM, Appshots, Command A+, W4A4 quantization, Cerebras models, NEO-unify, LoRA, Mixture-of-Experts (MoE), vector search, production retrieval systems, gemini API, Issue Triage Agent, Mix-Quant

### Noise Removed (2)
- **reconciliation**: Standard English word used in a data context. Not jargon.
- **fal**: Company name (FAL.ai). Should not be classified as jargon.

### Previously Removed (from earlier run with lower token limits)
- **fal Assets**: Product name within FAL ecosystem. Not domain jargon.
- **fal Sandbox**: Product name. Same issue.
- **Modal**: Company name. Not jargon.
- **goal mode**: Codex product feature. Not domain jargon.
- **EpochAI**: Research org name. Borderline — kept in earlier run but removed on review.
- **xAI**: Company name misclassified as "Security & Privacy" jargon.

## Theme Distribution

| Theme | Terms | Notes |
|-------|-------|-------|
| AI & ML Research | 7 | AGI, LoRA, MoE, NEO-unify, Mix-Quant, vector search, retrieval systems |
| Developer Tools | 5 | Appshots, Command A+, W4A4 quantization, gemini API, Triage Agent |
| Hardware & IoT | 2 | HBM, Cerebras models |

## Model Performance

| Metric | Value |
|--------|-------|
| Chunks | 3 (5K chars each) |
| Total time | ~60 seconds |
| Time per chunk | ~20s average |
| Tokens generated per call | ~200-600 |
| JSON parse failures | 1 (chunk 2 truncated at 2000 tok limit — fixed by raising to 4000) |
| Malformed source_level entries | 2 (dict instead of string — both in noise terms, not clean terms) |

## Noise Patterns (qwen2.5:7b Failure Modes)

1. **Company names → jargon**: FAL, Modal, Cerebras, xAI all identified when they're proper nouns
2. **Product features → jargon**: "goal mode", "Appshots", "fal Sandbox" treated as domain terms
3. **Acronym over-detection**: Anything in ALL-CAPS gets flagged even if standard English
4. **source_level as dict**: When model is confused, it outputs `source_level: {doctor: "...", lawyer: "..."}` instead of a string. This is a reliable signal of a bad classification — if source_level is a dict, the term is probably noise.

## Recommendations

- Post-process every run: check for `source_level` being a dict → delete
- The noise terms tend to come from chunk boundaries where context is thin
- For tweet digests, the noise rate is ~10-15% — acceptable for a fire-and-forget pipeline
- Consider a company-name filter list for future versions