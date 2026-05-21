# Blocked / Recheck Video Lifecycle

This reference documents the three failure tiers that `yt-backlog.json` uses to route YouTube transcript videos that couldn’t be fetched live.

## Failure statuses in `failed_videos`

| Status | Meaning | Next action |
|--------|---------|-------------|
| `confirmed_permanent` | Video has no subtitles, transcript disabled, or transcr… failed irrecoverably. Do NOT retry. | Skip forever. |
| `cloud_ip_blocked` | YouTube returned SSLEOFError / IP blocked; fetch failed but a home-cache transcript *might* exist somewhere. | Put in `blocked_recheck_pool`. Retry when node is off-cloud. |
| `blocked_recheck` | Was `cloud_ip_blocked` but is eligible for periodic re-check. Move back to the active selection pool every N cron runs. | Attempt fulltext recovery first (see below), then live fetch. Promote to `confirmed_permanent` if still blocked; go to `cloud_ip_blocked` if recovery succeeded. |

## Fulltext recovery check order

Before any live fetch attempt for a `blocked_recheck` video, scan in this order:

1. `/opt/data/content/youtube-raw/{ID}_transcript.txt` — already has a good transcript (`≥ 500 B`)? → skip, mark DONE in playlist.
2. `/opt/data/home/.hermes/content/youtube-raw/{ID}_transcript.txt` — home cache hit? → `shutil.copy2()` to prod raw dir.
3. `/opt/data/content/youtube-raw/{ID}_fulltext.txt` — chapter/heading stubs from prior stub pass? → run `parse_fulltext_to_transcript()` → write triplet → add to `unique_videos`, promote out of `blocked_recheck`.
4. No local content → attempt live fetch with the agent venv Python.

## Promoting / demoting status on retry

- After a successful recovery or live fetch: remove the `cloud_ip_blocked` or `blocked_recheck` entry from `failed_videos`; add `video_id` to `unique_videos`. Never leave permanent duplicates in `failed_videos`.
- After another `cloud_ip_blocked` failure: keep (or create) the `cloud_ip_blocked` entry. Optionally re-tag as `blocked_recheck` if you want periodic re-probing.
- After a confirmed `blocked_recheck` failure (no content fetched, no home cache): log a fresh failure note and leave in `blocked_recheck` until proven permanent.

## `confirmed_permanent` and partial raw-content

A `confirmed_permanent` entry can co-exist with real transcript content on disk.
That content comes from an earlier fulltext-recovery or stub-pass run, and is
_valid and meaningful_ — typically chapter-level headings (10–20 segments, 500 B–2 KB).
Do **not** treat it as a reason to promote the status back to `cloud_ip_blocked` or
`blocked_recheck`; the status signals that a **live fetch** consistently fails, not
that no useful data exists. The transcript / fulltext files from the prior pass should
simply be preserved and not overwritten or deleted.

## Playlist-exhaustion guard interaction

When `playlist-new-ids.txt` is fully consumed (all DONE):

- Check `yt-backlog.json` → `failed_videos` for `status: blocked_recheck`.
- For each candidate with no `_transcript.txt ≥ 500 B`, run the live-fetch or fulltext-recovery pipeline.
- A **zero-candidate `blocked_recheck` pool** (pool is empty or all candidates already have
  qualifying transcript files) is a normal exhaustion signal. It means all work in scope has
  been completed; it is **not** a pipeline break.
- Only return `[SILENT]` if BOTH the playlist is fully DONE *and* the `blocked_recheck` pool
  is empty. This two-condition gate is deliberate: each leg supplies work only when the other
  has been consumed.

## Grid schema mapping a vid to failure status (reference)

| What the vid has on disk | Typical `failed_videos` status | Interpretation |
|--------------------------|-------------------------------|----------------|
| `_transcript` ≥ 2 KB + `_fulltext` ≥ 200 B | `cloud_ip_blocked_recovered` / `unique_videos` member | Fully recovered content; skip live-fetch |
| `_transcript` 500 B – 2 KB + `_fulltext` | `cloud_ip_blocked_recovered` | Chapter-level headings from fulltext recovery; readable but incomplete |
| `_transcript` < 500 B + `_fulltext` ≥ 200 B | `confirmed_permanent` | Stub was overwritten; prior fulltext-recovery produced chapters, later run relabelled status |
| No files at all | `confirmed_permanent` | Nothing written; pure label, no content |
| `_transcript` 0 – 99 B (stub), no fulltext | `confirmed_permanent` | Failed stub pass; nothing to recover |
