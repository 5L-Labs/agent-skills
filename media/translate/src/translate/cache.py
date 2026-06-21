"""Translation cache: keyed on (text, source, target, backend_signature).

Translations of a fixed input under a fixed (backend, model, system-prompt) are
stable — TTL is effectively indefinite. LRU eviction is left for a follow-up;
the cache is filesystem-bound, so a stale entry costs only disk.

The `signature` argument is whatever the backend returns from `cache_signature()`.
It captures backend name, model id, and a digest of the system prompt, so any
change there invalidates affected entries automatically (no manual version bumps)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def default_cache_dir() -> Path:
    base = os.environ.get("TRANSLATE_CACHE_DIR")
    if base:
        return Path(base)
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "translate"
    return Path.home() / ".cache" / "translate"


def _key(text: str, source: str, target: str, signature: str) -> str:
    h = hashlib.sha256()
    for part in (text, source, target, signature):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def get(cache_dir: Path, text: str, source: str, target: str, signature: str) -> str | None:
    key = _key(text, source, target, signature)
    path = cache_dir / key[:2] / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())["translation"]
    except (OSError, ValueError, KeyError):
        return None


def put(cache_dir: Path, text: str, source: str, target: str, signature: str, translation: str) -> None:
    key = _key(text, source, target, signature)
    path = cache_dir / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "source_text": text,
        "source_lang": source,
        "target_lang": target,
        "signature": signature,
        "translation": translation,
    }, ensure_ascii=False))
    tmp.replace(path)
