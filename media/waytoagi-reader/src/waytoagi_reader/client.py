"""Tiny HTTP client. Stdlib only — caching is layered on top in `cache.py`."""
from __future__ import annotations

import http.cookiejar
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_BACKOFF_BASE_SEC = 0.5


def _is_retryable(exc: Exception) -> bool:
    """5xx and connection-class errors are retryable; 4xx and parse errors aren't."""
    if isinstance(exc, urllib.error.HTTPError):
        return 500 <= exc.code < 600
    return isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError))


def fetch_html(
    url: str,
    *,
    user_agent: str | None = None,
    timeout: float = 20.0,
    max_retries: int | None = None,
) -> str:
    """Fetch a guest-mode Feishu wiki page and return decoded HTML.

    Retries up to `WAYTOAGI_MAX_RETRIES` (default 2) with exponential backoff on
    5xx / connection-class errors. A transient Feishu glitch shouldn't wedge the
    5-minute cache TTL on the user's next invocation."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL scheme: {url}")

    ua = user_agent or os.environ.get("WAYTOAGI_USER_AGENT") or DEFAULT_UA
    retries = max_retries if max_retries is not None else int(os.environ.get("WAYTOAGI_MAX_RETRIES", "2"))
    for attempt in range(retries + 1):
        try:
            jar = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            opener.addheaders = [("User-Agent", ua), ("Accept-Language", "zh-CN,en;q=0.9")]
            with opener.open(url, timeout=timeout) as resp:  # nosec B310
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            if attempt >= retries or not _is_retryable(exc):
                raise
            sleep_for = _BACKOFF_BASE_SEC * (2 ** attempt)
            print(
                f"[warn] fetch failed ({type(exc).__name__}: {exc}); "
                f"retrying in {sleep_for:.1f}s (attempt {attempt + 2}/{retries + 1})",
                file=sys.stderr,
            )
            time.sleep(sleep_for)
    raise RuntimeError("unreachable")  # pragma: no cover
