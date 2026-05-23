#!/usr/bin/env python3
"""
Batch state reconciliation — skip stub re-fetches and zero duplicate work.

Usage:
    python3 reconcile_batch_state.py

Reads:
    /opt/data/content/playlist-new-ids.txt
    /opt/data/content/yt-backlog.json
    /opt/data/content/youtube-raw/

Prints a three-source table and exits with:
    code 0  — all counts agree, system is current
    code 1  — discrepancy detected, investigate
"""
import json, os, re, sys

_PLAYLIST = "/opt/data/content/playlist-new-ids.txt"
_BACKLOG  = "/opt/data/content/yt-backlog.json"
_RAW_DIR  = "/opt/data/content/youtube-raw/"

# Regex patterns — compiled WITH re.MULTILINE so ^ anchors to line-start on every line.
# Python 3.13 changed re behavior: passing flags to re.findall() on a pre-compiled pattern
# is either a ValueError or silently ignored depending on version. Embedding the flag at
# compile time is the only safe cross-version approach.
#
# Two bracketed formats exist in the wild:
#   [M:SS] text   -- single-digit minutes, no hour field (most common)
#   [MM:SS] text  -- zero-padded minutes
#   [H:MM:SS]     -- hour field present (videos > 9 h)
# Both end right before the next bracket, so no trailing-\\s required.
stub_pattern = re.compile(r'^\d{1,2}:\d{2}(?::\d{2})? ', re.MULTILINE)
brack_pattern= re.compile(r'^\[\d{1,2}:\d{2}(?::\d{2})?\]', re.MULTILINE)
error_terms = {'ERROR', 'SSL', 'UNEXPECTED_EOF', 'all subtitle formats failed'}

def is_stub(path: str) -> bool:
    """Return True if transcript file is a stub or error marker, False if valid."""
    if not os.path.exists(path):
        return True
    with open(path) as fh:
        content = fh.read()
    segs  = len(re.findall(stub_pattern, content))   # MULTILINE baked in at compile time
    segs += len(re.findall(brack_pattern, content))  # same
    segs = max(segs, 0)
    return (len(content) < 500
            or segs < 5
            or any(e in content for e in error_terms))

# --- 1. Playlist ---
playlist_done = 0
playlist_total = 0
with open(_PLAYLIST) as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        playlist_total += 1
        fields = line.split('\t')
        if fields[-1] == 'DONE':
            playlist_done += 1

# --- 2. Backlog ---
with open(_BACKLOG) as fh:
    bl = json.load(fh)
unique_videos  = set(bl.get('unique_videos', []))
failed_videos  = {e['video_id'] for e in bl.get('failed_videos', [])}
not_failed     = unique_videos - failed_videos

# --- 3. Raw dir ---
all_bases = set()
valid_raw_ids = set()
stub_raw_ids  = set()
if os.path.exists(_RAW_DIR):
    for fname in os.listdir(_RAW_DIR):
        for suf in ('_transcript.txt',):
            if fname.endswith(suf):
                vid = fname[:-len(suf)]
                all_bases.add(vid)
                if is_stub(os.path.join(_RAW_DIR, fname)):
                    stub_raw_ids.add(vid)
                else:
                    valid_raw_ids.add(vid)
                break

# --- Table ---
print(f"{'Source':<35} {'Total':>6}  {'Note'}")
print("-" * 80)
print(f"{'playlist-new-ids.txt (all entries)':<35} {playlist_total:>6}")
print(f"{'playlist-new-ids.txt (DONE)':<35} {playlist_done:>6}")
print(f"{'yt-backlog.json → unique_videos':<35} {len(unique_videos):>6}")
print(f"{'yt-backlog.json → failed_videos':<35} {len(failed_videos):>6}")
print(f"{'not-failed in backlog':<35} {len(not_failed):>6}")
print(f"{'youtube-raw/ → valid transcripts':<35} {len(valid_raw_ids):>6}")
print(f"{'youtube-raw/ → error stubs':<35} {len(stub_raw_ids):>6}")

# --- Agreement check ---
# Stubs should appear in failed_videos; validate that
unaccounted_stubs = stub_raw_ids - failed_videos
if unaccounted_stubs:
    print(f"\n⚠️  Stubs not yet in failed_videos ({len(unaccounted_stubs)}): {sorted(unaccounted_stubs)}")

# A system is "current" when every backlog candidate has a valid raw file
# AND every valid raw ID is already in unique_videos
backlog_unserved = not_failed - valid_raw_ids   # still need fetch
raw_not_tracked  = valid_raw_ids - unique_videos

if not backlog_unserved and not raw_not_tracked:
    if playlist_done == playlist_total:
        print("\n✅ All counts agree — system is current. No fetch needed.")
        sys.exit(0)
else:
    print(f"\n❌ Discrepancy — investigation needed")
    if backlog_unserved:
        print(f"   Backlog candidates with no valid raw file ({len(backlog_unserved)}): {sorted(backlog_unserved)[:10]}{'...' if len(backlog_unserved)>10 else ''}")
    if raw_not_tracked:
        print(f"   Valid raw IDs missing from backlog ({len(raw_not_tracked)}): {sorted(raw_not_tracked)[:10]}{'...' if len(raw_not_tracked)>10 else ''}")
    sys.exit(1)
