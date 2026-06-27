"""NYT HTTP client. Cookie session + the 3 static project-vi headers."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from news_reader_base import BaseClient, load_dotenv
from news_reader_base.errors import (
    NotFoundError as _NotFound,
    SessionExpiredError as _SessionExpired,
    UpstreamError as _Upstream,
)

# Static client identifier extracted from the NYT web bundle (samizdat-graphql
# "project-vi"). NYT validates this token on every GraphQL request but the
# value itself is public and constant across browser sessions. Override via
# NYT_TOKEN if NYT rotates it.
DEFAULT_NYT_TOKEN = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAs+/oUCTBmD/cLdmcecrnBMHiU/p"
    "xQCn2DDyaPKUOXxi4p0uUSZQzsuq1pJ1m5z1i0YGPd1U1OeGHAChWtqoxC7bFMCXcwnE1oy"
    "ui9G1uobgpm1GdhtwkR7ta7akVTcsF8zxiXx7DNXIPd2nIJFH83rmkZueKrC4JVaNzjvD+Z"
    "03piLn5bHWU6+w+rA+kyJtGgZNTXKyPh6EC6o5N+rknNMG5+CdTq35p8f99WjFawSvYgP9V"
    "64kgckbTbtdJ6YhVP58TnuYgr12urtwnIqWP9KSJ1e5vmgf3tunMqWNm6+AnsqNj8mCLdCu"
    "c5cEB74CwUeQcP2HQQmbCddBy2y0mEwIDAQAB"
)


class NYTError(Exception):
    exit_code = 1
    code = "ERROR"


class SessionExpiredError(NYTError, _SessionExpired):
    exit_code = 2
    code = "SESSION_EXPIRED"


class NotFoundError(NYTError, _NotFound):
    exit_code = 3
    code = "NOT_FOUND"


class UpstreamError(NYTError, _Upstream):
    exit_code = 4
    code = "NETWORK"


class NYTClient(BaseClient):
    """Single-threaded, polite HTTP client for NYT."""

    SOURCE = "NYT"

    GRAPHQL = "https://samizdat-graphql.nytimes.com/graphql/v2"
    BASE = "https://www.nytimes.com"

    NAMED_COOKIES = (
        ("NYT_A", "nyt-a"),
        ("NYT_S", "NYT-S"),
        ("NYT_JKIDD", "nyt-jkidd"),
        ("NYT_PURR", "nyt-purr"),
        ("NYT_B_SID", "nyt-b-sid"),
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
        self.nyt_token = os.environ.get("NYT_TOKEN") or DEFAULT_NYT_TOKEN

    def _build_cookie_header(self) -> str:
        missing = [
            env_name for env_name, _ in self.NAMED_COOKIES
            if not os.environ.get(env_name)
        ]
        if missing:
            raise SessionExpiredError(
                "No NYT credentials in env. Set the five named cookies: "
                f"{', '.join(n for n, _ in self.NAMED_COOKIES)}. "
                f"Missing: {', '.join(missing)}."
            )
        return "; ".join(
            f"{cookie}={os.environ[env_name]}"
            for env_name, cookie in self.NAMED_COOKIES
        )

    def _graphql_headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{self.BASE}/",
            "Origin": self.BASE,
            "content-type": "application/json",
            "nyt-app-type": "project-vi",
            "nyt-app-version": "0.0.5",
            "nyt-token": self.nyt_token,
            "Cookie": self.cookie_header,
        }

    def _html_headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{self.BASE}/",
            "Cookie": self.cookie_header,
        }

    # Default headers for arbitrary get_json calls.
    def _headers(self) -> dict:
        return self._graphql_headers()

    def graphql(
        self,
        operation_name: str,
        *,
        sha256_hash: str,
        variables: Optional[dict] = None,
        space: bool = True,
    ) -> Any:
        params = {
            "operationName": operation_name,
            "variables": json.dumps(variables or {}, separators=(",", ":")),
            "extensions": json.dumps(
                {"persistedQuery": {"version": 1, "sha256Hash": sha256_hash}},
                separators=(",", ":"),
            ),
        }
        url = f"{self.GRAPHQL}?{urlencode(params)}"
        return self.get_json(url, headers=self._graphql_headers(), space=space)

    def get_html(self, url: str, *, space: bool = True) -> str:
        self._check_budget()
        if space:
            self._space()
        try:
            r = self.session.get(url, headers=self._html_headers(), timeout=30)
        except requests.RequestException as e:
            raise UpstreamError(f"network error for {url}: {e}") from e
        self._fetch_count += 1
        self._last_origin_fetch_at = time.time()
        self._raise_for_status(r, url)
        return r.text
