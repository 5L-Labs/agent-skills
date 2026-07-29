"""Tests for match.py — scoring, generic titles, exit-code-2 abort, dry-run."""
from __future__ import annotations

import json
import os
import stat
import textwrap
from datetime import date
from pathlib import Path

import pytest

from pressreader_toc.match import (
    DEFAULT_BUCKETS,
    _is_generic_title,
    _norm_title,
    _score,
    _byline_surnames,
    match_stories,
)


# ---------------------------------------------------------------------------
# Unit: title scoring

@pytest.mark.parametrize("print_title,web_title,min_score", [
    # Clear matches
    ("Quit quitting", "How to win at quitting", 0.4),
    ("Days of deliverance", "Days of deliverance", 0.99),
    ("Anthropic to close China loopholes", "Anthropic to close China loopholes", 0.99),
    # Web title extends print title
    ("How to sell a home in a slow market", "Selling in a slow market: a guide", 0.3),
])
def test_score_reasonable(print_title, web_title, min_score):
    assert _score(print_title, web_title) >= min_score


def test_score_unrelated():
    assert _score("Blooming good", "Anthropic closes China loopholes") < 0.3


def test_norm_title_strips_htsi_prefix():
    assert "htsi" not in _norm_title("HTSI: Fashion special")
    assert "fashion" in _norm_title("HTSI: Fashion special")


# ---------------------------------------------------------------------------
# Unit: generic title detection

@pytest.mark.parametrize("title,expected", [
    ("Abraham Lincoln", True),     # 2 tokens, both stopword-free but < 3
    ("Prince", True),              # 1 token
    ("Anthropic to close China loopholes", False),
    ("How to win at quitting", False),
])
def test_generic_title_detection(title, expected):
    assert _is_generic_title(title) == expected


# ---------------------------------------------------------------------------
# Unit: byline cleaning

def test_byline_surnames_email():
    surnames = _byline_surnames("jo.ellison@ft.com")
    assert not any("@" in s for s in surnames)


def test_byline_surnames_bio():
    surnames = _byline_surnames(
        "by Jamie Dimon Jamie Dimon is the chairman and CEO of JPMorganChase"
    )
    assert "dimon" in surnames


def test_byline_surnames_location():
    surnames = _byline_surnames("ELEANOR OLCOTT — BEIJING")
    assert "olcott" in surnames
    assert "beijing" not in surnames


# ---------------------------------------------------------------------------
# Integration: dry-run

def _make_entry(title, bucket="life-arts", byline="", kind="story"):
    return {
        "kind": kind,
        "id": hash(title),
        "toc_ids": [hash(title)],
        "uid": "x",
        "title": title,
        "byline": byline,
        "text": "some text",
        "page": 1,
        "pages": [1],
        "section": "Life & Arts",
        "theme": None,
        "bucket": bucket,
        "teaser_for": None,
        "match_status": "pending",
        "ft_url": None,
        "ft_uuid": None,
        "match_score": None,
    }


def test_dry_run_does_not_call_ft(capsys):
    entries = [_make_entry("Days of deliverance")]
    updated, report = match_stories(
        entries, date(2026, 7, 4), dry_run=True
    )
    assert report["dry_run"] is True
    assert report["would_search"] == 1
    # Entry should still be pending — no ft search happened
    assert updated[0]["match_status"] == "pending"


def test_dry_run_excludes_non_story():
    teaser = _make_entry("Quit quitting", kind="teaser")
    story = _make_entry("Days of deliverance", kind="story")
    _, report = match_stories(
        [teaser, story], date(2026, 7, 4), dry_run=True
    )
    assert report["would_search"] == 1  # only the story


def test_dry_run_respects_bucket_filter():
    main_story = _make_entry("Anthropic China", bucket="main")
    la_story = _make_entry("Days of deliverance", bucket="life-arts")
    _, report = match_stories(
        [main_story, la_story], date(2026, 7, 4),
        buckets=frozenset({"life-arts"}), dry_run=True
    )
    assert report["would_search"] == 1


# ---------------------------------------------------------------------------
# Integration: exit-code-2 abort (fake ft binary)

def _write_fake_ft(tmp_path: Path, exit_code: int, stdout: str = "{}") -> str:
    script = tmp_path / "ft"
    script.write_text(
        f"#!/bin/sh\necho '{stdout}'\nexit {exit_code}\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_exit_code_2_aborts_immediately(tmp_path):
    ft = _write_fake_ft(tmp_path, 2, '{"error":{"code":"SESSION_EXPIRED","message":"expired"}}')
    entries = [
        _make_entry("Story One"),
        _make_entry("Story Two"),
    ]
    updated, report = match_stories(
        entries, date(2026, 7, 4), ft_binary=ft
    )
    assert report["aborted"] is True
    assert "SESSION_EXPIRED" in (report["abort_reason"] or "")
    # At most 1 entry was attempted before abort
    searched_count = sum(1 for e in updated if e["match_status"] != "pending")
    assert searched_count <= 1


def test_successful_match(tmp_path):
    result_payload = json.dumps({
        "schema_version": 1,
        "results": [
            {"uuid": "abc123", "url": "https://www.ft.com/content/abc123",
             "title": "Days of deliverance", "published": "2026-07-04T00:00:00Z",
             "author": "Simon Schama"}
        ]
    })
    ft = _write_fake_ft(tmp_path, 0, result_payload.replace("'", '"').replace('"', '\\"'))
    # Use a simpler approach — write a Python script instead
    script = tmp_path / "ft"
    script.write_text(
        f'#!/usr/bin/env python3\nimport sys\nprint({result_payload!r})\nsys.exit(0)\n'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    entries = [_make_entry("Days of deliverance")]
    updated, report = match_stories(
        entries, date(2026, 7, 4), ft_binary=str(script)
    )
    assert report["matched"] == 1
    assert updated[0]["match_status"] == "matched"
    assert updated[0]["ft_url"] == "https://www.ft.com/content/abc123"


def test_resumable_skips_already_matched(tmp_path):
    """An already-matched entry should not be re-searched (no retry_unmatched)."""
    result_payload = json.dumps({
        "schema_version": 1,
        "results": [{"uuid": "x", "url": "https://ft.com/content/x",
                     "title": "Test", "published": None, "author": None}]
    })
    script = tmp_path / "ft"
    call_count_file = tmp_path / "calls.txt"
    script.write_text(
        f'#!/usr/bin/env python3\nimport sys\n'
        f'open({str(call_count_file)!r}, "a").write("1\\n")\n'
        f'print({result_payload!r})\nsys.exit(0)\n'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    entries = [
        {**_make_entry("Already matched"), "match_status": "matched",
         "ft_url": "https://ft.com/content/already"},
        _make_entry("New story"),
    ]
    match_stories(entries, date(2026, 7, 4), ft_binary=str(script))
    calls = call_count_file.read_text().strip().splitlines() if call_count_file.exists() else []
    assert len(calls) == 1  # only "New story" was searched
