"""Tests for toc.py — date parsing, issue key, caching, not-found handling."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pressreader_toc.toc import fetch_toc, resolve_date, _issue_key
from pressreader_toc.errors import NotFoundError

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Date parsing

def test_resolve_today():
    d = resolve_date("today")
    assert d == date.today()


def test_resolve_iso():
    assert resolve_date("2026-07-04") == date(2026, 7, 4)


def test_resolve_invalid():
    with pytest.raises(ValueError):
        resolve_date("not-a-date")


def test_resolve_weekend_saturday():
    # If "today" is a Saturday this returns today; we can't control that,
    # but we can verify it returns a Saturday.
    d = resolve_date("weekend")
    assert d.weekday() == 5  # Saturday


# ---------------------------------------------------------------------------
# Issue key construction

def test_issue_key_format():
    key = _issue_key("v99e", date(2026, 7, 4))
    assert key == "v99e2026070400000000001001"

    key2 = _issue_key("9lh5", date(2026, 7, 4))
    assert key2 == "9lh52026070400000000001001"


# ---------------------------------------------------------------------------
# fetch_toc with a mocked client (no network)

def _make_client(fixture_name: str):
    """Return a mock PRClient that returns the fixture TOC."""
    raw = json.loads((FIXTURES / fixture_name).read_text())
    client = MagicMock()
    client.fetch_toc.return_value = raw
    return client


def test_fetch_toc_ft_only(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESSREADER_DATA_DIR", str(tmp_path))
    client = _make_client("toc_v99e_2026-07-04.json")
    result = fetch_toc("2026-07-04", pub="ft", client=client)
    assert result["date"] == "2026-07-04"
    assert len(result["issues"]) == 1
    assert result["issues"][0]["cid"] == "v99e"
    assert result["total_stories"] > 0


def test_fetch_toc_all_saturday_fetches_htsi(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESSREADER_DATA_DIR", str(tmp_path))
    # 2026-07-04 is a Saturday; --pub all should fetch both v99e and 9lh5
    v99e_raw = json.loads((FIXTURES / "toc_v99e_2026-07-04.json").read_text())
    htsi_raw = json.loads((FIXTURES / "toc_9lh5_2026-07-04.json").read_text())
    client = MagicMock()
    client.fetch_toc.side_effect = lambda key: (
        htsi_raw if key.startswith("9lh5") else v99e_raw
    )
    result = fetch_toc("2026-07-04", pub="all", client=client)
    cids = {iss["cid"] for iss in result["issues"]}
    assert "v99e" in cids
    assert "9lh5" in cids


def test_fetch_toc_weekday_skips_htsi(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESSREADER_DATA_DIR", str(tmp_path))
    # 2026-07-03 is a Friday
    raw = json.loads((FIXTURES / "toc_v99e_2026-07-04.json").read_text())
    client = MagicMock()
    client.fetch_toc.return_value = raw
    result = fetch_toc("2026-07-03", pub="all", client=client)
    assert all(iss["cid"] == "v99e" for iss in result["issues"])


def test_fetch_toc_cache_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESSREADER_DATA_DIR", str(tmp_path))
    client = _make_client("toc_v99e_2026-07-04.json")
    # First call populates cache
    fetch_toc("2026-07-04", pub="ft", client=client)
    assert client.fetch_toc.call_count == 1
    # Second call should hit cache, not call client again
    fetch_toc("2026-07-04", pub="ft", client=client)
    assert client.fetch_toc.call_count == 1


def test_fetch_toc_refresh_bypasses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESSREADER_DATA_DIR", str(tmp_path))
    client = _make_client("toc_v99e_2026-07-04.json")
    fetch_toc("2026-07-04", pub="ft", client=client)
    fetch_toc("2026-07-04", pub="ft", client=client, refresh=True)
    assert client.fetch_toc.call_count == 2


def test_fetch_toc_htsi_not_found_warns_but_continues(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESSREADER_DATA_DIR", str(tmp_path))
    v99e_raw = json.loads((FIXTURES / "toc_v99e_2026-07-04.json").read_text())
    client = MagicMock()
    def side_effect(key):
        if key.startswith("9lh5"):
            raise NotFoundError("not found")
        return v99e_raw
    client.fetch_toc.side_effect = side_effect

    result = fetch_toc("2026-07-04", pub="all", client=client)
    # Should not raise — HTSI miss is a warning
    htsi_issue = next((iss for iss in result["issues"] if iss["cid"] == "9lh5"), None)
    assert htsi_issue is not None
    assert htsi_issue.get("not_found") is True
    assert htsi_issue["entries"] == []


def test_fetch_toc_htsi_explicit_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESSREADER_DATA_DIR", str(tmp_path))
    client = MagicMock()
    client.fetch_toc.side_effect = NotFoundError("not found")
    with pytest.raises(NotFoundError):
        fetch_toc("2026-07-04", pub="htsi", client=client)
