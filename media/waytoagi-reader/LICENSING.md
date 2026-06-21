# Licensing notes

This skill is Apache-2.0 (see `LICENSE`).

## Why the test fixtures are synthetic

The WaytoAGI Feishu wiki is a community knowledge base with no explicit content license advertised in the footer. Absent a clear permissive grant, we treat the content as all-rights-reserved and do **not** snapshot real entries into the repo, even for tests.

All test fixtures in `tests/` use fabricated Chinese strings, fabricated dates, and fabricated document tokens. They exercise the parser shape, not real content.

If WaytoAGI maintainers later publish a permissive content license (CC-BY etc.), we can revisit and include a small snapshot for richer regression coverage.

## What the skill does at runtime

The skill makes HTTP requests to `waytoagi.feishu.cn` on behalf of the user and renders the response as JSON. It does not republish, redistribute, or persist WaytoAGI content beyond the user's own cache directory.
