"""Map PressReader stories to ft.com URLs via `ft search`.

Runs `ft search "<title>" --limit N --json-errors` as a subprocess (same pattern
as data_as_podcasts FTIngestor, but with careful exit-code handling).

Abort immediately on exit code 2 (SESSION_EXPIRED), persist partial state.
Back off exponentially on 403/429-style upstream errors, then abort resumably.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import subprocess
import sys
import time
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

# Default weekend-only buckets — add --all to include main/lex/opinion/etc.
DEFAULT_BUCKETS = frozenset({
    "life-arts",
    "house-home",
    "magazine",
    "htsi",
    "books-arts-travel-style-food",
})

# Throttle between ft search calls — www.ft.com/search rate-limits quickly
THROTTLE_BASE_S = 10.0
THROTTLE_JITTER_S = 2.0

# Score threshold below which a match is accepted with low_confidence flag
LOW_CONFIDENCE_THRESHOLD = 0.60

# Titles with fewer than this many "distinctive" tokens require byline corroboration
GENERIC_TITLE_TOKEN_MIN = 3

# Stopwords for token extraction
_STOPWORDS = frozenset(
    "a an the of in on at to for by with from and or but is are was were be been "
    "this that it its".split()
)


def _norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"^htsi[:\s]+", "", t)  # strip HTSI prefix from web titles
    t = re.sub(r"[''\"'\"()&%$#@!?.,;:–—-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _tokens(t: str) -> set[str]:
    return {w for w in _norm_title(t).split() if w not in _STOPWORDS and len(w) > 1}


def _score(print_title: str, web_title: str) -> float:
    nt_p = _norm_title(print_title)
    nt_w = _norm_title(web_title)
    sm = SequenceMatcher(None, nt_p, nt_w).ratio()
    toks_p = _tokens(print_title)
    toks_w = _tokens(web_title)
    union = toks_p | toks_w
    jaccard = len(toks_p & toks_w) / len(union) if union else 0.0
    return max(sm, jaccard)


def _byline_surnames(byline: str) -> set[str]:
    """Extract lowercased surnames from messy bylines.
    Handles: 'By Jamie Dimon Jamie Dimon is the...', 'jo.ellison@ft.com', 'JOHN SMITH — LONDON'.
    """
    # Strip emails
    byline = re.sub(r"\S+@\S+", "", byline)
    # Strip bio sentences (anything after a verb-ish pattern or dash sequences)
    byline = re.sub(r"\s+(is |was |are |has )[^,]*", "", byline, flags=re.IGNORECASE)
    # Strip locations after —
    byline = re.sub(r"—[A-Z ]+$", "", byline)
    # Strip "By" prefix
    byline = re.sub(r"^by\s+", "", byline, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z]{2,}", byline)
    # Surnames tend to be capitalized and > 2 chars; grab all words that could be names
    return {w.lower() for w in words if w[0].isupper()}


def _is_generic_title(title: str) -> bool:
    return len(_tokens(title)) < GENERIC_TITLE_TOKEN_MIN


def _extract_search_words(text: str, n: int = 6) -> str:
    """Pick the n most distinctive (longest, non-stopword) words from a text snippet."""
    words = re.findall(r"[a-zA-Z]{4,}", text)
    unique = list(dict.fromkeys(w.lower() for w in words if w.lower() not in _STOPWORDS))
    # Sort by length descending — longer words are more distinctive
    unique.sort(key=len, reverse=True)
    return " ".join(unique[:n])


def _extract_body_text(structured: dict) -> str:
    """Recursively pull text values out of the ft article body tree."""
    parts: list[str] = []
    def walk(node: dict) -> None:
        if node.get("type") == "text":
            parts.append(node.get("value", ""))
        for child in node.get("children", []):
            walk(child)
    walk(structured.get("tree", {}))
    return " ".join(parts)


def _body_score(print_text: str, web_body: str) -> float:
    """Similarity between the print snippet and the opening of the web body.

    Compares the first 300 chars of each using SequenceMatcher — enough to
    catch identical or near-identical opening sentences.
    """
    a = _norm_title(print_text[:300])
    b = _norm_title(web_body[:300])
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _run_ft_article(uuid: str, ft_binary: str) -> Optional[str]:
    """Fetch article body text via `ft article {uuid}`. Returns flat body text or None."""
    cmd = [ft_binary, "article", uuid, "--json-errors"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except Exception as exc:
        logger.warning("ft article %s failed: %s", uuid, exc)
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "{}")
        structured = (data.get("body") or {}).get("structured") or {}
        return _extract_body_text(structured)
    except Exception:
        return None


def _body_match_candidates(
    print_text: str, candidates: list[dict], ft_binary: str, top_n: int = 5
) -> tuple[float, Optional[dict]]:
    """Fetch article bodies for candidates and return the best body-text match."""
    best_score, best_result = 0.0, None
    for r in candidates[:top_n]:
        uuid = r.get("uuid") or ""
        if not uuid:
            continue
        web_body = _run_ft_article(uuid, ft_binary)
        if web_body:
            bs = _body_score(print_text, web_body)
            logger.debug("body_score → %s: %.3f", r.get("title", "")[:40], bs)
            if bs > best_score:
                best_score, best_result = bs, r
    return best_score, best_result


def _run_ft_search(
    query: str,
    limit: int,
    ft_binary: str,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> tuple[int, list[dict]]:
    """Run `ft search <query> --limit N --json-errors`.
    Returns (exit_code, results_list). Results list is empty on error.
    """
    cmd = [ft_binary, "search", query, "--limit", str(limit), "--json-errors"]
    if date_from:
        cmd += ["--date-from", date_from]
    if date_to:
        cmd += ["--date-to", date_to]
    logger.debug("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        try:
            err = json.loads(proc.stdout or "{}").get("error", {})
        except Exception:
            err = {}
        logger.warning("ft search exited %d: %s", proc.returncode, err)
        return proc.returncode, []
    try:
        data = json.loads(proc.stdout or "{}")
        return 0, data.get("results", [])
    except json.JSONDecodeError:
        logger.warning("ft search non-JSON output: %s", proc.stdout[:200])
        return 1, []


def _throttle() -> None:
    time.sleep(THROTTLE_BASE_S + random.uniform(-THROTTLE_JITTER_S, THROTTLE_JITTER_S))


def match_stories(
    entries: list[dict],
    issue_date: date,
    *,
    buckets: Optional[frozenset[str]] = None,
    min_score: float = 0.60,
    limit: int = 5,
    retry_unmatched: bool = False,
    dry_run: bool = False,
    ft_binary: str = "ft",
) -> tuple[list[dict], dict]:
    """Attempt to match stories in `entries` to ft.com URLs.

    Modifies entries in-place (call store.update_entries after each batch).
    Returns (updated_entries, report_dict).
    """
    if buckets is None:
        buckets = DEFAULT_BUCKETS

    pending = [
        e for e in entries
        if e["kind"] == "story"
        and e["bucket"] in buckets
        and (
            e["match_status"] == "pending"
            or (retry_unmatched and e["match_status"] == "unmatched")
        )
    ]

    if dry_run:
        print(f"Would search {len(pending)} stories in buckets: {sorted(buckets)}")
        for e in pending:
            print(f"  {e['bucket']:30} {e['title']!r}")
        return entries, {"dry_run": True, "would_search": len(pending)}

    matched = 0
    unmatched = 0
    low_confidence = 0
    aborted = False
    abort_reason = ""
    consecutive_upstream = 0

    for e in pending:
        rc, results = _run_ft_search(e["title"], limit, ft_binary)

        if rc == 2:
            aborted = True
            abort_reason = "SESSION_EXPIRED (401) — re-paste FT_COOKIE from browser"
            print(f"ABORTING: {abort_reason}", file=sys.stderr)
            break

        if rc != 0:
            consecutive_upstream += 1
            if consecutive_upstream >= 3:
                aborted = True
                abort_reason = f"upstream errors (rc={rc}) persisted — possible rate limit, try again later"
                print(f"ABORTING: {abort_reason}", file=sys.stderr)
                break
            wait = 60.0 * consecutive_upstream
            logger.warning("upstream error rc=%d, backing off %.0fs", rc, wait)
            time.sleep(wait)
            rc2, results = _run_ft_search(e["title"], limit, ft_binary)
            if rc2 == 2:
                aborted = True
                abort_reason = "SESSION_EXPIRED (401) — re-paste FT_COOKIE from browser"
                print(f"ABORTING: {abort_reason}", file=sys.stderr)
                break
            if rc2 != 0:
                consecutive_upstream += 1
                if consecutive_upstream >= 3:
                    aborted = True
                    abort_reason = f"upstream errors persisted after backoff (rc={rc2})"
                    print(f"ABORTING: {abort_reason}", file=sys.stderr)
                    break
                results = []
            else:
                consecutive_upstream = 0
        else:
            consecutive_upstream = 0

        # Score candidates
        issue_dt = issue_date
        best_score = 0.0
        best_result: Optional[dict] = None

        generic = _is_generic_title(e["title"])
        print_surnames = _byline_surnames(e.get("byline") or "")

        for r in results:
            score = _score(e["title"], r.get("title") or "")

            # Date boost: published within ±4 days of issue
            pub_str = r.get("published") or ""
            if pub_str:
                try:
                    from datetime import datetime
                    pub_d = datetime.fromisoformat(pub_str.replace("Z", "+00:00")).date()
                    if abs((pub_d - issue_dt).days) <= 4:
                        score = min(1.0, score + 0.1)
                except Exception:
                    pass

            # Byline surname boost
            if print_surnames:
                web_surnames = _byline_surnames(r.get("author") or "")
                if print_surnames & web_surnames:
                    score = min(1.0, score + 0.1)

            if score > best_score:
                best_score = score
                best_result = r

        if best_result and best_score >= min_score:
            if generic and not (print_surnames & _byline_surnames(best_result.get("author") or "")):
                e["match_status"] = "matched"
                e["ft_uuid"] = best_result.get("uuid")
                e["ft_url"] = best_result.get("url")
                e["match_score"] = round(best_score, 3)
                e["low_confidence"] = True
                low_confidence += 1
            else:
                e["match_status"] = "matched"
                e["ft_uuid"] = best_result.get("uuid")
                e["ft_url"] = best_result.get("url")
                e["match_score"] = round(best_score, 3)
                e["low_confidence"] = best_score < 0.75
                if e["low_confidence"]:
                    low_confidence += 1
            matched += 1
        else:
            # Title score too low — try three progressively broader strategies
            print_text = e.get("text") or ""
            body_best_score = 0.0
            body_best_result: Optional[dict] = None
            abort_now = False

            # Strategy 1: body-text match against title-search candidates
            if print_text and results:
                body_best_score, body_best_result = _body_match_candidates(
                    print_text, results, ft_binary
                )

            # Strategy 2: author-scoped search (surname + ±7-day date window)
            if body_best_score < 0.70 and print_surnames:
                primary_surname = max(print_surnames, key=len)
                date_from = (issue_date - timedelta(days=7)).isoformat()
                date_to = (issue_date + timedelta(days=1)).isoformat()
                _throttle()
                rc2, author_results = _run_ft_search(
                    primary_surname, 20, ft_binary,
                    date_from=date_from, date_to=date_to,
                )
                if rc2 == 2:
                    aborted = True
                    abort_reason = "SESSION_EXPIRED (401) — re-paste FT_COOKIE from browser"
                    print(f"ABORTING: {abort_reason}", file=sys.stderr)
                    abort_now = True
                elif rc2 == 0 and author_results and print_text:
                    bs, br = _body_match_candidates(print_text, author_results, ft_binary)
                    if bs > body_best_score:
                        body_best_score, body_best_result = bs, br

            # Strategy 3: distinctive words from print body text
            if not abort_now and body_best_score < 0.70 and print_text:
                words = _extract_search_words(print_text)
                if words:
                    _throttle()
                    rc3, word_results = _run_ft_search(words, 10, ft_binary)
                    if rc3 == 2:
                        aborted = True
                        abort_reason = "SESSION_EXPIRED (401) — re-paste FT_COOKIE from browser"
                        print(f"ABORTING: {abort_reason}", file=sys.stderr)
                        abort_now = True
                    elif rc3 == 0 and word_results:
                        bs, br = _body_match_candidates(print_text, word_results, ft_binary)
                        if bs > body_best_score:
                            body_best_score, body_best_result = bs, br

            if abort_now:
                break

            if body_best_result and body_best_score >= 0.70:
                e["match_status"] = "matched"
                e["ft_uuid"] = body_best_result.get("uuid")
                e["ft_url"] = body_best_result.get("url")
                e["match_score"] = round(body_best_score, 3)
                e["low_confidence"] = True
                e["match_source"] = "body_text"
                low_confidence += 1
                matched += 1
            else:
                e["match_status"] = "unmatched"
                e["match_score"] = round(best_score, 3) if best_result else None
                unmatched += 1

        _throttle()

    report = {
        "searched": matched + unmatched,
        "matched": matched,
        "unmatched": unmatched,
        "low_confidence": low_confidence,
        "aborted": aborted,
        "abort_reason": abort_reason if aborted else None,
        "unmatched_titles": [
            {"title": e["title"], "bucket": e["bucket"], "score": e.get("match_score")}
            for e in entries
            if e["kind"] == "story" and e["match_status"] == "unmatched"
            and e["bucket"] in buckets
        ],
        "low_confidence_titles": [
            {"title": e["title"], "bucket": e["bucket"], "ft_url": e.get("ft_url"), "score": e.get("match_score")}
            for e in entries
            if e["kind"] == "story" and e.get("low_confidence")
            and e["bucket"] in buckets
        ],
    }
    return entries, report
