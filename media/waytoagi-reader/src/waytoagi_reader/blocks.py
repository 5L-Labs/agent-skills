"""Walk Feishu blocks and decode AttributedText (the apool + run-encoded format)."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

_TRACKING_PARAMS = frozenset({
    "from", "from_app", "from_source", "fr", "utm_source", "utm_medium",
    "utm_campaign", "utm_content", "utm_term", "login_redirect_times",
})


def clean_url(url: str | None) -> str | None:
    """Drop Feishu and common UTM tracking params from a URL, keeping everything else."""
    if not url:
        return url
    try:
        parts = urlparse(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k not in _TRACKING_PARAMS]
    return urlunparse(parts._replace(query=urlencode(kept)))

_RUN_RE = re.compile(r'((?:\*[0-9a-z]+)+)\+([0-9a-z]+)')
_HEADING_RE = re.compile(r'heading(\d+)')


def block_type(b: dict) -> str:
    return ((b.get("data") or {}).get("type")) or ""


def block_parent(b: dict) -> str | None:
    return (b.get("data") or {}).get("parent_id")


def block_children(b: dict) -> list[str]:
    return ((b.get("data") or {}).get("children")) or []


def heading_level(t: str) -> int | None:
    m = _HEADING_RE.match(t)
    return int(m.group(1)) if m else None


def render_runs(b: dict) -> list[Any]:
    """Decode AttributedText into a list of `str` chunks interleaved with
    `{"type": "mention_doc", "title": ..., "url": ..., "token": ...}` dicts."""
    data = b.get("data") or {}
    t = data.get("text")
    if not isinstance(t, dict):
        return []
    apool = (t.get("apool") or {}).get("numToAttrib") or {}
    iat = t.get("initialAttributedTexts") or {}
    attribs = (iat.get("attribs") or {}).get("0", "")
    raw = (iat.get("text") or {}).get("0", "")

    out: list[Any] = []
    pos = 0
    for m in _RUN_RE.finditer(attribs):
        keys = re.findall(r"\*([0-9a-z]+)", m.group(1))
        # Etherpad / Feishu encode lengths in base 36.
        length = int(m.group(2), 36)
        chunk = raw[pos:pos + length]
        pos += length
        comp = None
        for k in keys:
            attrib = apool.get(k)
            if attrib and attrib[0] == "inline-component":
                try:
                    comp = json.loads(attrib[1])
                except (json.JSONDecodeError, TypeError):
                    comp = None
                if comp:
                    break
        if comp and comp.get("type") == "mention_doc":
            d = comp.get("data") or {}
            out.append({
                "type": "mention_doc",
                "title": d.get("title"),
                "url": clean_url(d.get("raw_url")),
                "token": d.get("token"),
            })
        else:
            out.append(chunk)
    if pos < len(raw):
        out.append(raw[pos:])
    return out


def render_text(b: dict) -> str:
    """Flat string form of a block's text. Mentions render as `《title》`."""
    parts = render_runs(b)
    out = []
    for p in parts:
        if isinstance(p, dict) and p.get("type") == "mention_doc":
            out.append(f"《{p.get('title') or ''}》")
        else:
            out.append(str(p))
    return "".join(out)


_EMPTY_BOOK_QUOTE_RE = re.compile(r"^[《〈]\s*[》〉]\s*")


def split_mention_and_summary(b: dict) -> tuple[dict | None, str]:
    """Convenience: split a bullet into (first mention_doc | None, remaining summary text).

    Real Feishu bullets often have literal `《 》` brackets in the source text with the
    linked title rendered as an overlay; once we've extracted the mention, the leftover
    empty brackets are noise and get stripped from the summary."""
    mention = None
    summary_parts = []
    for p in render_runs(b):
        if isinstance(p, dict) and p.get("type") == "mention_doc" and mention is None:
            mention = p
        elif isinstance(p, dict):
            summary_parts.append(f"《{p.get('title') or ''}》")
        else:
            summary_parts.append(p)
    summary = "".join(summary_parts).strip()
    if mention is not None:
        summary = _EMPTY_BOOK_QUOTE_RE.sub("", summary).strip()
    return mention, summary


def normalize_heading(s: str) -> str:
    """Strip emoji, whitespace, and punctuation so heading matching is glyph-tolerant."""
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s -⁯\U0001F000-\U0001FFFF\W_]+", "", s)


def find_heading(blocks: dict, needle: str) -> str | None:
    target = normalize_heading(needle)
    for bid, b in blocks.items():
        if heading_level(block_type(b)) is not None:
            if target and target in normalize_heading(render_text(b)):
                return bid
    return None


def find_first_mention(blocks: dict, title_needle: str) -> dict | None:
    """Scan all blocks for the first mention_doc whose title contains the needle.
    Used to auto-discover the archive doc link from the main doc."""
    target = normalize_heading(title_needle)
    for b in blocks.values():
        for part in render_runs(b):
            if isinstance(part, dict) and part.get("type") == "mention_doc":
                title = part.get("title") or ""
                if target and target in normalize_heading(title):
                    return part
    return None
