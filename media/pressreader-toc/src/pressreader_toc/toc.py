"""Fetch, normalize and store a PressReader TOC for one or more issues on a date."""
from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from typing import Optional

from .client import PRClient
from .errors import NotFoundError, UpstreamError
from .normalize import normalize
from .store import load_normalized, load_raw, normalized_exists, save_normalized, save_raw

logger = logging.getLogger(__name__)

# CID → publication name
PUBS = {
    "v99e": "Financial Times US",
    "9lh5": "HTSI US",
}

WEEKEND_PUBS = ("v99e", "9lh5")


def _issue_key(cid: str, d: date) -> str:
    return f"{cid}{d.strftime('%Y%m%d')}00000000001001"


def _most_recent_saturday(today: date) -> date:
    days_since = (today.weekday() + 2) % 7  # Mon=0 … Sat=5 → days back to Saturday
    return today - timedelta(days=days_since)


def resolve_date(spec: str) -> date:
    """Parse 'today', 'weekend', or an ISO date string."""
    if spec == "today":
        return date.today()
    if spec == "weekend":
        d = date.today()
        return d if d.weekday() == 5 else _most_recent_saturday(d)
    try:
        return date.fromisoformat(spec)
    except ValueError as e:
        raise ValueError(
            f"Invalid date {spec!r} — use YYYY-MM-DD, 'today', or 'weekend'"
        ) from e


def _fetch_one(
    cid: str,
    issue_date: date,
    *,
    client: Optional[PRClient] = None,
    refresh: bool = False,
) -> dict:
    """Fetch TOC for one publication. Returns normalized issue doc."""
    if not refresh and normalized_exists(cid, issue_date):
        doc = load_normalized(cid, issue_date)
        if doc:
            doc["_cached"] = True
            return doc

    # Try to re-normalize from raw if available (schema bump scenario)
    if not refresh:
        raw = load_raw(cid, issue_date)
        if raw:
            entries = normalize(raw)
            save_normalized(cid, issue_date, entries)
            return {
                "schema_version": 1,
                "cid": cid,
                "issue_date": issue_date.isoformat(),
                "entries": entries,
                "_renormalized": True,
            }

    client = client or PRClient()
    raw = client.fetch_toc(_issue_key(cid, issue_date))
    save_raw(cid, issue_date, raw)
    entries = normalize(raw)
    save_normalized(cid, issue_date, entries)
    return {
        "schema_version": 1,
        "cid": cid,
        "issue_date": issue_date.isoformat(),
        "entries": entries,
    }


def fetch_toc(
    spec: str,
    *,
    pub: str = "all",
    refresh: bool = False,
    client: Optional[PRClient] = None,
) -> dict:
    """Fetch TOC(s) for the given date spec and pub filter.

    Returns:
      {schema_version, date, issues: [{cid, pub_name, entries, warnings: [...]}]}
    """
    issue_date = resolve_date(spec)
    is_saturday = issue_date.weekday() == 5

    if pub == "all":
        cids = list(PUBS.keys()) if is_saturday else ["v99e"]
    elif pub == "ft":
        cids = ["v99e"]
    elif pub == "htsi":
        cids = ["9lh5"]
    else:
        raise ValueError(f"Unknown pub {pub!r} — use ft, htsi, or all")

    issues = []
    for cid in cids:
        warnings: list[str] = []
        try:
            doc = _fetch_one(cid, issue_date, client=client, refresh=refresh)
            issues.append({
                "cid": cid,
                "pub_name": PUBS.get(cid, cid),
                "issue_date": issue_date.isoformat(),
                "cached": doc.get("_cached", False),
                "warnings": warnings,
                "entries": doc["entries"],
            })
        except NotFoundError:
            msg = (
                f"{PUBS.get(cid, cid)} issue not found for {issue_date} "
                "(paper may not be on the CDN yet — retry later, or this date has no issue)"
            )
            if pub == "all":
                print(f"WARNING: {msg}", file=sys.stderr)
                issues.append({
                    "cid": cid,
                    "pub_name": PUBS.get(cid, cid),
                    "issue_date": issue_date.isoformat(),
                    "not_found": True,
                    "warnings": [msg],
                    "entries": [],
                })
            else:
                raise NotFoundError(msg)
        except UpstreamError:
            raise

    story_count = sum(
        sum(1 for e in iss["entries"] if e["kind"] == "story")
        for iss in issues
    )
    return {
        "schema_version": 1,
        "date": issue_date.isoformat(),
        "issues": issues,
        "total_stories": story_count,
    }
