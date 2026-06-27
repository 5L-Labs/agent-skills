from __future__ import annotations
import time

from news_reader_base import Cache


def test_json_roundtrip_and_miss(tmp_path):
    c = Cache(tmp_path)
    assert c.get_json("GET", "https://x/y", ttl=60) is None
    c.set_json("GET", "https://x/y", {"a": 1})
    assert c.get_json("GET", "https://x/y", ttl=60) == {"a": 1}


def test_json_ttl_expiry(tmp_path):
    c = Cache(tmp_path)
    c.set_json("GET", "https://x/y", {"a": 1})
    time.sleep(0.02)
    assert c.get_json("GET", "https://x/y", ttl=0) is None


def test_bytes_roundtrip(tmp_path):
    c = Cache(tmp_path)
    p = c.set_bytes("GET", "https://x/mp3", b"\x00\x01\x02")
    assert p.exists()
    assert c.get_bytes_path("GET", "https://x/mp3", ttl=60) == p


def test_for_skill_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_CACHE_DIR", str(tmp_path / "custom"))
    c = Cache.for_skill(tmp_path / "skill", env_var="TEST_CACHE_DIR")
    assert c.base == tmp_path / "custom"


def test_for_skill_default(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_CACHE_DIR", raising=False)
    c = Cache.for_skill(tmp_path / "skill", env_var="TEST_CACHE_DIR")
    assert c.base == tmp_path / "skill" / "cache"
