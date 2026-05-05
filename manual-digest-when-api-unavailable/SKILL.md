---
name: manual-digest-when-api-unavailable
description: Create a plain-text digest in Luna style when X/Twitter API is unavailable, using work-queue items and historical context.
category: productivity
---

When the X API returns 401/400 and token refresh fails, follow this workflow to produce a digest manually:

1. Read the work-queue file (/opt/data/home/.hermes/work-queue.md) for pending items related to tweet digests or xlinks summaries.
2. Review recent conversation history for user preferences: plain text, no markdown headers, no emoji, conversational tone, raw tweet links at the end, thematic sections.
3. Extract themes from the work-queue items and any available context (e.g., list IDs, account names).
4. Write a digest in plain text:
   - Start with a brief conversational lead-in.
   - Use bullet-point indentation (e.g., " - ") for items.
   - Group items into thematic sections (e.g., Models & benchmarks, ML research, Infrastructure & compute).
   - Do not use bold, as the user prefers plain text without any formatting.
   - End with a section "Raw links:" and list any tweet URLs referenced.
5. Save the digest to a temporary file (e.g., /tmp/manual_digest.txt).
6. Instruct the user to paste the digest into the target channel (Discord/Mattermost) or, if API access is restored, use the normal x-digest skill.

Pitfalls:
- Without API access, you cannot fetch new tweets; rely on queued work items and historical notes.
- Ensure the digest matches the user's current plain-text preference (verify via memory or recent instructions).
- Do not include markdown headers or emoji dividers unless explicitly allowed.

Verification:
- Check that the output contains no markdown header lines (lines starting with #).
- Check that there are no emoji characters.
- Confirm raw links are present at the end if any were referenced.