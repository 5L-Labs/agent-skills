#!/usr/bin/env python3
"""
recover_stubs.py — batch re-segment cached fulltext stubs.

Usage
-----
    # Process top-10 (largest fulltext first, segs=-1)
    /opt/hermes/.venv/bin/python scripts/recover_stubs.py

    # Process a specific set
    /opt/hermes/.venv/bin/python scripts/recover_stubs.py T0mZJjl_dsA NBnOk0Uy9ig ...

    # Process all eligible stubs (no-arg limit)
    /opt/hermes/.venv/bin/python scripts/recover_stubs.py --all

What it does
------------
1. Scans youtube-raw/ for _meta.json entries with segments == -1.
2. Reads _fulltext.txt (must be ≥ 500 B, skipped if ≥ 5000 B already).
3. Parses both [M:SS] Title and M:SS Title chapter headings.
4. Corrupted-timestamp lines of the form MM:SS:-N are cleaned before matching.
5. Writes corrected _transcript.txt, _fulltext.txt, _meta.json (source=COHERENT_FULLTEXT_RESEQUENCED).
6. Updates yt-backlog.json and marks DONE in latent backlog.

Exit codes: 0 = all processed OK; 1 = one or more errors.
"""

import os, re, json, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

RAW_DIR        = "/opt/data/content/youtube-raw"
BACKLOG_JSON   = "/opt/data/content/yt-backlog.json"
LATENT_BL      = "/opt/data/.hermes/content/yt-latent-space-backlog.txt"
TS_PATTERN     = re.compile(r'^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s+(.+)')
MSS_PATTERN    = re.compile(r'^(\d{1,2}):(\d{2})\s+(.+)')
CORRUPT_PATTERN = re.compile(r'^(\d{1,2}):(\d{2}):-\d+\s+(.+)$')


def parse_ts_line(line):
    """Return (seconds, title) or (None, None). Handles [M:SS], M:SS, and -N-corrupted forms."""
    m = TS_PATTERN.match(line)
    if m:
        mn, s = int(m.group(1)), int(m.group(2))
        return mn * 60 + s, m.group(4)

    m = CORRUPT_PATTERN.match(line)
    if m:
        mn, s = int(m.group(1)), int(m.group(2))
        return mn * 60 + s, m.group(3)

    m = MSS_PATTERN.match(line)
    if m:
        mn, s = int(m.group(1)), int(m.group(2))
        return mn * 60 + s, m.group(3)

    return None, None


def collect_stubs(max_count=None):
    with open(BACKLOG_JSON) as f:
        backlog = json.load(f)
    done_ids = set(backlog["unique_videos"] + [v["video_id"] for v in backlog["failed_videos"]])

    stubs = []
    for fname in sorted(os.listdir(RAW_DIR)):
        if not fname.endswith("_meta.json"):
            continue
        vid = fname[:-len("_meta.json")]
        mpath = os.path.join(RAW_DIR, fname)
        with open(mpath) as f:
            try:
                meta = json.load(f)
            except json.JSONDecodeError:
                continue
        segs = meta.get("segments", -1)
        if segs > 0:
            continue
        if vid in done_ids:
            continue
        ft_path = os.path.join(RAW_DIR, f"{vid}_fulltext.txt")
        if not os.path.exists(ft_path):
            continue
        ft_sz = os.path.getsize(ft_path)
        if ft_sz < 500:
            continue
        if ft_sz >= 5000:
            continue
        stubs.append((vid, ft_sz))

    stubs.sort(key=lambda x: x[1], reverse=True)
    if max_count:
        stubs = stubs[:max_count]
    return stubs


def resegment(vid, ts_lines):
    chapters, other = [], []
    for line in ts_lines:
        line = line.strip()
        if not line:
            continue
        start, title = parse_ts_line(line)
        if start is not None:
            chapters.append({"start": start, "title": title})
        else:
            other.append(line)

    has_chapters = len(chapters) > 0
    if has_chapters and chapters:
        duration = chapters[-1]["start"] + 30.0
    else:
        duration = len(ts_lines) * 5.0
    return chapters, has_chapters, round(duration)


