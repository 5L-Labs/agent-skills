#!/usr/bin/env python3
"""jargon-weekly-notify: deterministic weekly jargon digest (no_agent cron).

Posts the week's NEW jargon terms (first_seen within the last 7 days) to the
Signal "Weekly Updates" group, with meanings at all three complexity levels and
a per-source frequency breakdown from the registry's seen_in history.

Silent (empty stdout) when there are no new terms for the week. State kept in
/opt/data/references/jargon-weekly-posted.json keyed by ISO year-week so a
week is posted exactly once.

Usage: jargon_weekly_notify.py [--dry-run] [--self-test]
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

REGISTRY_PATHS = [
    "/opt/data/references/jargon-registry.json",
    "/opt/data/skills/research/jargon/references/jargon-registry.json",
    "/opt/data/repos/agent-skills/research/jargon/references/jargon-registry.json",
]
STATE_PATH = "/opt/data/references/jargon-weekly-posted.json"
SIGNAL_TARGET = "signal:Weekly AI Updates"
WINDOW_DAYS = 7

LEVEL_LABELS = {"kindergarten": "ELI5", "high-school": "School", "doctor": "PhD"}
SOURCE_LABELS = {
    "arxiv": "arXiv",
    "ai-news": "AI-news",
    "xdigest": "X digest",
    "x": "X",
    "hn-brief": "HN",
    "hn": "HN",
    "waytoagi": "WaytoAGI",
    "smol-ai": "AI-news",
}


def atomic_write(path, data):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def load_json(paths, required, what):
    for p in paths:
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    if required:
        print(f"ERROR: {what} not found at any of {paths}", file=sys.stderr)
        raise SystemExit(1)
    return None


def week_key():
    d = datetime.now(timezone.utc)
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def source_count(seen_in):
    """Count seen_in entries per source bucket."""
    counts = {}
    for entry in seen_in or []:
        src = entry.split(":", 1)[0]
        counts[src] = counts.get(src, 0) + 1
    return counts


def build_message(terms, registry):
    lines = [
        "Weekly AI updates — new jargon seen across this week's feeds:",
        "",
    ]
    for t in terms:
        entry = registry.get(t, {})
        pp = entry.get("plainspeak") or {}
        src_lvl = entry.get("source_level", "doctor")
        lines.append(f"• {t} (from {src_lvl}-level sources)")
        for lv in ("kindergarten", "high-school", "doctor"):
            d = pp.get(lv)
            if d:
                d = re.sub(r"\s+", " ", d).strip()
                if len(d) > 220:
                    d = d[:217].rstrip() + "..."
                lines.append(f"  {LEVEL_LABELS[lv]}: {d}")
        c = source_count(entry.get("seen_in"))
        if c:
            parts = ", ".join(
                f"{SOURCE_LABELS.get(s, s)} ×{n}" for s, n in sorted(c.items()))
            lines.append(f"  seen in: {parts}")
        first = entry.get("first_seen", "?")
        lines.append(f"  first seen: {first}")
        lines.append("")
    return "\n".join(lines).rstrip()


def send_signal(text, dry):
    if dry:
        print("[dry-run] would post to " + SIGNAL_TARGET + ":\n" + text)
        return True
    cmd = ["hermes", "send", "--to", SIGNAL_TARGET, "--", text]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"ERROR: hermes send failed rc={r.returncode}: {r.stderr[:300]}",
              file=sys.stderr)
    return r.returncode == 0


def main():
    dry = "--dry-run" in sys.argv
    self_test = "--self-test" in sys.argv

    registry = load_json(REGISTRY_PATHS, True, "jargon registry")
    terms = registry.get("terms", {})

    state = {}
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                state = json.load(f)
        except Exception:
            state = {}
    posted_weeks = set(state.get("posted_weeks", []))

    wk = week_key()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)) \
        .strftime("%Y-%m-%d")

    new_terms = []
    if wk in posted_weeks:
        # Already posted for this ISO week: stay silent, so a re-run (manual
        # trigger, catch-up, retry) can never double-post the same week.
        sys.exit(0)
    for t, e in sorted(terms.items(), key=lambda kv: kv[1].get("first_seen", "")):
        fs = e.get("first_seen", "")
        if fs >= cutoff:
            new_terms.append((t, e))

    if self_test:
        # Synthesize: pretend the 3 newest registry terms are new this week
        newest = sorted(terms.items(), key=lambda kv: kv[1].get("first_seen", ""))[-3:]
        fake = dict(newest)
        text = build_message(fake, terms)
        assert "• " in text and "ELI5" in text and "seen in" in text
        print("[self-test] render OK:\n" + text)
        print("[self-test] PASS")
        sys.exit(0)

    if not new_terms:
        # silent
        sys.exit(0)

    text = build_message([t for t, _ in new_terms], terms)
    if not send_signal(text, dry):
        sys.exit(1)

    if not dry:
        posted_weeks.add(wk)
        atomic_write(STATE_PATH, {"posted_weeks": sorted(posted_weeks)})

    print(f"jargon-weekly-notify: posted {len(new_terms)} new term(s) for {wk}")


main()
