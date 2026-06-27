"""Tiered TTL file cache. Key = sha256(method + url). Stores JSON or bytes."""
from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional


class Cache:
    def __init__(self, base: Path):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_skill(cls, skill_dir: Path, env_var: str) -> "Cache":
        """Resolve cache dir from `env_var` or fall back to `<skill_dir>/cache`."""
        override = os.environ.get(env_var)
        return cls(Path(override) if override else skill_dir / "cache")

    def _key(self, method: str, url: str) -> str:
        return hashlib.sha256(f"{method.upper()} {url}".encode()).hexdigest()

    def _paths(self, key: str, binary: bool) -> tuple[Path, Path]:
        ext = "bin" if binary else "json"
        return self.base / f"{key}.{ext}", self.base / f"{key}.meta.json"

    def get_json(self, method: str, url: str, ttl: int) -> Optional[Any]:
        key = self._key(method, url)
        data_p, meta_p = self._paths(key, binary=False)
        if not (data_p.exists() and meta_p.exists()):
            return None
        meta = json.loads(meta_p.read_text())
        if time.time() - meta["fetched_at"] >= ttl:
            return None
        return json.loads(data_p.read_text())

    def set_json(self, method: str, url: str, value: Any) -> None:
        key = self._key(method, url)
        data_p, meta_p = self._paths(key, binary=False)
        data_p.write_text(json.dumps(value))
        meta_p.write_text(json.dumps({"fetched_at": time.time(), "url": url}))

    def get_bytes_path(self, method: str, url: str, ttl: int) -> Optional[Path]:
        key = self._key(method, url)
        data_p, meta_p = self._paths(key, binary=True)
        if not (data_p.exists() and meta_p.exists()):
            return None
        meta = json.loads(meta_p.read_text())
        if time.time() - meta["fetched_at"] >= ttl:
            return None
        return data_p

    def set_bytes(self, method: str, url: str, value: bytes) -> Path:
        key = self._key(method, url)
        data_p, meta_p = self._paths(key, binary=True)
        data_p.write_bytes(value)
        meta_p.write_text(json.dumps({"fetched_at": time.time(), "url": url}))
        return data_p
