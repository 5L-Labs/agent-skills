# Stub Recovery Notes (2026-05-19 session)

## IP-block env-constant

Confirmed 2026-05-19: `fetch_transcript.py` (youtube-transcript-api) and `yt-dlp` both
return `SSLEOFError(UNEXPECTED_EOF_WHILE_READING)` in under 1 s. Verified against
`dQw4w9WgXcQ` and `jNQXAC9IVRw`. No client library can bypass. The only recovery paths are:

1. Fulltext ≥ 5 KB from a previous non-cloud fetch (saved to `youtube-raw/` earlier)
2. Partial stub bytes (500 B+) — full transcripts written before the IP block dropped
3. Chapter outline stubs (corrupted timestamps from partial-write instrumentation)

## Stub hierarchy observed in 2026-05-19 run (109 raw dir entries)

| Type | Count | Key | Action |
|---|---|---|---|
| 0-B with confirmed_permanent | 29 | `_meta.json` has `segments=0, fetch_error` | skip; logged in yt-backlog.json failed_videos |
| Fulltext ≥ 500 B + segs falsy | 22 | partial cached body text re-segmentable | inline re-segmentation (no hard upper bound on fulltext size) |
| Chapters preserved ([M:SS] Title) | 3 | TZGVB6L_2Eo, rTuU8FUlIvY | re-segment with meta patch |
| Minutes wrap in timestamps | 4 (session 2026-05-19) | z6XWYCM3Q8s, sVo7SC62voA, A2P3Q3LCoLw, +1 confirmed | use `compute_duration_with_wraps()`, not `last_sec + N` |
| Corrupted timestamps (:-N offset) | 1 | tIVKgztDaYQ | strip `:-\d+` before parsing |
| Already ≥ 5 KB, segs=positive | 40 | not a target | skip |

## Duration correction for minute-wrapping transcripts (verified 2026-05-19)

Pad-zero `MM:SS` transcripts used by long videos/podcasts loop every 60 minutes.
The naive formula `last_timestamp_seconds + 30` produces `~60 s` for a one-hour
loop even when the real duration is `~3,600 s` or more.

**Correct algorithm**: iterate the ordered timestamp minute values in sequence;
whenever the current minute < previous minute, add 3600 s per wrap. Count wraps
by detecting strictly-decreasing minute pairs and adding one+ hour per event.

Affected videos in 2026-05-19 run: `z6XWYCM3Q8s` (2,878 segs, 3,729 s = 62 min
not 2 min), `sVo7SC62voA` (1,960 segs, 3,704 s = 61 min), `A2P3Q3LCoLw` (1,986
segs, 3,694 s = 61 min). Implementation: `compute_duration_with_wraps()` in
`references/inline-resegmentation-fallback.md`.

## recover_stubs.py behaviour on tIVKgztDaYQ-stubs

Lines like `02:13:-7847 Genesis of Speak…` in the cached fulltext are parsed
by the CORRUPT_PATTERN regex — `:-7847` stripped before timestamp extraction.
Result: chapter at 133 s with title `Genesis of Speak…`. The original fulltext
is preserved as-is; `source=COHERENT_FULLTEXT_RESEQUENCED` is set in meta.

## Bracket regex `\b` pitfall (verified 2026-05-19)

A regex like `r'^\[(\d{1,2}:\d{2})\] ...'` **silently fails** on lines with
`[0:00]`-style bracketed timestamps when `\b` appears anywhere between the
digits and `]` or `:`. The anchor `\b` is non-matching between a digit and
non-word characters `]:`, so it absorbs the boundary and the pattern still
matches  – but if placed explicitly before `]`, some Python/RE2 engines may
reject it as an invalid word-boundary position.

The safe form is `r'^\[(\d{1,2}:\d{2})(?:]|\s|:|$)'` — replace `\b` with
`(?:]|\s|:|$)` to cover all legal terminators without a word-boundary assertion.

Observed impact: when `\b` blocked `[MM:SS]` matching, all [MM:SS]-format videos
in a batch of 10 reported `segments=0` and `duration=0` until the regex was fixed.

## New stub variant: entries in `unique_videos` with zero raw files (2026-05-19 session)

Two videos processed in the current run were found with `segments=0` error stubs but
**zero-byte** `_fulltext.txt` / `_transcript.txt` (or the files missing entirely):

| Video ID | Situation |
|---|---|
| `botHQ7u6-Jk` | `unique_videos` + `failed_videos` (IP-block); no raw files on disk |
| `yYZBd25rl4Q` | `failed_videos` only (`blocked_recheck`); not in `unique_videos`; no raw files |

Both were attempted live-fetch (confirmed `[SSL: UNEXPECTED_EOF_WHILE_READING]`,
env-constant IP block), then stub-wrapped:

```
youtube-raw/{ID}_fulltext.txt       0 B   (empty placeholder)
youtube-raw/{ID}_transcript.txt     0 B   (empty placeholder)
youtube-raw/{ID}_meta.json          ~305 B (segments=0, source=ip_block_fallback)
youtube-raw/{ID}_error.txt          ~175 B (block note + UTC)
```

**Decision table for this stub variant:**

| video in `unique_videos` | video in `failed_videos` | raw files exist? | required action |
|---|---|---|---|
| ✅ Yes | — | No / both 0 B | live fetch → write stub → files already logged |
| ✅ Yes | ✅ Yes | No / both 0 B | live fetch → write stub; skip adding to `unique_videos` (already there) |
| ❌ No | ✅ Yes | No / both 0 B | live fetch → write stub → add to `unique_videos` (failed, not previously acknowledged) |

This fixes a subtle state: `yt-backlog.json` must always list every video that has
been attempted, even when raw files are empty. Without the `unique_videos` entry the
video looks like a brand-new candidate in the next funnel scan and fetch will be
re-attempted again (and fail) without any visible progress record.

## Latent backlog state

When `yt-latent-space-backlog.txt` reaches a state where every non-empty line
ends in `DONE`, there is no queue to consume. The fallback is scanning
`youtube-raw/` for `{segments falsy, fulltext >= 500 B}` entries — there is
no upper size bound. Build the candidate list dynamically. Do NOT re-read
`batch_fetch_candidates.py` as the sole source of truth when it shows 0 results,

**New edge: no re-segmentation candidates AND no 0B stubs in unique_videos → QUIET RUN.**
If the inline scan produces zero eligible candidates and no "unfilled unique_videos
entries" remain, the queue is genuinely exhausted. Report success count=0 and skip
the fetch attempt step entirely. Do NOT fabricate work.
