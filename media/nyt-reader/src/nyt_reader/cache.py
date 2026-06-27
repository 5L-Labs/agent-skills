"""NYT cache: re-exports base Cache plus NYT-specific TTLs."""
from __future__ import annotations
from pathlib import Path

from news_reader_base import Cache as _Cache


class Cache(_Cache):
    def __init__(self, base=None):
        if base is None:
            skill_dir = Path(__file__).resolve().parent.parent.parent
            super().__init__(_Cache.for_skill(skill_dir, "NYT_CACHE_DIR").base)
        else:
            super().__init__(base)


# TTLs in seconds
TTL_ARTICLE = 30 * 24 * 3600
TTL_AUDIO = 30 * 24 * 3600
TTL_HEADLINES = 60 * 60
TTL_SAVED = 60 * 60
