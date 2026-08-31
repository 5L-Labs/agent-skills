#!/usr/bin/env python3
"""Deterministic orchestrator for the WaytoAGI digest pipelines.

Runs the full data-prep chain (fetch -> translate titles/summaries -> fetch full
article content -> translate bodies) and writes the enriched JSON to disk for a
downstream cron LLM to format/deliver.

Usage:
    waytoagi_pipeline.py daily   # -> /tmp/wt_daily_full.json
    waytoagi_pipeline.py weekly  # -> /tmp/wt_week_full.json

Both write /tmp/wt_<scope>_full.json. The cron LLM reads that file and formats
the digest — it never runs the heavy chain itself, so it stays under the
foreground timeout and never needs to background/self-approve.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

WTR = "/opt/data/repos/agent-skills/media/waytoagi-reader"
HOST = os.environ.get("WAYTOAGI_TRANSLATE_HOST", "http://lunarbeacon.newyork.nicklange.family:11434")
MODEL = os.environ.get("WAYTOAGI_TRANSLATE_MODEL", "qwen3.8")
OUT = {  # scope -> (output_path, translate args)
    "daily": ("/tmp/wt_daily_full.json", ["--latest-day"]),
    "weekly": ("/tmp/wt_week_full.json", []),
}

# Per-scope subprocess timeouts (seconds). Weekly is far heavier (all items
# vs. one day) and cold-cache runs must not be killed by a daily-sized budget.
TIMEOUTS = {
    "fetch":    {"daily": 130, "weekly": 130},
    "translate": {"daily": 200, "weekly": 900},
    "content":  {"daily": 1100, "weekly": 2400},
}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main(argv=None) -> int:
    args = sys.argv[1:]
    if not args or args[0] not in OUT:
        print("usage: waytoagi_pipeline.py <daily|weekly>", file=sys.stderr)
        return 2
    scope = args[0]
    out_path, trans_extra = OUT[scope]
    t0 = time.time()

    # 1. fetch flat
    r = run(["python3", "-m", "waytoagi_reader.cli", "update-log", "--flatten", "--no-cache"],
            cwd=WTR, timeout=TIMEOUTS["fetch"][scope])
    if r.returncode != 0 or not r.stdout.strip():
        print(f"[err] fetch failed: {r.stderr[-300:]}", file=sys.stderr)
        return 1
    flat = r.stdout

    # 2. translate titles/summaries
    tr = run(["python3", f"{WTR}/scripts/waytoagi_translate.py",
              "--host", HOST, "--model", MODEL] + trans_extra,
             input=flat, timeout=TIMEOUTS["translate"][scope])
    if tr.returncode != 0:
        print(f"[err] translate failed: {tr.stderr[-300:]}", file=sys.stderr)
        return 1
    print(f"[info] {scope}: titles/summaries translated in {time.time()-t0:.0f}s", file=sys.stderr)

    # 3. full article content + translate (the heavy part; this script IS the long runner)
    fc = run(["python3", f"{WTR}/scripts/waytoagi_content.py",
              "--host", HOST, "--model", MODEL],
             input=tr.stdout, timeout=TIMEOUTS["content"][scope])
    if fc.returncode != 0:
        print(f"[err] content failed: {fc.stderr[-300:]}", file=sys.stderr)
        return 1
    print(f"[info] {scope}: content translated in {time.time()-t0:.0f}s", file=sys.stderr)

    with open(out_path, "w") as f:
        f.write(fc.stdout)
    print(f"[info] wrote {out_path} ({time.time()-t0:.0f}s total)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
