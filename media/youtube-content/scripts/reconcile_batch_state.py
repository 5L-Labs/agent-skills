#!/usr/bin/env python3
"""
Fast-Audit script — reconcile three sources in one pass.

Use this when the playlist is fully DONE to check whether counts agree
before deciding there is "nothing to do".

Sources
  1. playlist-new-ids.txt   → DONE entries (last field == 'DONE')
  2. yt-backlog.json        → unique_videos string array
  3. youtube-raw/           → *_transcript.txt files that pass is_stub() check

Exits with code 0 if counts agree (all three sources consistent),
              code 1 if discrepancy detected.
"""

import json, glob, os, re, sys

RAW_DIR  = '/opt/data/content/youtube-raw'
PLAYLIST = '/opt/data/content/playlist-new-ids.txt'
BACKLOG  = '/opt/data/content/yt-backlog.json'

def is_stub(path):
    with open(path) as f:
        content = f.read()
    n_bare  = len(re.findall(r'^\d{1,2}:\d{2}(?::\d{2})? ', content, re.MULTILINE))
    n_brack = len(re.findall(r'^\[\d{1,2}:\d{2}(?::\d{2})?\] ', content, re.MULTILINE))
    stub_terms = ['ERROR','SSL','UNEXPECTED_EOF','all subtitle formats failed',
                  'Cloud IP','batch_fetch','transcript file found but empty','post_batch_recheck']
    return len(content) < 500 or max(n_bare, n_brack) < 5 or any(e in content for e in stub_terms)


def main():
    # Source 1 — playlist
    playlist_ids = set()
    with open(PLAYLIST) as f:
        for line in f:
            parts = line.strip().split('\t')
            if parts and parts[-1] == 'DONE':
                playlist_ids.add(parts[0])
    playlist_count = len(playlist_ids)

    # Source 2 — backlog
    with open(BACKLOG) as f:
        backlog = json.load(f)
    backlog_count = len(backlog.get('unique_videos', []))

    # Source 3 — valid raw
    raw_files = glob.glob(os.path.join(RAW_DIR, '*_transcript.txt'))
    valid_raw = {os.path.basename(f).replace('_transcript.txt', '')
                 for f in raw_files if not is_stub(f)}
    valid_raw_count = len(valid_raw)

    # Stub count
    stub_raw = {os.path.basename(f).replace('_transcript.txt', '')
                for f in raw_files if is_stub(f)}

    # The fast-audit table
    print("=== Fast-Audit Table ===")
    print(f"{'Source':<38} {'Count':>6}  {'What done means'}")
    print("-" * 70)
    print(f"{'playlist-new-ids.txt':<38} {playlist_count:>6}  {'last field == DONE'}")
    print(f"{'yt-backlog.json → unique_videos':<38} {backlog_count:>6}  {'video_id in array'}")
    print(f"{'youtube-raw/ (valid, non-stub)':<38} {valid_raw_count:>6}  {'pass is_stub()'}")
    print(f"{'youtube-raw/ (stub files)':<38} {len(stub_raw):>6}  {'fail is_stub()'}")
    print()

    # Verify every stub has a confirmed_permanent entry in failed_videos
    fv_ids = {v['video_id'] for v in backlog.get('failed_videos', [])
              if isinstance(v, dict) and v.get('status') == 'confirmed_permanent'}
    stub_not_logged = sorted(stub_raw - fv_ids)
    if stub_not_logged:
        print(f"⚠️  {len(stub_not_logged)} stub files not logged in failed_videos as confirmed_permanent:")
        for v in stub_not_logged:
            print(f"     {v}")
        print()

    # Three-way reconcile
    print("Reconcile verdict:")
    agree = playlist_count == backlog_count == valid_raw_count
    if agree:
        print("  ✅ All three counts agree — system is current.")
        sys.exit(0)
    else:
        print(f"  ⚠️  DISCREPANCY DETECTED")
        print(f"     playlist DONE = {playlist_count}")
        print(f"     backlog unique_videos = {backlog_count}")
        print(f"     valid raw transcripts = {valid_raw_count}")
        print()
        print("  Psychoanalyze:")
        if backlog_count > valid_raw_count:
            unprocessed = backlog_count - valid_raw_count - len(stub_raw)
            print(f"    • {backlog_count - valid_raw_count} IDs in backlog have no valid raw transcript")
            print(f"      ({len(stub_raw)} of those are stubs logged in failed_videos)")
        if playlist_count < backlog_count:
            print(f"    • playlist has {backlog_count - playlist_count} IDs not yet marked DONE")
        print()
        print("  → Proceed with backlog processing for unprocessed candidates.")
        sys.exit(1)


if __name__ == '__main__':
    main()
