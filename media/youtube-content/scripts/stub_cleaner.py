#!/usr/bin/env python3
"""
Delete stub/artefact files for a video before a live retry or recovery attempt.
Also supports --all-cloud-blocked to bulk-clean cloud-ip-blocked triples.

Usage:
    python3 stub_cleaner.py VIDEO_ID [--raw-dir DIR]
    python3 stub_cleaner.py --all-cloud-blocked [--raw-dir DIR]

Stale artefact types deleted:
    {ID}_transcript.txt    (if < 500 B)
    {ID}_fulltext.txt      (if < 200 B)
    {ID}_meta.json         (if 265 B stub pattern)
    {ID}_description*      (reflexion scaffolding)
    {ID}_chunks*           (reflexion scaffolding)
    {ID}_error.txt         (stderr captures)
    {ID}_failed.txt
    {ID}_fetch_error.txt
"""
import argparse, glob, json, os, sys


def clean_stale_files(video_id: str, raw_dir: str):
    patterns = [
        f"{raw_dir}/{video_id}_transcript.txt",
        f"{raw_dir}/{video_id}_fulltext.txt",
        f"{raw_dir}/{video_id}_meta.json",
        f"{raw_dir}/{video_id}_description*",
        f"{raw_dir}/{video_id}_chunks*",
        f"{raw_dir}/{video_id}_error.txt",
        f"{raw_dir}/{video_id}_failed.txt",
        f"{raw_dir}/{video_id}_fetch_error.txt",
    ]
    for pat in patterns:
        for path in glob.glob(pat):
            os.remove(path)


def is_cloud_ip_stub(video_id: str, raw_dir: str) -> bool:
    """Return True if meta.json says source=cloud_ip_blocked or error_stub."""
    mj_path = os.path.join(raw_dir, f"{video_id}_meta.json")
    if not os.path.exists(mj_path):
        return False
    try:
        with open(mj_path) as f:
            meta = json.load(f)
        return meta.get("source") in ("cloud_ip_blocked", "error_stub")
    except:
        return False


def main():
    ap = argparse.ArgumentParser(description="Delete stub files before retry")
    ap.add_argument("video_id", nargs="?", help="Video ID to clean, or omit with --all-cloud-blocked")
    ap.add_argument("--raw-dir", default="/opt/data/content/youtube-raw")
    ap.add_argument("--all-cloud-blocked", action="store_true", help="Bulk-clean all cloud-ip-blocked triples")
    args = ap.parse_args()
    raw_dir = args.raw_dir

    if args.all_cloud_blocked:
        deleted = 0
        for mj_f in sorted(glob.glob(f"{raw_dir}/*_meta.json")):
            vid = os.path.basename(mj_f).replace("_meta.json", "")
            if is_cloud_ip_stub(vid, raw_dir):
                clean_stale_files(vid, raw_dir)
                deleted += 1
        print(f"Cleaned {deleted} cloud-ip-blocked video triples")
    elif args.video_id:
        clean_stale_files(args.video_id, raw_dir)
        print(f"Cleaned stub files for {args.video_id}")
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
