#!/usr/bin/env python3
"""
Corrected three-way audit for the youtube-content batch pipeline.

Usage:
    python3 audit_raw_state.py

Shows the real raw transcript counts (fixes the reconcile_batch_state.py
glob bug) and reports whether the full batch state is reconciled.

Exit codes:
    0 — all three sources in agreement (playlist == backlog == raw+cp+cp_no_raw)
    1 — discrepancy detected
"""
import glob, os, re, json, sys

RAW_DIR  = '/opt/data/content/youtube-raw'
PLAYLIST = '/opt/data/content/playlist-new-ids.txt'
BACKLOG  = '/opt/data/content/yt-backlog.json'


def is_stub(path):
    with open(path) as f:
        content = f.read()
    n_bare  = len(re.findall(r'^\d{1,2}:\d{2}(?::\d{2})? ', content, re.MULTILINE))
    n_brack = len(re.findall(r'^\[\d{1,2}:\d{2}(?::\d{2})?\] ', content, re.MULTILINE))
    stub_terms = ['ERROR', 'SSL', 'UNEXPECTED_EOF', 'all subtitle formats failed',
                  'Cloud IP', 'batch_fetch', 'transcript file found but empty',
                  'post_batch_recheck']
    return (len(content) < 500
            or max(n_bare, n_brack) < 5
            or any(e in content for e in stub_terms))


def main():
    # Source 1 — playlist DONE entries
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
    backlog_vids = set(backlog.get('unique_videos', []))
    backlog_count = len(backlog_vids)

    # Source 3 — raw transcript files (corrected glob — uses os.path.join)
    raw_files = glob.glob(os.path.join(RAW_DIR, '*_transcript.txt'))
    valid_raw = set()
    stub_raw  = set()
    for fp in raw_files:
        vid = os.path.basename(fp).replace('_transcript.txt', '')
        if is_stub(fp):
            stub_raw.add(vid)
        else:
            valid_raw.add(vid)

    # confirmed_permanent identities
    fail_vids = {v['video_id'] for v in backlog.get('failed_videos', [])
                 if isinstance(v, dict) and v.get('status') == 'confirmed_permanent'}

    # Stubs not yet logged
    stub_not_logged = sorted(stub_raw - fail_vids)

    print("=== CORRECTED Fast-Audit Table ===")
    print(f"{'Source':<38} {'Count':>6}  What done means")
    print("-" * 70)
    print(f"{'playlist-new-ids.txt':<38} {playlist_count:>6}  last field == DONE")
    print(f"{'yt-backlog.json unique_videos':<38} {backlog_count:>6}  video_id in array")
    print(f"{'youtube-raw/ (valid, non-stub)':<38} {len(valid_raw):>6}  pass is_stub()")
    print(f"{'youtube-raw/ (stub files)':<38} {len(stub_raw):>6}  fail is_stub()")
    print()

    print(f"Raw transcript files detected: {len(raw_files)}")
    print(f"Playlist DONE entries:         {playlist_count}")
    print(f"Backlog unique_videos:         {backlog_count}")

    # Stub-not-logged warning
    if stub_not_logged:
        print(f"\n⚠️  {len(stub_not_logged)} stub files not logged as confirmed_permanent:")
        for v in stub_not_logged:
            print(f"     {v}")

    # Break down confirmed_permanent into buckets
    cp_in_stub  = fail_vids & stub_raw
    cp_no_stub  = fail_vids - stub_raw  # no raw transcript at all (error.txt only or nothing)
    cp_in_valid = fail_vids & valid_raw  # should be 0, flagged as odd

    print(f"\nconfirmed_permanent breakdown ({len(fail_vids)} total):")
    print(f"  stub_raw AND fail_vids:       {len(cp_in_stub)}")
    if cp_in_valid:
        print(f"  valid_raw AND fail_vids:      {len(cp_in_valid)}  ← unexpected")
    print(f"  fail_vids without raw:        {len(cp_no_stub)}  → {sorted(cp_no_stub)}")

    # Canonical partition sum
    part_a = valid_raw - fail_vids          # good valid, not in fail_vids
    part_b = valid_raw & fail_vids          # should be 0
    part_c = stub_raw - fail_vids           # should be 0
    part_d = stub_raw & fail_vids           # confirmed_permanent stubs
    part_e = cp_no_stub                     # fail_vids no raw file
    part_f = backlog_vids - (valid_raw | stub_raw | fail_vids)  # truly unresolved

    total_check = (len(part_a) + len(part_b) + len(part_c)
                   + len(part_d) + len(part_e) + len(part_f))

    print(f"\nBacklog partition (sum should = {backlog_count}):")
    print(f"  part_a valid-only:   {len(part_a)}")
    print(f"  part_b valid+fail:   {len(part_b)}")
    print(f"  part_c stub-only:    {len(part_c)}")
    print(f"  part_d stub+fail:    {len(part_d)}")
    print(f"  part_e fail,no-raw:  {len(part_e)}")
    print(f"  part_f unresolved:   {len(part_f)}")
    print(f"  ∑ = {total_check}")

    # Three-way agreement
    agree = (playlist_count == backlog_count
             == len(valid_raw) + len(stub_raw) + len(cp_no_stub)
             == total_check)

    print(f"\nReconcile verdict:")
    if agree:
        print("  ✅ All three sources in agreement — batch is fully reconciled.")
        sys.exit(0)
    else:
        print("  ⚠️  DISCREPANCY DETECTED")
        print(f"     playlist DONE = {playlist_count}")
        print(f"     backlog unique_videos = {backlog_count}")
        print(f"     raw+cp total = {len(valid_raw) + len(stub_raw) + len(cp_no_stub)}")
        unresolved = sorted(backlog_vids - valid_raw - stub_raw - fail_vids)
        if unresolved:
            print(f"\n  → {len(unresolved)} IDs still need fetching:")
            for v in unresolved:
                print(f"     {v}")
        sys.exit(1)


if __name__ == '__main__':
    main()
