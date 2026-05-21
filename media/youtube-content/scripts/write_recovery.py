#!/usr/bin/env python3
"""
Fulltext-to-transcript recovery (offline path).
Reads a _fulltext.txt (chapter headings or inline timestamps) from
RAW_DIR and emits a _transcript.txt + _fulltext.txt + _meta.json triplet.

Usage:
    python3 write_recovery.py VIDEO_ID [--raw-dir DIR] [--title "Video title"]
    # Reads fulltext from RAW_DIR/VIDEO_ID_fulltext.txt
    python3 write_recovery.py VIDEO_ID --in-file PATH
"""
import argparse, json, os, re, sys
from datetime import datetime, timezone


def parse_fulltext_to_txlines(fulltext: str) -> list[str]:
    """Convert stored chapter/summary fulltext -> timestamped transcript lines."""
    tx_lines = []
    secs = 0.0

    # Format 1: inline timestamps mixed into a single paragraph
    first_ts = re.search(r"\d{1,2}:\d{2}\s+[A-Z]", fulltext)
    if first_ts and "\n" not in fulltext[: first_ts.start() + 20]:
        intro = fulltext[: first_ts.start()].strip()
        rest = fulltext[first_ts.start():]
        if intro:
            tx_lines.append("[00:00] " + intro)
        for m in re.finditer(r"(\d{1,2}:\d{2})\s+(.*?)(?=\s+\d{1,2}:\d{2}\s+|$)", rest):
            ts, part = m.group(1), m.group(2).strip()
            if part:
                tx_lines.append(f"[{ts}] {part}")
        return tx_lines

    # Format 2-4: line-by-line
    for raw in fulltext.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^(Video:|Duration:|Chapters\()", line):
            continue
        m = re.match(r"^\[(\d{1,2}:\d{2})\]\s*(.*)", line)
        if m:
            t = m.group(2).rstrip()
            if t:
                tx_lines.append(f"[{m.group(1)}] {t}")
            continue
        m = re.match(r"^(\d{1,2}:\d{2})([\s\-])", line)
        if m:
            rest = line[5:].strip()
            if rest:
                tx_lines.append(f"[{m.group(0)[:5]}] {rest}")
            continue
        tx_lines.append(f"[{int(secs)//60:02d}:{int(secs)%60:02d}] {line}")
        secs += 60.0
    return tx_lines


def clean_stale_files(video_id: str, raw_dir: str):
    """Delete stub/artefact files before writing a fresh triplet."""
    import glob
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
            try:
                os.remove(path)
            except FileNotFoundError:
                pass


def write_triplet(
    raw_dir: str,
    video_id: str,
    tx_lines: list[str],
    title: str = "",
    source: str = "fulltext_recovery",
) -> dict:
    """Write the 3-file triplet; return meta dict."""
    fulltext = " ".join(
        re.sub(r"^\[\d+:\d{2}(?::\d{2})?\]\s*", "", l).strip()
        for l in tx_lines if l.strip()
    )
    meta = {
        "video_id":      video_id,
        "title":         title or f"[{video_id}]",
        "segments":      len(tx_lines),
        "duration_secs": 0,
        "source":        source,
        "fetched_utc":   datetime.now(timezone.utc).isoformat(),
    }
    with open(os.path.join(raw_dir, f"{video_id}_transcript.txt"), "w") as f:
        f.write("\n".join(tx_lines) + "\n")
    with open(os.path.join(raw_dir, f"{video_id}_fulltext.txt"), "w") as f:
        f.write(fulltext)
        f.write("\n")
    with open(os.path.join(raw_dir, f"{video_id}_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def main():
    ap = argparse.ArgumentParser(description="Offline fulltext->transcript recovery")
    ap.add_argument("video_id", help="YouTube video ID")
    ap.add_argument("--raw-dir", default="/opt/data/content/youtube-raw")
    ap.add_argument("--title", default="", help="Optional video title")
    ap.add_argument("--in-file", help="Read fulltext from file instead of raw-dir")
    args = ap.parse_args()
    raw_dir = args.raw_dir
    video_id = args.video_id

    if args.in_file:
        with open(args.in_file) as f:
            fulltext_content = f.read()
    else:
        ft_path = os.path.join(raw_dir, f"{video_id}_fulltext.txt")
        with open(ft_path) as f:
            fulltext_content = f.read()

    if len(fulltext_content) < 200:
        print(f"[SKIP] {video_id}: fulltext too short ({len(fulltext_content)}B)", file=sys.stderr)
        sys.exit(1)

    clean_stale_files(video_id, raw_dir)
    tx_lines = parse_fulltext_to_txlines(fulltext_content)
    if not tx_lines:
        print(f"[FAIL] {video_id}: no segments extracted from fulltext", file=sys.stderr)
        sys.exit(1)

    meta = write_triplet(raw_dir, video_id, tx_lines, title=args.title)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
