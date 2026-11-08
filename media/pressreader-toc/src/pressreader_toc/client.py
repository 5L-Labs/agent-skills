"""Thin HTTP client for the public PressReader CDN TOC endpoint.

No authentication required — the TOC is served by a public CDN.
Uses urllib (stdlib-only; no requests dep needed for these unauthenticated calls).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from news_reader_base import load_dotenv

from .errors import NotFoundError, UpstreamError

TOC_BASE = "https://s.prcdn.co/services/toc/"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"


class PRClient:
    """HTTP client for the public PressReader CDN (no cookies needed for TOC)."""

    def __init__(self, *, env_loaded: bool = False):
        if not env_loaded:
            load_dotenv(Path(__file__).resolve().parent.parent.parent)

    def _get(self, url: str, timeout: int = 30) -> Any:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _UA, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "ignore")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFoundError(f"PressReader returned 404 for {url}")
            raise UpstreamError(f"PressReader returned {e.code} for {url}: {e.read()[:200]!r}")
        except urllib.error.URLError as e:
            raise UpstreamError(f"Network error fetching {url}: {e.reason}")
        except json.JSONDecodeError as e:
            raise UpstreamError(f"Non-JSON response from {url}: {e}")

    def fetch_toc(self, issue_key: str) -> dict:
        url = f"{TOC_BASE}?issue={urllib.parse.quote(issue_key)}"
        return self._get(url)
