"""Raw-tier file cache. TTL-only (Feishu sends `Cache-Control: no-store`, no ETag).

v0.1 ships the raw HTML tier only; parsed-blocks and rendered tiers are deliberately
deferred — both are a JSON parse away from the cached HTML."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_RAW_TTL = 300  # seconds


def _default_cache_dir() -> Path:
    base = os.environ.get("WAYTOAGI_CACHE_DIR")
    if base:
        return Path(base)
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "waytoagi-reader"
    return Path.home() / ".cache" / "waytoagi-reader"


def _key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _paths(cache_dir: Path, key: str) -> tuple[Path, Path]:
    shard = cache_dir / "raw" / key[:2]
    return shard / f"{key}.html.gz", shard / f"{key}.meta.json"


@dataclass
class CacheResult:
    body: str
    hit: bool
    fetched_at: float
    age_seconds: float


CacheMode = Literal["read+write", "no", "refresh"]


def cached_fetch(
    url: str,
    *,
    fetcher,
    ttl: int | None = None,
    mode: CacheMode = "read+write",
    cache_dir: Path | None = None,
) -> CacheResult:
    """Fetch `url` using `fetcher(url) -> str`, applying TTL caching.

    Modes:
      read+write — normal: serve from cache if fresh, else fetch and store.
      no         — bypass cache entirely.
      refresh    — bypass read; always fetch and overwrite the stored entry.
    """
    if mode == "no":
        body = fetcher(url)
        return CacheResult(body=body, hit=False, fetched_at=time.time(), age_seconds=0.0)

    ttl = ttl if ttl is not None else int(os.environ.get("WAYTOAGI_CACHE_RAW_TTL", DEFAULT_RAW_TTL))
    root = cache_dir or _default_cache_dir()
    key = _key(url)
    body_path, meta_path = _paths(root, key)

    if mode == "read+write" and body_path.exists() and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            age = time.time() - meta["fetched_at"]
            if age <= ttl:
                with gzip.open(body_path, "rt", encoding="utf-8") as f:
                    body = f.read()
                return CacheResult(body=body, hit=True, fetched_at=meta["fetched_at"], age_seconds=age)
        except (OSError, ValueError, KeyError):
            pass  # corrupt entry — fall through to refetch

    body = fetcher(url)
    body_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_body = body_path.with_suffix(body_path.suffix + ".tmp")
    with gzip.open(tmp_body, "wt", encoding="utf-8") as f:
        f.write(body)
    tmp_body.replace(body_path)
    meta = {"url": url, "fetched_at": time.time(), "bytes": len(body)}
    meta_path.write_text(json.dumps(meta))
    return CacheResult(body=body, hit=False, fetched_at=meta["fetched_at"], age_seconds=0.0)
