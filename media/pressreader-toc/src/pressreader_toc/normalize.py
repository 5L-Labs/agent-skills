"""Three-pass normalization of a raw PressReader TOC response.

Pass 0 — clean: strip soft hyphens, normalize whitespace, drop null-article pages.
Pass 1 — merge continuations: union-find on ContFromPage/ContOnPage links.
Pass 2 — classify: story | continuation | teaser | filler.
Pass 3 — section/bucket: alias map + coarse bucket assignment.

Every raw entry gets a `kind`; nothing is deleted.
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

# Threshold (chars) separating teasers from real article starts.
# Fixture teasers: 38–139 chars; real starts: 259–269. Log 120–180 as borderline.
TEASER_TEXT_THRESHOLD = 150
TEASER_BORDERLINE_LOW = 120
TEASER_BORDERLINE_HIGH = 180

# Section name aliases (lowercased match → canonical)
_SECTION_ALIASES: dict[str, str] = {
    "life": "Life & Arts",
    "life & arts": "Life & Arts",
    "lex.": "Lex",
    "lex": "Lex",
    "the ft view": "The FT View",
    "ft big read": "FT Big Read",
    "house & home": "House & Home",
    "companies & markets": "Companies & Markets",
    "market data": "Market Data",
    "financial times share service": "Financial Times Share Service",
    "magazine": "Magazine",
    "front page": "Front Page",
    "international": "International",
    "books": "Books",
    "arts": "Arts",
    "style": "Style",
    "travel": "Travel",
    "food & drink": "Food & Drink",
    "opinion": "Opinion",
    "htsi": "HTSI",
}

# Coarse bucket for each canonical section name (substring match, ordered)
_BUCKET_RULES: list[tuple[str, str]] = [
    ("Life & Arts", "life-arts"),
    ("Life", "life-arts"),
    ("Arts", "books-arts-travel-style-food"),
    ("Books", "books-arts-travel-style-food"),
    ("Style", "books-arts-travel-style-food"),
    ("Travel", "books-arts-travel-style-food"),
    ("Food", "books-arts-travel-style-food"),
    ("House & Home", "house-home"),
    ("Magazine", "magazine"),
    ("HTSI", "htsi"),
    ("Market Data", "data"),
    ("Share Service", "data"),
]

# Titles that are always fillers (puzzles, crosswords, standing features)
_FILLER_TITLE_PATTERNS = re.compile(
    r"^(POLYMATH|CROSSWORD|CHESS|BRIDGE|i\s*/\s*DETAILS)$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# helpers


def _clean_str(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.replace("­", "")  # soft hyphen
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _canonical_section(raw: str) -> tuple[str, Optional[str]]:
    """Split 'Magazine | America At 250' → ('Magazine', 'America At 250').
    Apply alias map to left side. Return (section, theme).
    """
    parts = raw.split("|", 1)
    sec = parts[0].strip()
    theme = parts[1].strip() if len(parts) > 1 else None
    alias_key = sec.lower()
    sec = _SECTION_ALIASES.get(alias_key, sec)
    return sec, theme


def _bucket(section: str) -> str:
    for fragment, bucket in _BUCKET_RULES:
        if fragment.lower() in section.lower():
            return bucket
    return "main"


# ---------------------------------------------------------------------------
# union-find


class _UF:
    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        self._parent[self.find(a)] = self.find(b)


# ---------------------------------------------------------------------------
# main entry point


def normalize(raw: dict) -> list[dict]:
    """Return a flat list of normalized entry dicts (one per logical story/teaser/filler).

    Each entry has:
      kind          : 'story' | 'teaser' | 'filler' | 'continuation'
      id            : primary PressReader Id (int)
      toc_ids       : list[int] of all raw Ids merged into this entry
      uid           : PressReader Uid
      title         : str
      byline        : str
      text          : str  (longest snippet among merged fragments)
      page          : int  (start page)
      pages         : list[int]
      section       : str
      theme         : str | null
      bucket        : str
      teaser_for    : int | null  (best-guess target Id for teasers)
      match_status  : 'pending'
      ft_url        : null
      ft_uuid       : null
      match_score   : null
    """
    pages = raw.get("Pages") or []

    # ------------------------------------------------------------------
    # Pass 0: flatten and clean
    flat: list[dict] = []
    for page in pages:
        articles = page.get("Articles")
        if not articles:
            continue
        sec_raw = _clean_str(page.get("SectionName") or page.get("UnhyphenatedSectionName") or "")
        pg_num = page.get("PageNumber") or 0
        for a in articles:
            title = _clean_str(a.get("Title"))
            byline = _clean_str(a.get("Byline"))
            text = _clean_str(a.get("Text"))
            flat.append({
                "_id": a.get("Id"),
                "_uid": a.get("Uid"),
                "_title": title,
                "_byline": byline,
                "_text": text,
                "_page": a.get("Page") or pg_num,
                "_sec_raw": sec_raw,
                "_cont_on": a.get("ContOnPage"),
                "_cont_from": a.get("ContFromPage"),
                "_h": a.get("H") or 0,
                "_w": a.get("W") or 0,
            })

    # index: page → list of entries on that page
    by_page: dict[int, list[dict]] = {}
    for e in flat:
        by_page.setdefault(e["_page"], []).append(e)

    # index by id
    by_id: dict[int, dict] = {e["_id"]: e for e in flat if e["_id"] is not None}

    # ------------------------------------------------------------------
    # Pass 1: merge continuations via union-find
    uf = _UF()
    for e in flat:
        cont_from = e.get("_cont_from")
        if cont_from is None:
            continue
        # Find entries on page `cont_from` that point back to this entry's page
        candidates = [
            p for p in by_page.get(cont_from, [])
            if p.get("_cont_on") == e["_page"]
        ]
        if len(candidates) == 1:
            uf.union(e["_id"], candidates[0]["_id"])
        elif len(candidates) > 1:
            # Tie-break by title similarity
            best = max(candidates, key=lambda c: _title_similarity(c["_title"], e["_title"]))
            uf.union(e["_id"], best["_id"])
        # else: leave standalone

    # Group entries by their root id
    root_groups: dict[int, list[dict]] = {}
    for e in flat:
        root = uf.find(e["_id"])
        root_groups.setdefault(root, []).append(e)

    # ------------------------------------------------------------------
    # Pass 2 + 3: classify and assign sections

    results: list[dict] = []

    # Pre-build a map of page → list of story entries (for teaser_for lookup),
    # populated as we go; use a first-pass collect of all page entries.
    page_story_candidates: dict[int, list[dict]] = {}

    for root_id, group in root_groups.items():
        # Determine the root (start) entry: lowest page number
        root_entry = min(group, key=lambda e: e["_page"])
        longest_text = max((e["_text"] for e in group), key=len)

        all_pages = sorted({e["_page"] for e in group})
        all_ids = [e["_id"] for e in group if e["_id"] is not None]
        is_merged = len(group) > 1

        title = root_entry["_title"]
        byline = root_entry["_byline"]
        text = longest_text
        page = root_entry["_page"]
        sec_raw = root_entry["_sec_raw"]
        cont_on = root_entry.get("_cont_on")

        section, theme = _canonical_section(sec_raw)
        bucket = _bucket(section)

        # Classification
        # Check for known filler patterns first (puzzles, standing features)
        if title and _FILLER_TITLE_PATTERNS.match(title):
            kind = "filler"
        elif is_merged:
            # Already merged — the fragments become the single story entry
            kind = "story"
        elif cont_on is not None:
            # Dangling ContOnPage (no fragment linked back)
            text_len = len(text)
            if TEASER_BORDERLINE_LOW <= text_len <= TEASER_BORDERLINE_HIGH:
                logger.debug(
                    "Borderline teaser/story: %r len=%d page=%d", title, text_len, page
                )
            kind = "teaser" if text_len < TEASER_TEXT_THRESHOLD else "story"
        else:
            # No continuation links
            if not title:
                kind = "filler"
            elif not byline and len(text) < 40:
                kind = "filler"
            else:
                kind = "story"

        entry: dict = {
            "kind": kind,
            "id": root_id,
            "toc_ids": all_ids,
            "uid": root_entry["_uid"],
            "title": title,
            "byline": byline,
            "text": text,
            "page": page,
            "pages": all_pages,
            "section": section,
            "theme": theme,
            "bucket": bucket,
            "teaser_for": None,
            "match_status": "pending",
            "ft_url": None,
            "ft_uuid": None,
            "match_score": None,
        }
        results.append(entry)

        # Track stories by page for teaser_for lookup
        if kind == "story":
            page_story_candidates.setdefault(page, []).append(entry)

    # Resolve teaser_for: for each teaser, find best-match story on cont_on page
    root_cont_on: dict[int, Optional[int]] = {}
    for e in flat:
        rid = uf.find(e["_id"])
        if e["_id"] == rid:  # only from root entries
            root_cont_on[rid] = e.get("_cont_on")

    for entry in results:
        if entry["kind"] != "teaser":
            continue
        cont_on = root_cont_on.get(entry["id"])
        if cont_on is None:
            continue
        candidates = page_story_candidates.get(cont_on, [])
        if not candidates:
            continue
        best = max(candidates, key=lambda s: _title_similarity(s["title"], entry["title"]))
        score = _title_similarity(best["title"], entry["title"])
        if score >= 0.75:
            entry["teaser_for"] = best["id"]

    return results
