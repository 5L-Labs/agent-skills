"""Cache tier behavior: hit/miss/refresh/no-cache, atomic write, corrupt-meta recovery."""
from __future__ import annotations

import json
import time
from pathlib import Path

from waytoagi_reader.cache import cached_fetch


def _fetcher_factory():
    calls = {"n": 0}

    def f(url):
        calls["n"] += 1
        return f"<html>body-{calls['n']}</html>"

    return f, calls


def test_miss_then_hit(tmp_path: Path):
    fetcher, calls = _fetcher_factory()
    r1 = cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60)
    assert r1.hit is False and r1.body == "<html>body-1</html>"
    r2 = cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60)
    assert r2.hit is True and r2.body == "<html>body-1</html>"
    assert calls["n"] == 1


def test_ttl_expiry_triggers_refetch(tmp_path: Path):
    fetcher, calls = _fetcher_factory()
    cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=0)
    cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=0)
    assert calls["n"] == 2


def test_no_cache_bypasses_both_read_and_write(tmp_path: Path):
    fetcher, calls = _fetcher_factory()
    cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60, mode="no")
    cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60, mode="no")
    assert calls["n"] == 2
    assert not list((tmp_path / "raw").rglob("*.html.gz"))


def test_refresh_rewrites_entry(tmp_path: Path):
    fetcher, calls = _fetcher_factory()
    cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60)
    r = cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60, mode="refresh")
    assert r.hit is False and r.body == "<html>body-2</html>"
    assert calls["n"] == 2
    r2 = cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60)
    assert r2.hit is True and r2.body == "<html>body-2</html>"


def test_corrupt_meta_falls_through_to_refetch(tmp_path: Path):
    fetcher, calls = _fetcher_factory()
    cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60)
    meta_files = list((tmp_path / "raw").rglob("*.meta.json"))
    assert meta_files
    meta_files[0].write_text("not json")
    r = cached_fetch("https://example/", fetcher=fetcher, cache_dir=tmp_path, ttl=60)
    assert r.hit is False
    assert calls["n"] == 2
