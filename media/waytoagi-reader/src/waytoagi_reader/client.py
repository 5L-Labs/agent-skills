"""Tiny HTTP client. Stdlib only — caching is layered on top in `cache.py`."""
from __future__ import annotations

import http.cookiejar
import urllib.request

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def fetch_html(url: str, *, user_agent: str = DEFAULT_UA, timeout: float = 20.0) -> str:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", user_agent), ("Accept-Language", "zh-CN,en;q=0.9")]
    with opener.open(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")
