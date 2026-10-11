"""Tests for normalize.py — TDD, all based on committed fixtures."""
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

import pytest

from pressreader_toc.normalize import normalize

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def v99e_raw():
    return json.loads((FIXTURES / "toc_v99e_2026-07-04.json").read_text())


@pytest.fixture(scope="session")
def v99e_entries(v99e_raw):
    return normalize(v99e_raw)


@pytest.fixture(scope="session")
def htsi_raw():
    return json.loads((FIXTURES / "toc_9lh5_2026-07-04.json").read_text())


@pytest.fixture(scope="session")
def htsi_entries(htsi_raw):
    return normalize(htsi_raw)


# ---------------------------------------------------------------------------
# Kind counts (pin once algorithm is stable)

def test_v99e_kind_counts(v99e_entries):
    counts = Counter(e["kind"] for e in v99e_entries)
    assert counts["story"] == 124
    assert counts["teaser"] == 6
    assert counts["filler"] == 7
    assert len(v99e_entries) == 137


def test_no_unknown_kind(v99e_entries):
    bad = [e for e in v99e_entries if e["kind"] not in ("story", "teaser", "filler", "continuation")]
    assert bad == [], f"Unknown kinds: {[e['kind'] for e in bad]}"


# ---------------------------------------------------------------------------
# Soft hyphen removal

def test_no_soft_hyphens(v99e_entries):
    for e in v99e_entries:
        for field in ("title", "byline", "text"):
            assert "­" not in e[field], f"Soft hyphen in {field}: {e[field]!r}"


# ---------------------------------------------------------------------------
# Continuation chain: "The plot thickens" on p40+p41 in House & Home

def test_continuation_chain_merged(v99e_entries):
    """House & Home continuations are correctly merged into multi-page stories.

    'How to sell a home in a slow market' (p39) continues as 'Selling in a slow
    market' (p40) — these are the SAME article and should merge into one entry
    spanning pages [39, 40].

    'The plot thickens' (p40) continues on p41 — a SEPARATE article, merged into
    pages [40, 41].

    They must NOT be merged with each other.
    """
    house_home = [e for e in v99e_entries if e["bucket"] == "house-home"]

    sell = next((e for e in house_home if "sell" in e["title"].lower()), None)
    assert sell is not None, "Expected 'sell' story in house-home"
    assert sell["kind"] == "story"
    assert 39 in sell["pages"] and 40 in sell["pages"], f"Expected pages 39+40, got {sell['pages']}"

    plot = next((e for e in house_home if "plot" in e["title"].lower()), None)
    assert plot is not None, "Expected 'plot thickens' story in house-home"
    assert plot["kind"] == "story"
    assert 40 in plot["pages"] and 41 in plot["pages"], f"Expected pages 40+41, got {plot['pages']}"

    # They are distinct stories
    assert sell["id"] != plot["id"]


# ---------------------------------------------------------------------------
# Teaser page (p19 Life & Arts section front)

def test_p19_teasers_are_classified(v99e_entries):
    """Entries on p19 with short text and ContOnPage should be teasers, not stories."""
    p19 = [e for e in v99e_entries if e["page"] == 19]
    # p19 contains both teasers and the real story start for some articles
    # At least some should be classified as teasers
    teasers = [e for e in p19 if e["kind"] == "teaser"]
    stories = [e for e in p19 if e["kind"] == "story"]
    # The cover teasers must not all be classified as stories
    assert len(teasers) >= 2, f"Expected >=2 teasers on p19, got {len(teasers)}. p19 entries: {[(e['title'], e['kind']) for e in p19]}"


def test_teasers_not_pending_for_match(v99e_entries):
    """Teasers should be pending (we keep them) but the match command will skip them."""
    teasers = [e for e in v99e_entries if e["kind"] == "teaser"]
    assert all(e["match_status"] == "pending" for e in teasers)


# ---------------------------------------------------------------------------
# Section normalization

def test_life_section_aliased(v99e_entries):
    """'Life' (continuation page name) should be aliased to 'Life & Arts'."""
    # All entries should use the canonical name, not the raw 'Life'
    assert not any(e["section"] == "Life" for e in v99e_entries), (
        "Found entries with raw section 'Life' — should be aliased to 'Life & Arts'"
    )


def test_section_theme_split(v99e_entries):
    """'Magazine | America At 250' → section='Magazine', theme='America At 250'.
    'Food & Drink | America At 250' → section='Food & Drink', theme='America At 250'.
    Both use the same theme; the section differs.
    """
    themed = [e for e in v99e_entries if e["theme"] == "America At 250"]
    assert len(themed) > 0, "Expected themed entries"
    # Themes come from at least two sections
    sections = {e["section"] for e in themed}
    assert "Magazine" in sections
    assert "Food & Drink" in sections
    # No entry should have the raw unsplit name as section
    assert not any("|" in (e["section"] or "") for e in v99e_entries)


def test_buckets_are_valid(v99e_entries):
    valid = {"main", "life-arts", "house-home", "magazine", "books-arts-travel-style-food",
             "htsi", "data", "other"}
    bad = [e for e in v99e_entries if e["bucket"] not in valid]
    assert bad == [], f"Invalid buckets: {[(e['title'], e['bucket']) for e in bad]}"


# ---------------------------------------------------------------------------
# No duplicate IDs

def test_no_duplicate_root_ids(v99e_entries):
    ids = [e["id"] for e in v99e_entries]
    assert len(ids) == len(set(ids)), "Duplicate root IDs found"


# ---------------------------------------------------------------------------
# HTSI fixture processes without error

def test_htsi_normalizes(htsi_entries):
    assert len(htsi_entries) > 0
    assert all("kind" in e for e in htsi_entries)
    stories = [e for e in htsi_entries if e["kind"] == "story"]
    assert len(stories) > 0


def test_htsi_bucket(htsi_entries):
    # HTSI stories should not be assigned main/life-arts by default
    # (they come from a different publication, bucket assignment comes from section)
    # Just verify no crash and all have valid buckets
    valid = {"main", "life-arts", "house-home", "magazine", "books-arts-travel-style-food",
             "htsi", "data", "other"}
    assert all(e["bucket"] in valid for e in htsi_entries)


# ---------------------------------------------------------------------------
# Match status initialized

def test_all_entries_have_match_status(v99e_entries):
    assert all("match_status" in e for e in v99e_entries)
    assert all(e["ft_url"] is None for e in v99e_entries)
    assert all(e["ft_uuid"] is None for e in v99e_entries)
