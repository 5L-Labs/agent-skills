#!/usr/bin/env python3
"""Deterministic orchestrator for the WaytoAGI digest pipelines.

Runs the full data-prep chain (fetch -> translate titles/summaries -> fetch full
article content -> translate bodies) and writes the enriched JSON to disk for a
downstream cron LLM to format/deliver.

Usage:
    waytoagi_pipeline.py daily   # -> $WAYTOAGI_OUT_DIR/wt_daily_full.json
    waytoagi_pipeline.py weekly  # -> $WAYTOAGI_OUT_DIR/wt_week_full.json

Output goes to a DURABLE, non-skill directory (default
/opt/data/cache/waytoagi) — never /tmp, which is wiped on container restart,
and never inside the skill dir, which the nightly consumption rebuild deletes.
The cron LLM reads that file and formats the digest — it never runs the heavy
chain itself, so it stays under the foreground timeout and never needs to
background/self-approve.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from waytoagi_translate import _needs_translation

WTR = os.environ.get("WAYTOAGI_READER_DIR") or str(Path(__file__).resolve().parents[1])
# Sibling helper scripts (translate/content) live in the SAME directory as this
# pipeline — in the consumption skill dir (/opt/data/skills/.../scripts/), NOT
# under the repo's scripts/ dir. Resolve them relative to this file so the
# prep works regardless of which copy is invoked.
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
# The waytoagi_reader package lives at <waytoagi-reader dir>/src. The cron venv
# (/opt/hermes/.venv) does NOT have it installed (only the system python does),
# so we must put the reader src on PYTHONPATH for whichever interpreter runs us.
# The reader dir is the parent of scripts/; its src/ sits beside scripts/.
READER_SRC = os.path.join(os.environ.get("WAYTOAGI_READER_DIR") or os.path.dirname(SCRIPTS), "src")
PY = sys.executable  # inherit the interpreter that launched us (cron venv, etc.)
# Merge env so subprocesses can import waytoagi_reader from the consumption copy.
SUBENV = dict(os.environ)
SUBENV["PYTHONPATH"] = READER_SRC + (os.pathsep + SUBENV["PYTHONPATH"]
                                     if SUBENV.get("PYTHONPATH") else "")
HOST = os.environ.get("WAYTOAGI_TRANSLATE_HOST", "http://192.168.100.10:11434")
MODEL = os.environ.get("WAYTOAGI_TRANSLATE_MODEL", "qwen3.8-27b-instruct-mtp-d3")
# Durable handoff dir: survives container restarts (/tmp does not) and stays
# OUTSIDE the skill dir (the nightly consumption rebuild wipes anything the
# repo does not track). Override with WAYTOAGI_OUT_DIR.
OUT_DIR = Path(os.environ.get("WAYTOAGI_OUT_DIR", "/opt/data/cache/waytoagi"))
OUT = {  # scope -> (output_path, translate args)
    "daily": (str(OUT_DIR / "wt_daily_full.json"), ["--latest-day"]),
    "weekly": (str(OUT_DIR / "wt_week_full.json"), []),
}

# Per-scope subprocess timeouts (seconds). Weekly is far heavier (all items
# vs. one day) and cold-cache runs must not be killed by a daily-sized budget.
TIMEOUTS = {
    "fetch":    {"daily": 130, "weekly": 130},
    "translate": {"daily": 200, "weekly": 900},
    "content":  {"daily": 1100, "weekly": 2400},
}

# Weekly full-body work is unbounded: seven days of articles cannot finish inside
# any sane cap against a local model, which is exactly why every weekly run timed
# out and reported a failure. Cap how many bodies get translated; the rest of the
# week keeps title_en/summary_en, which is what a weekly synthesis needs.
WEEKLY_CONTENT_LIMIT = int(os.environ.get("WAYTOAGI_WEEKLY_MAX_ARTICLES", "30"))


def run(cmd, **kw):
    kw.setdefault("env", SUBENV)
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] not in OUT:
        print("usage: waytoagi_pipeline.py <daily|weekly>", file=sys.stderr)
        return 2
    scope = args[0]
    out_path, trans_extra = OUT[scope]
    t0 = time.time()

    # 1. fetch flat
    r = run([PY, "-m", "waytoagi_reader.cli", "update-log", "--flatten", "--no-cache"],
            cwd=WTR, timeout=TIMEOUTS["fetch"][scope])
    if r.returncode != 0 or not r.stdout.strip():
        print(f"[err] fetch failed: {r.stderr[-300:]}", file=sys.stderr)
        return 1
    flat = r.stdout

    if scope == "weekly":
        # The 7-day section also carries section/nav links as day-less items
        # (e.g. the 历史更新 archive mention). They are not part of the week's
        # updates, and the archive body is enormous (17k+ zh chars), so they
        # waste translation time and pollute the digest. Drop them.
        try:
            _doc = json.loads(flat)
            _all = _doc.get("items", [])
            _kept = [i for i in _all if i.get("day")]
            _doc["items"] = _kept
            flat = json.dumps(_doc, ensure_ascii=False)
            print(f"[info] {scope}: dropped {len(_all) - len(_kept)} day-less (nav/archive) item(s)",
                  file=sys.stderr)
        except (ValueError, TypeError) as e:
            print(f"[err] fetch output is not JSON: {e}", file=sys.stderr)
            return 1

    # 2. translate titles/summaries
    tr = run([PY, f"{SCRIPTS}/waytoagi_translate.py",
              "--host", HOST, "--model", MODEL] + trans_extra,
             input=flat, timeout=TIMEOUTS["translate"][scope])
    if tr.returncode != 0:
        print(f"[err] translate failed: {tr.stderr[-300:]}", file=sys.stderr)
        return 1
    try:
        translated = json.loads(tr.stdout)
        for item in translated["items"]:
            for field in ("title", "summary"):
                if _needs_translation(item.get(field) or ""):
                    if not isinstance(item.get(field + "_en"), str) or not item[field + "_en"].strip():
                        raise ValueError(f"Missing {field}_en")
    except (ValueError, KeyError, TypeError) as e:
        print(f"[err] incomplete title/summary output: {e}", file=sys.stderr)
        return 1
    print(f"[info] {scope}: titles/summaries translated in {time.time()-t0:.0f}s", file=sys.stderr)

    # 3. full article content + translate (the heavy part; this script IS the long runner)
    fc = None
    content_cmd = [PY, f"{SCRIPTS}/waytoagi_content.py", "--host", HOST, "--model", MODEL]
    if scope == "weekly" and WEEKLY_CONTENT_LIMIT > 0:
        content_cmd += ["--limit", str(WEEKLY_CONTENT_LIMIT)]
        print(f"[info] {scope}: capping full-body translation at {WEEKLY_CONTENT_LIMIT} article(s)",
              file=sys.stderr)
    try:
        fc = run(content_cmd,
                 input=tr.stdout, timeout=TIMEOUTS["content"][scope])
    except subprocess.TimeoutExpired:
        print(f"[err] content stage timed out after {TIMEOUTS['content'][scope]}s", file=sys.stderr)
    if fc is not None and fc.returncode != 0:
        print(f"[err] content failed (rc={fc.returncode}): {fc.stderr[-300:]}", file=sys.stderr)
        fc = None
    payload = None
    if fc is not None:
        try:
            enriched = json.loads(fc.stdout)
            if len(enriched["items"]) != len(translated["items"]):
                raise ValueError("Content stage changed item count")
            usable = 0
            capped = 0
            limited = scope == "weekly" and WEEKLY_CONTENT_LIMIT > 0
            for source, item in zip(translated["items"], enriched["items"]):
                if any(item.get(key) != value for key, value in source.items() if key not in ("content_zh", "content_en")):
                    raise ValueError("Content stage changed source item")
                if not source.get("url"):
                    continue
                if item.get("content_error"):
                    # Per-article fetch/render failure. The content stage degrades
                    # instead of dying; the item falls back to title_en/summary_en.
                    print(f"[warn] {scope}: no body for {source['url']}: {item['content_error']}", file=sys.stderr)
                    continue
                for field in ("content_zh", "content_en"):
                    if not isinstance(item.get(field), str) or not item[field].strip():
                        if limited:
                            # The body cap means most items are intentionally left
                            # with title/summary only. Mark them the same way a
                            # fetch failure is marked so the validator accepts the
                            # run instead of discarding every body it did get.
                            item["content_error"] = (
                                f"beyond the weekly body cap ({WEEKLY_CONTENT_LIMIT} articles)")
                            capped += 1
                            break
                        raise ValueError(f"Missing {field}")
                else:
                    usable += 1
            if not usable and any(i.get("url") for i in enriched["items"]):
                raise ValueError("No article produced content")
            if usable:
                print(f"[info] {scope}: {usable} article(s) with full translated bodies", file=sys.stderr)
            if capped:
                enriched["content_capped"] = capped
                enriched["content_cap_limit"] = WEEKLY_CONTENT_LIMIT
                print(f"[info] {scope}: {capped} article(s) beyond the {WEEKLY_CONTENT_LIMIT}-article "
                      f"body cap (title/summary only)", file=sys.stderr)
            payload = json.dumps(enriched, ensure_ascii=False)
        except (ValueError, KeyError, TypeError) as e:
            print(f"[err] incomplete article output: {e}", file=sys.stderr)
        if payload is not None:
            print(f"[info] {scope}: content translated in {time.time()-t0:.0f}s", file=sys.stderr)
    if payload is None:
        # Degrade, don't die: hand the delivery job a FRESH titles/summaries
        # file (content_error set, bodies empty) so the digest still arrives
        # with current-day items instead of silently re-delivering a stale one.
        # The degradation is recorded IN the JSON so the delivery job can say so
        # out loud; it is not a job failure (see the return below).
        print(f"[warn] {scope}: content stage unavailable — writing degraded handoff (titles/summaries only)", file=sys.stderr)
        for item in translated["items"]:
            item.setdefault("content_zh", "")
            item.setdefault("content_en", "")
            item["content_error"] = "content stage unavailable (timeout or failure)"
        translated["content_degraded"] = True
        translated["content_degraded_reason"] = "content stage unavailable (timeout or failure)"
        payload = json.dumps(translated, ensure_ascii=False)
        degraded = True
    else:
        degraded = False

    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=output.name + ".", suffix=".tmp", delete=False) as f:
            temporary = Path(f.name)
            f.write(payload)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"[info] wrote {out_path} ({time.time()-t0:.0f}s total)", file=sys.stderr)
    if degraded:
        # A fresh, usable, self-describing handoff was written: the weekly digest
        # can still be produced (content_degraded=true tells the delivery job to
        # say so). Exiting non-zero here made this job report a failure on every
        # single weekly run, which buried the runs that actually broke.
        print(f"[warn] {scope}: handoff written DEGRADED (content_degraded=true) — treating as success",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
