#!/usr/bin/env python3
"""
Chapter-based batch fallback: reads yt-dlp JSON metadata files and produces
the standard 3-file tuple (_transcript.txt, _fulltext.txt, _meta.json) using
chapter data as a structured transcript proxy.

Usage:
    python3 chapter_fallback_batch.py --meta-dir /tmp/ytbatch_meta --raw-dir /opt/data/content/youtube-raw

Dependencies: json, os, argparse — stdlib only.
"""
import argparse, json, os, sys
from datetime import datetime, timezone


def fmt_ts(secs_float: float) -> str:
    s = int(secs_float)
    h, r = divmod(s, 3600)
    m, s2 = divmod(r, 60)
    return f"{h}:{m:02d}:{s2:02d}" if h else f"{m}:{s2:02d}"


def process_meta(meta_path: str, raw_dir: str, now_iso: str) -> tuple:
    """Return (video_id, status, detail) for one JSON metadata file."""
    vid = os.path.splitext(os.path.basename(meta_path))[0]
    try:
        with open(meta_path) as f:
            data = json.load(f)
    except Exception as e:
        return vid, "fail", f"json_error: {e}"

    chapters   = data.get("chapters") or []
    title      = data.get("fulltitle") or data.get("title") or ""
    duration   = data.get("duration", 0)

    if not chapters:
        # No chapters at all — skip, leave for retry (transient)
        failed_mark = os.path.join(raw_dir, f"{vid}_failed.txt")
        if not os.path.exists(failed_mark):
            with open(failed_mark, "w") as f:
                f.write(f"{now_iso} no_chapters\n")
        return vid, "skip", "no_chapters"

    ts_lines, ft_parts = [], []
    for ch in chapters:
        t = (ch.get("title") or "Untitled").strip()
        s = int(ch.get("start_time", 0))
        ts = fmt_ts(s)
        ts_lines.append(f"[{ts}] {t}")
        ft_parts.append(f"{ts} {t}")

    os.makedirs(raw_dir, exist_ok=True)

    # _transcript.txt
    with open(os.path.join(raw_dir, f"{vid}_transcript.txt"), "w") as f:
        f.write("\n".join(ts_lines) + "\n")

    # _fulltext.txt
    with open(os.path.join(raw_dir, f"{vid}_fulltext.txt"), "w") as f:
        f.write("\n\n".join(ft_parts) + "\n")

    # _meta.json
    meta = {
        "video_id": vid,
        "title": title,
        "duration": duration,
        "segment_count": len(chapters),
        "fetched_at": now_iso,
        "note": "chapter_outline_ip_blocked",
    }
    with open(os.path.join(raw_dir, f"{vid}_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Remove stale _failed.txt if present
    failed_mark = os.path.join(raw_dir, f"{vid}_failed.txt")
    if os.path.exists(failed_mark):
        os.remove(failed_mark)

    dur_min = int(duration // 60)
    return vid, "ok", f"{len(chapters)} chapters ~{dur_min}min"


def main():
    ap = argparse.ArgumentParser(description="Batch chapter-fallback: JSON → 3-file tuple")
    ap.add_argument("--meta-dir", required=True, help="Dir with per-video yt-dlp JSON files")
    ap.add_argument("--raw-dir",  default="/opt/data/content/youtube-raw")
    ap.add_argument("--file-pattern", default="*.json", help="Glob pattern for meta files")
    args = ap.parse_args()

    now_iso = datetime.now(timezone.utc).isoformat()
    meta_files = sorted(
        os.path.join(args.meta_dir, f)
        for f in os.listdir(args.meta_dir)
        if __import__("fnmatch").fnmatch(f, args.file_pattern)
    )

    if not meta_files:
        print("WARNING: no meta files found", file=sys.stderr)
        sys.exit(1)

    results = []
    for mp in meta_files:
        vid, status, detail = process_meta(mp, args.raw_dir, now_iso)
        print(f"  {vid}: {status}  {detail}")
        results.append((vid, status, detail))

    ok  = [r for r in results if r[1] == "ok"]
    skp = [r for r in results if r[1] == "skip"]
    fl  = [r for r in results if r[1] == "fail"]
    print(f"\n=== SUMMARY ===")
    print(f"Processed (chapters written): {len(ok)}")
    print(f"Skipped  (no chapters):      {len(skp)}")
    print(f"Failed   (JSON parse error):  {len(fl)}")

    # Exit non-zero only on real errors
    if fl:
        sys.exit(2)


if __name__ == "__main__":
    main()
