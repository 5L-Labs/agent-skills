"""Tests for store.py — atomic writes, round-trip, schema versioning."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

from pressreader_toc.store import (
    SCHEMA_VERSION,
    load_normalized,
    load_raw,
    normalized_exists,
    save_normalized,
    save_raw,
    update_entries,
)


@pytest.fixture()
def tmp_store(monkeypatch, tmp_path):
    monkeypatch.setenv("PRESSREADER_DATA_DIR", str(tmp_path))
    return tmp_path


def _sample_entries():
    return [
        {"kind": "story", "id": 1, "toc_ids": [1], "uid": "a", "title": "Test",
         "byline": "", "text": "body", "page": 1, "pages": [1],
         "section": "Front Page", "theme": None, "bucket": "main",
         "teaser_for": None, "match_status": "pending",
         "ft_url": None, "ft_uuid": None, "match_score": None},
    ]


def test_save_and_load_raw(tmp_store):
    raw = {"Pages": [], "Meta": {}}
    d = date(2026, 7, 4)
    save_raw("v99e", d, raw)
    loaded = load_raw("v99e", d)
    assert loaded == raw


def test_save_and_load_normalized(tmp_store):
    entries = _sample_entries()
    d = date(2026, 7, 4)
    save_normalized("v99e", d, entries)
    doc = load_normalized("v99e", d)
    assert doc is not None
    assert doc["schema_version"] == SCHEMA_VERSION
    assert doc["cid"] == "v99e"
    assert doc["issue_date"] == "2026-07-04"
    assert len(doc["entries"]) == 1


def test_normalized_exists(tmp_store):
    d = date(2026, 7, 4)
    assert not normalized_exists("v99e", d)
    save_normalized("v99e", d, _sample_entries())
    assert normalized_exists("v99e", d)


def test_update_entries(tmp_store):
    d = date(2026, 7, 4)
    save_normalized("v99e", d, _sample_entries())
    entries = load_normalized("v99e", d)["entries"]
    entries[0]["match_status"] = "matched"
    entries[0]["ft_url"] = "https://ft.com/content/abc"
    update_entries("v99e", d, entries)
    doc = load_normalized("v99e", d)
    assert doc["entries"][0]["match_status"] == "matched"
    assert doc["entries"][0]["ft_url"] == "https://ft.com/content/abc"


def test_schema_version_mismatch_returns_none(tmp_store):
    d = date(2026, 7, 4)
    save_normalized("v99e", d, _sample_entries())
    # Corrupt the schema_version
    path = tmp_store / "v99e-2026-07-04.json"
    doc = json.loads(path.read_text())
    doc["schema_version"] = 99
    path.write_text(json.dumps(doc))
    assert load_normalized("v99e", d) is None
    assert not normalized_exists("v99e", d)


def test_atomic_write_creates_file(tmp_store):
    d = date(2026, 7, 4)
    save_normalized("v99e", d, _sample_entries())
    files = list(tmp_store.iterdir())
    # No .tmp. files left behind
    assert not any(".tmp." in f.name for f in files)
    assert any(f.name == "v99e-2026-07-04.json" for f in files)
