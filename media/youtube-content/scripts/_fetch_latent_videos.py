#!/usr/bin/env python3
"""
Fetch transcripts for YouTube videos from the latent backlog.

Writes the canonical 3-file tuple to RAW_DIR:
  {VIDEO_ID}_transcript.txt   — [MM:SS] text (one segment per line)
  {VIDEO_ID}_fulltext.txt     — plain text, no timestamps
  {VIDEO_ID}_meta.json        — video_id, title, duration, segment_count, fetched_at

Priority order:
  1. VTT auto-captions (yt-dlp --write-auto-subs, bypass proxy)
  2. Chapter outline fallback (yt-dlp metadata chapters[], marked chapter_outline_ip_blocked)
  3. No-workable-data failure — writes _failed.txt, does NOT mark permanent

USAGE (run via terminal(), not execute_code):
  terminal("/tmp/yt-venv/bin/python /opt/data/content/_fetch_latent_videos.py")
  or directly:
  terminal("/opt/hermes/.venv/bin/python /opt/data/content/_fetch_latent_videos.py")

ENV overrides:
  RAW_DIR default: /opt/data/content/youtube-raw/
  YT_VENV default: /tmp/yt-venv/bin/yt-dlp
  VIDEO_IDS     default: built-in latent-candidate list
"""
import subprocess, json, os, re, datetime

RAW_DIR: str = os.environ.get("RAW_DIR", "/opt/data/content/youtube-raw/")
YT_VENV:   str = os.environ.get("YT_VENV", "/tmp/yt-venv/bin/yt-dlp")
NOW: str   = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# Default: 10 latent-backlog items (replace or extend per batch)
VIDEO_IDS: list[str] = [
    "7UGjf080qag", "IYrO9h4KYZc", "XquVJ-v0ML4", "_IlTcWciEC4",
    "djIKPkw0gYY", "Y0Hlizumgpw", "2fDBeMu6xjk", "xlXIi6GZNGY",
    "n4VDa9uAIi4", "uIKmG3M0X3M",
]

VTT_TMP: str = "/tmp/ytd_vtt"

# ── helpers ─────────────────────────────────────────────────────────────────

def sh(cmd: str, timeout: int = 90) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def dump_meta(video_id: str) -> dict | None:
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = f'ALL_PROXY="" "{YT_VENV}" --dump-single-json --quiet --no-warnings "{url}" > /tmp/ytd_dump_{video_id}.json'
    rc, _ = sh(cmd)
    path = f"/tmp/ytd_dump_{video_id}.json"
    if rc != 0 or not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        with open(path) as f:
            return json.loads(f.read().strip())
    except json.JSONDecodeError:
        return None


def download_vtt_same_session(video_id: str) -> str | None:
    """Download VTT in the same terminal() shell session as metadata dump."""
    os.makedirs(VTT_TMP, exist_ok=True)
    # Clean stale files for this video
    for f in os.listdir(VTT_TMP):
        if f.startswith(video_id):
            os.remove(os.path.join(VTT_TMP, f))
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = (
        f'ALL_PROXY="" "{YT_VENV}" --skip-download '
        f'--write-auto-subs --sub-langs en --sub-format "vtt/srt" '
        f'--output "{VTT_TMP}/{video_id}.%(ext)s" '
        f'--quiet --no-warnings "{url}"'
    )
    sh(cmd)
    for f in os.listdir(VTT_TMP):
        if f.startswith(video_id) and f.endswith(".vtt"):
            return os.path.join(VTT_TMP, f)
    return None


def parse_vtt(path: str) -> list[tuple[str, str]]:
    """Parse WebVTT → [(timestamp_str, text), ...]"""
    segs: list[tuple[str, str]] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*-->", line)
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
            # Distinguish MM:SS vs HH:MM:SS
            if h < 10 and len(m.group(1)) <= 1:
                ts = f"{mi}:{s:02d}"
            else:
                ts = f"{h}:{mi:02d}:{s:02d}"
            i += 1
            parts: list[str] = []
            while i < len(lines):
                t = lines[i].strip()
                if not t or t == "WEBVTT" or t.startswith("NOTE") or "-->" in t:
                    break
                parts.append(re.sub(r"<[^>]+>", "", t))
                i += 1
            text = " ".join(parts).strip()
            if text:
                segs.append((ts, text))
            continue
        i += 1
    return segs


