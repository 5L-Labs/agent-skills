"""End-to-end CLI test using the noop backend — no network, no LLM."""
from __future__ import annotations

import io
import json
import os
import sys

import pytest

from translate.cli import main


def _run(input_doc, args, monkeypatch, tmp_path):
    monkeypatch.setenv("TRANSLATE_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(input_doc)))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    code = main(args)
    return code, json.loads(buf.getvalue())


def test_noop_adds_lang_siblings(monkeypatch, tmp_path):
    doc = {"title": "Hello", "days": [{"heading": "H", "items": [{"title": "X", "summary": "S"}]}]}
    code, out = _run(doc, ["--target", "en", "--backend", "noop"], monkeypatch, tmp_path)
    assert code == 0
    assert out["title_en"] == "[en] Hello"
    assert out["days"][0]["heading_en"] == "[en] H"
    assert out["days"][0]["items"][0]["title_en"] == "[en] X"
    assert out["days"][0]["items"][0]["summary_en"] == "[en] S"


def test_noop_inplace_replaces(monkeypatch, tmp_path):
    doc = {"title": "Hello"}
    code, out = _run(doc, ["--target", "en", "--backend", "noop", "--inplace"], monkeypatch, tmp_path)
    assert code == 0
    assert out["title"] == "[en] Hello"
    assert "title_en" not in out


def test_idempotent_skip_already_translated(monkeypatch, tmp_path):
    doc = {"title": "Hello", "title_en": "preserved"}
    code, out = _run(doc, ["--target", "en", "--backend", "noop"], monkeypatch, tmp_path)
    assert code == 0
    assert out["title_en"] == "preserved"


def test_cache_round_trip(monkeypatch, tmp_path):
    doc = {"title": "Hello"}
    _run(doc, ["--target", "en", "--backend", "noop"], monkeypatch, tmp_path)
    cache_files = list(tmp_path.rglob("*.json"))
    assert cache_files, "cache should have written an entry"


def test_cache_write_failure_does_not_abort_run(monkeypatch, tmp_path):
    """A disk error inside cache.put() must never break translation output."""
    from translate import cache as cache_mod

    def broken_put(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(cache_mod, "put", broken_put)
    doc = {"title": "Hello", "summary": "World"}
    code, out = _run(doc, ["--target", "en", "--backend", "noop"], monkeypatch, tmp_path)
    assert code == 0
    assert out["title_en"] == "[en] Hello"
    assert out["summary_en"] == "[en] World"


def test_cache_read_failure_does_not_abort_run(monkeypatch, tmp_path):
    from translate import cache as cache_mod

    def broken_get(*_args, **_kwargs):
        raise OSError("read error")

    monkeypatch.setattr(cache_mod, "get", broken_get)
    doc = {"title": "Hello"}
    code, out = _run(doc, ["--target", "en", "--backend", "noop"], monkeypatch, tmp_path)
    assert code == 0
    assert out["title_en"] == "[en] Hello"


def test_backend_failure_emits_error_sibling(monkeypatch, tmp_path):
    """Reviewer flagged that the _error sibling contract was untested.
    Per-item backend failures must not abort the whole run."""
    from translate.backends import noop as noop_mod

    class FlakyBackend(noop_mod.NoopBackend):
        def translate(self, text, *, source, target):
            raise RuntimeError("backend down")

    def factory(*_args, **_kwargs):
        return FlakyBackend()

    monkeypatch.setattr("translate.cli.get_backend", factory)
    doc = {"title": "Hello", "summary": "World"}
    code, out = _run(doc, ["--target", "en", "--backend", "noop"], monkeypatch, tmp_path)
    assert code == 4  # EXIT_BACKEND
    assert out["title_en"] is None
    assert out["title_en_error"].startswith("RuntimeError:")
    assert out["summary_en"] is None


def test_cache_signature_isolates_models(tmp_path):
    """Swapping models (different cache_signature) must not silently reuse stale output."""
    from translate import cache as cache_mod
    cache_mod.put(tmp_path, "Hello", "auto", "en", "ollama:7b:abc", "TR_SMALL")
    cache_mod.put(tmp_path, "Hello", "auto", "en", "ollama:32b:def", "TR_BIG")
    assert cache_mod.get(tmp_path, "Hello", "auto", "en", "ollama:7b:abc") == "TR_SMALL"
    assert cache_mod.get(tmp_path, "Hello", "auto", "en", "ollama:32b:def") == "TR_BIG"
