"""prtoc CLI: toc | match | stories. JSON to stdout, errors to stderr."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from news_reader_base import add_common_flags, emit

from . import SCHEMA_VERSION
from .errors import NotFoundError, PressReaderError, UpstreamError


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="prtoc",
        description="PressReader FT table-of-contents fetcher and ft.com story matcher.",
    )
    p.add_argument("--json-errors", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    # --- toc ---
    pt = sub.add_parser("toc", help="Fetch and normalize the TOC for a date.")
    pt.add_argument("date", help="ISO date (2026-07-04), 'today', or 'weekend'.")
    pt.add_argument("--pub", choices=["ft", "htsi", "all"], default="all",
                    help="Publication(s) to fetch (default: all).")
    pt.add_argument("--refresh", action="store_true", help="Re-fetch even if cached.")
    add_common_flags(pt)

    # --- match ---
    pm = sub.add_parser("match", help="Map stories to ft.com URLs via ft search.")
    pm.add_argument("date", help="ISO date of a previously fetched issue.")
    pm.add_argument("--buckets", help="Comma-separated bucket names (default: weekend).")
    pm.add_argument("--all", dest="all_buckets", action="store_true",
                    help="Match all buckets including main news sections.")
    pm.add_argument("--min-score", type=float, default=0.60)
    pm.add_argument("--limit", type=int, default=5, help="ft search results per query.")
    pm.add_argument("--retry-unmatched", action="store_true")
    pm.add_argument("--dry-run", action="store_true",
                    help="Print queries without hitting ft.com.")
    pm.add_argument("--ft-binary", default="ft", help="Path to the ft CLI binary.")
    add_common_flags(pm)

    # --- stories ---
    ps = sub.add_parser("stories", help="Emit matched ft.com URLs for downstream use.")
    ps.add_argument("date", help="ISO date of a matched issue.")
    ps.add_argument("--buckets", help="Comma-separated bucket names (default: weekend).")
    ps.add_argument("--format", choices=["urls", "json"], default="urls")
    add_common_flags(ps)

    args = p.parse_args(argv)
    json_errors = getattr(args, "json_errors", False)

    try:
        if args.cmd == "toc":
            return _cmd_toc(args, json_errors)
        elif args.cmd == "match":
            return _cmd_match(args, json_errors)
        elif args.cmd == "stories":
            return _cmd_stories(args, json_errors)
        else:
            p.error(f"unknown command {args.cmd}")
            return 1
    except PressReaderError as e:
        return emit(None, json_errors=json_errors, error=e)


# ---------------------------------------------------------------------------

def _cmd_toc(args, json_errors: bool) -> int:
    from .toc import fetch_toc
    payload = fetch_toc(args.date, pub=args.pub, refresh=args.refresh)
    return emit(payload, json_errors=json_errors)


def _cmd_match(args, json_errors: bool) -> int:
    from datetime import date as dt
    from .match import match_stories, DEFAULT_BUCKETS
    from .store import load_normalized, update_entries
    from .toc import resolve_date

    issue_date = resolve_date(args.date)

    if args.all_buckets:
        buckets = None  # match.py uses None to mean "all"
    elif args.buckets:
        buckets = frozenset(b.strip() for b in args.buckets.split(","))
    else:
        buckets = DEFAULT_BUCKETS

    # Collect entries from all CIDs for this date
    from .toc import PUBS
    all_entries_by_cid: dict[str, list[dict]] = {}
    for cid in PUBS:
        doc = load_normalized(cid, issue_date)
        if doc:
            all_entries_by_cid[cid] = doc["entries"]

    if not all_entries_by_cid:
        raise NotFoundError(
            f"No normalized issue found for {issue_date}. "
            "Run `prtoc toc {date}` first."
        )

    total_report: dict = {"searched": 0, "matched": 0, "unmatched": 0,
                          "low_confidence": 0, "aborted": False, "abort_reason": None,
                          "unmatched_titles": [], "low_confidence_titles": []}
    aborted = False

    for cid, entries in all_entries_by_cid.items():
        updated, report = match_stories(
            entries,
            issue_date,
            buckets=buckets,
            min_score=args.min_score,
            limit=args.limit,
            retry_unmatched=args.retry_unmatched,
            dry_run=args.dry_run,
            ft_binary=args.ft_binary,
        )
        if not args.dry_run:
            update_entries(cid, issue_date, updated)

        for k in ("searched", "matched", "unmatched", "low_confidence"):
            total_report[k] += report.get(k, 0)
        total_report["unmatched_titles"].extend(report.get("unmatched_titles", []))
        total_report["low_confidence_titles"].extend(report.get("low_confidence_titles", []))

        if report.get("aborted"):
            aborted = True
            total_report["aborted"] = True
            total_report["abort_reason"] = report.get("abort_reason")
            break

    payload = {"schema_version": SCHEMA_VERSION, "date": issue_date.isoformat(),
               "report": total_report}
    rc = emit(payload, json_errors=json_errors)
    return 2 if aborted and total_report.get("abort_reason", "").startswith("SESSION_EXPIRED") else rc


def _cmd_stories(args, json_errors: bool) -> int:
    from .match import DEFAULT_BUCKETS
    from .store import load_normalized
    from .toc import resolve_date, PUBS

    issue_date = resolve_date(args.date)

    if args.buckets:
        buckets = frozenset(b.strip() for b in args.buckets.split(","))
    else:
        buckets = DEFAULT_BUCKETS

    stories = []
    for cid in PUBS:
        doc = load_normalized(cid, issue_date)
        if not doc:
            continue
        for e in doc["entries"]:
            if (e["kind"] == "story"
                    and e["match_status"] == "matched"
                    and e.get("ft_url")
                    and e["bucket"] in buckets):
                stories.append(e)

    if not stories:
        raise NotFoundError(
            f"No matched stories found for {issue_date} in buckets {sorted(buckets)}. "
            "Run `prtoc match {date}` first."
        )

    if args.format == "urls":
        for s in stories:
            print(s["ft_url"])
        return 0

    payload = {
        "schema_version": SCHEMA_VERSION,
        "date": issue_date.isoformat(),
        "buckets": sorted(buckets),
        "stories": stories,
    }
    return emit(payload, json_errors=json_errors)


if __name__ == "__main__":
    sys.exit(main())