def fmt_ts(seconds: float) -> str:
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def write_three_files(video_id: str, segs: list[tuple[str, str]],
                      title: str, duration, note: str | None = None):
    raw = RAW_DIR
    # Delete any prior failure marker
    ft = os.path.join(raw, f"{video_id}_failed.txt")
    if os.path.exists(ft): os.remove(ft)

    ts_txt  = "\n".join(f"[{ts}] {txt}" for ts, txt in segs)
    ft_txt  = "\n\n".join(f"{ts} {txt}"  for ts, txt in segs)
    meta = {
        "video_id": video_id, "title": title, "duration": duration,
        "segment_count": len(segs), "fetched_at": NOW,
    }
    if note:
        meta["note"] = note

    for suffix, content in [
        ("_transcript.txt", ts_txt), ("_fulltext.txt", ft_txt),
    ]:
        with open(os.path.join(raw, f"{video_id}{suffix}"), "w") as fh:
            fh.write(content)
    with open(os.path.join(raw, f"{video_id}_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    return len(segs)


# ── main ─────────────────────────────────────────────────────────────────────

success, failed, skipped = 0, 0, 0
results: list[tuple[str, str, str]] = []  # (video_id, status, detail)

for video_id in VIDEO_IDS:
    t_file = os.path.join(RAW_DIR, f"{video_id}_transcript.txt")
    f_file = os.path.join(RAW_DIR, f"{video_id}_fulltext.txt")
    m_file = os.path.join(RAW_DIR, f"{video_id}_meta.json")

    # déjà-fetched guard
    if (os.path.exists(t_file) and os.path.exists(f_file) and os.path.exists(m_file)):
        with open(t_file) as fh:
            sz = len(fh.read())
        if sz >= 50:
            print(f"[SKIP] {video_id} — already fetched ({sz}B)", flush=True)
            skipped += 1; continue

    print(f"\n[FETCH] {video_id}", flush=True)

    data = dump_meta(video_id)
    if data is None:
        print("  FAIL: yt-dlp returned null/empty JSON", flush=True)
        with open(os.path.join(RAW_DIR, f"{video_id}_failed.txt"), "w") as fp:
            fp.write(f"yt-dlp null/empty JSON UTC:{NOW}\n")
        failed += 1; results.append((video_id, "FAIL", "null_json")); continue

    title    = data.get("fulltitle", "") or data.get("title", "")
    duration = data.get("duration", 0)

    # ── Path A: VTT captions ─────────────────────────────────────────────────
    if "en" in (data.get("automatic_captions") or {}):
        vtt_path = download_vtt_same_session(video_id)
        if vtt_path and os.path.exists(vtt_path):
            segs = parse_vtt(vtt_path)
            if segs:
                write_three_files(video_id, segs, title, duration)
                print(f"  OK — {len(segs)} segments (VTT)", flush=True)
                success += 1; results.append((video_id, "OK", "vtt")); continue
        print("  VTT empty or blocked, trying chapters…", flush=True)

    # ── Path B: Chapter outline fallback ─────────────────────────────────────
    chapters = data.get("chapters") or []
    if chapters:
        segs = [(fmt_ts(ch.get("start_time", 0)), ch.get("title", "").strip())
                for ch in chapters if ch.get("title")]
        if segs:
            write_three_files(video_id, segs, title, duration, note="chapter_outline_ip_blocked")
            print(f"  OK — {len(segs)} chapters (outline)", flush=True)
            success += 1; results.append((video_id, "OK", "chapters")); continue

    # ── Path C: Total failure ─────────────────────────────────────────────────
    print("  FAIL: no captions and no chapters", flush=True)
    with open(os.path.join(RAW_DIR, f"{video_id}_failed.txt"), "w") as fp:
        fp.write(f"No captions or chapters UTC:{NOW}\n")
    failed += 1; results.append((video_id, "FAIL", "no_data"))

# ── summary ──────────────────────────────────────────────────────────────────
print(f"\n===== {NOW} =====")
print(f"success={success} failed={failed} skipped={skipped}")
for vid, st, dt in results:
    print(f"  {vid}: {st} ({dt})")
