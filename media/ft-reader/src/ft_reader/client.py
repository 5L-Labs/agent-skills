"""FT-specific HTTP client. Builds on news_reader_base.BaseClient."""
from __future__ import annotations
import os
from pathlib import Path

from news_reader_base import BaseClient, load_dotenv
from news_reader_base.errors import (
    NotFoundError as _NotFound,
    SessionExpiredError as _SessionExpired,
    UpstreamError as _Upstream,
)


class FTError(Exception):
    exit_code = 1
    code = "ERROR"


class SessionExpiredError(FTError, _SessionExpired):
    exit_code = 2
    code = "SESSION_EXPIRED"


class NotFoundError(FTError, _NotFound):
    exit_code = 3
    code = "NOT_FOUND"


class UpstreamError(FTError, _Upstream):
    exit_code = 4
    code = "NETWORK"


class FTClient(BaseClient):
    """Single-threaded, polite HTTP client for FT.com."""

    SOURCE = "FT"

    APP_API = "https://app-api.ft.com"
    AUDIO_CHECK = "https://audio-available.ft.com"

    NAMED_COOKIES = (
        ("FT_SESSION_S", "FTSession_s"),
        ("FT_CLIENT_SESSION_ID", "FTClientSessionId"),
        ("FT_APP_USER", "AppUser"),
        ("FT_CSRF", "_csrf"),
    )

    def __init__(self, *, env_loaded: bool = False):
        if not env_loaded:
            load_dotenv(Path(__file__).resolve().parent.parent.parent)
        super().__init__(
            session_expired_cls=SessionExpiredError,
            not_found_cls=NotFoundError,
            upstream_cls=UpstreamError,
        )
        self.cookie_header = self._build_cookie_header()

    def _build_cookie_header(self) -> str:
        """Prefer FT_COOKIE (full browser Cookie header). Fall back to 4 named cookies.

        The 4-named fallback works for `/structure/v14` and article endpoints
        but not MyFT, which requires additional coupled cookies that resist
        isolation.
        """
        blob = os.environ.get("FT_COOKIE")
        if blob:
            return blob.strip()
        missing = [name for name, _ in self.NAMED_COOKIES if not os.environ.get(name)]
        if missing:
            raise SessionExpiredError(
                "No FT credentials in env. Set FT_COOKIE to the full Cookie header "
                "value from a browser DevTools Network request to app-api.ft.com "
                f"(recommended), or set the four legacy vars: "
                f"{', '.join(n for n, _ in self.NAMED_COOKIES)}. "
                f"Missing: {', '.join(missing)}."
            )
        return "; ".join(f"{c}={os.environ[e]}" for e, c in self.NAMED_COOKIES)

    def _headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://app.ft.com/",
            "Origin": "https://app.ft.com",
            "Cookie": self.cookie_header,
        }
