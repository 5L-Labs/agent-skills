"""Refresh WSJ_COOKIE from a real browser profile.

This module intentionally imports Playwright lazily so normal wsj-reader usage
does not require browser automation dependencies or installed browser binaries.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

from .client import SessionExpiredError, UpstreamError

DEFAULT_PROFILE_DIR = "~/.wsj-reader-browser"
DEFAULT_REFRESH_URL = "https://www.wsj.com/"


def refresh_cookie_with_browser(
    *,
    url: str = DEFAULT_REFRESH_URL,
    profile_dir: Optional[str] = None,
    env_path: Optional[Path] = None,
    headless: bool = False,
    timeout_s: int = 120,
    write: bool = True,
) -> dict:
    """Launch Chromium, let WSJ set browser cookies, and write WSJ_COOKIE.

    Headed mode is the default because DataDome and login flows are designed for
    a real interactive browser session. The profile is persistent so a user who
    logs in once can refresh cookies later without reauthenticating every run.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise UpstreamError(
            "Playwright is not installed. Install with: "
            "pip install -e '.[browser]' && python -m playwright install chromium"
        ) from e

    target = url or DEFAULT_REFRESH_URL
    profile = Path(profile_dir or os.environ.get("WSJ_BROWSER_PROFILE_DIR", DEFAULT_PROFILE_DIR)).expanduser()
    env_file = env_path or Path(__file__).resolve().parent.parent.parent / ".env"
    deadline = time.monotonic() + max(timeout_s, 1)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(profile),
            headless=headless,
            viewport={"width": 1440, "height": 1000},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(target, wait_until="domcontentloaded", timeout=60_000)
            status: dict[str, Any] = {}
            while True:
                page.wait_for_load_state("domcontentloaded", timeout=10_000)
                status = _article_unlock_status(page)
                cookie_header = _cookie_header_from_playwright(
                    context.cookies("https://www.wsj.com/")
                )
                if _ready_to_write(cookie_header, status):
                    break
                if time.monotonic() >= deadline:
                    raise SessionExpiredError(
                        "Browser did not produce an unlocked WSJ session before timeout. "
                        "Sign in to WSJ in the opened browser and retry."
                    )
                time.sleep(2)
            if write:
                _update_env_cookie(env_file, cookie_header)
            return {
                "url": target,
                "profile_dir": str(profile),
                "env_path": str(env_file),
                "wrote": write,
                "cookie_count": _cookie_count(cookie_header),
                **status,
            }
        finally:
            context.close()


def _ready_to_write(cookie_header: str, status: dict[str, Any]) -> bool:
    if "datadome=" not in cookie_header or "ca_id=" not in cookie_header:
        return False
    if not status.get("article_page"):
        return True
    return bool(status.get("ok"))


def _article_unlock_status(page) -> dict[str, Any]:
    data = page.evaluate(
        """() => {
          const el = document.querySelector('script#__NEXT_DATA__');
          if (!el) return {article_page: false};
          const payload = JSON.parse(el.textContent || '{}');
          const pp = payload?.props?.pageProps || {};
          const art = pp.articleData || {};
          const body = art.flattenedBody || art.articleBody || [];
          const paragraphs = Array.isArray(body)
            ? body.filter((b) => b && b.type === 'paragraph').length
            : 0;
          const articlePage = Boolean(art.originId || art.upstreamOriginId || pp.isSnippetView);
          const snippet = Boolean(pp.isSnippetView);
          const serverUnlocked = Boolean(pp.isServerUnlockedContent);
          return {
            article_page: articlePage,
            ok: articlePage ? (!snippet && serverUnlocked && paragraphs > 5) : false,
            snippet,
            serverUnlocked,
            paragraphs,
            body_blocks: Array.isArray(body) ? body.length : 0,
            article_id: art.originId || art.upstreamOriginId || null,
          };
        }"""
    )
    return data if isinstance(data, dict) else {"article_page": False}


def _cookie_header_from_playwright(cookies: list[dict[str, Any]]) -> str:
    wsj_cookies = [
        cookie
        for cookie in cookies
        if cookie.get("name") and _is_wsj_cookie_domain(str(cookie.get("domain", "")))
    ]
    return "; ".join(f"{cookie['name']}={cookie.get('value', '')}" for cookie in wsj_cookies)


def _is_wsj_cookie_domain(domain: str) -> bool:
    normalized = domain.lstrip(".").lower()
    return normalized == "wsj.com" or normalized.endswith(".wsj.com")


def _cookie_count(cookie_header: str) -> int:
    return sum(1 for part in cookie_header.split(";") if "=" in part)


def _update_env_cookie(env_path: Path, cookie_header: str) -> None:
    existing = env_path.read_text() if env_path.exists() else ""
    lines: list[str] = []
    seen = False
    for line in existing.splitlines():
        if line.startswith("WSJ_COOKIE="):
            lines.append(f"WSJ_COOKIE={cookie_header}")
            seen = True
        else:
            lines.append(line)
    if not seen:
        lines.append(f"WSJ_COOKIE={cookie_header}")
    env_path.write_text("\n".join(lines).rstrip() + "\n")
    os.chmod(env_path, 0o600)