def save_files(vid, ts_content, ft_content, segments, duration, has_chapters):
    ts_path = os.path.join(RAW_DIR, f"{vid}_transcript.txt")
    ft_path = os.path.join(RAW_DIR, f"{vid}_fulltext.txt")
    mt_path = os.path.join(RAW_DIR, f"{vid}_meta.json")

    with open(ts_path, "w", encoding="utf-8") as f:
        f.write(ts_content)
    with open(ft_path, "w", encoding="utf-8") as f:
        f.write(ft_content)
    meta = {
        "video_id": vid,
        "title": "",
        "segments": len(segments),
        "duration": duration,
        "source": "COHERENT_FULLTEXT_RESEQUENCED",
        "has_chapters": has_chapters,
    }
    with open(mt_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return ts_path, ft_path, mt_path


def mark_done(vid):
    with open(LATENT_BL) as f:
        lines = f.readlines()
    new_lines = []
    changed = 0
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.split()[0] == vid and not stripped.endswith("DONE"):
            new_lines.append(stripped + "DONE\n")
            changed += 1
        else:
            new_lines.append(line)
    with open(LATENT_BL, "w") as f:
        f.writelines(new_lines)
    return changed


def update_backlog(vid):
    with open(BACKLOG_JSON) as f:
        backlog = json.load(f)
    if vid not in backlog["unique_videos"]:
        backlog["unique_videos"].append(vid)
    backlog["last_updated"] = "2026-05-19T08:00:00.000000+00:00"
    with open(BACKLOG_JSON, "w") as f:
        json.dump(backlog, f, indent=2, ensure_ascii=False)


def process_one(vid, ft_sz):
    ft_path = os.path.join(RAW_DIR, f"{vid}_fulltext.txt")
    with open(ft_path, errors="replace") as f:
        fulltext = f.read()

    ts_lines = [l.strip() for l in fulltext.splitlines() if l.strip()]
    segments, has_chapters, duration = resegment(vid, ts_lines)
    ts_content = "\n".join(ts_lines)
    save_files(vid, ts_content, fulltext, segments, duration, has_chapters)
    update_backlog(vid)
    mark_done(vid)
    return len(segments), duration, has_chapters


def main():
    args = sys.argv[1:]
    if "--all" in args:
        max_count = None
        ids = None
        args = [a for a in args if a != "--all"]
    elif args:
        ids = args
        max_count = len(ids)
    else:
        ids = None
        max_count = 10

    if ids:
        stubs = [(vid, -1) for vid in ids]
    else:
        stubs = collect_stubs(max_count)

    if not stubs:
        print("No eligible stubs found.")
        sys.exit(0)

    ok, fail = [], []
    for vid, ft_sz in stubs:
        try:
            n_segs, dur, has_ch = process_one(vid, ft_sz)
            ok.append({"video_id": vid, "segments": n_segs, "duration": dur, "has_chapters": has_ch})
            print(f"  ✓ {vid}  {n_segs} segs  {dur}s  chapters={has_ch}")
        except Exception as ex:
            fail.append({"video_id": vid, "error": str(ex)})
            print(f"  ✗ {vid}  {ex}")

    print(f"\n═══ SUMMARY ═══")
    print(f"Processed: {len(ok) + len(fail)}  |  OK: {len(ok)}  |  FAIL: {len(fail)}")
    if ok:
        print("\nSuccessful:")
        for r in ok:
            print(f"  ✓ {r['video_id']}  {r['segments']} segs  {r['duration']}s")
    if fail:
        print("\nFailed:")
        for r in fail:
            print(f"  ✗ {r['video_id']}  {r['error'][:100]}")

    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    main()
