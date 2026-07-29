import sys

import pytest

from wsj_reader.client import UpstreamError
from wsj_reader.cookie_refresh import (
    _cookie_header_from_playwright,
    _ready_to_write,
    _update_env_cookie,
    refresh_cookie_with_browser,
)


def test_cookie_header_from_playwright_filters_to_wsj_domains():
    cookies = [
        {"name": "datadome", "value": "edge", "domain": ".wsj.com"},
        {"name": "ca_id", "value": "unlock", "domain": "www.wsj.com"},
        {"name": "other", "value": "ignored", "domain": "example.com"},
    ]

    assert _cookie_header_from_playwright(cookies) == "datadome=edge; ca_id=unlock"


def test_update_env_cookie_replaces_existing_value(tmp_path):
    env = tmp_path / ".env"
    env.write_text("WSJ_CACHE_DIR=/tmp/wsj\nWSJ_COOKIE=old=value\n")

    _update_env_cookie(env, "datadome=edge; ca_id=unlock")

    assert env.read_text() == "WSJ_CACHE_DIR=/tmp/wsj\nWSJ_COOKIE=datadome=edge; ca_id=unlock\n"
    assert oct(env.stat().st_mode & 0o777) == "0o600"


def test_ready_to_write_requires_edge_cookies_and_article_unlock():
    cookie = "datadome=edge; ca_id=unlock"

    assert _ready_to_write(cookie, {"article_page": False}) is True
    assert _ready_to_write(cookie, {
        "article_page": True,
        "ok": True,
        "snippet": False,
        "serverUnlocked": True,
        "paragraphs": 20,
    }) is True
    assert _ready_to_write("datadome=edge", {"article_page": False}) is False
    assert _ready_to_write(cookie, {"article_page": True, "ok": False}) is False


def test_refresh_cookie_missing_playwright_reports_install(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "playwright", None)

    with pytest.raises(UpstreamError, match=r"Playwright is not installed"):
        refresh_cookie_with_browser(env_path=tmp_path / ".env", timeout_s=1)
