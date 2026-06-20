"""Render the WaytoAGI '历史更新' archive doc.

Structure differs from the main doc: every entry sits as a direct child of the
page root in a flat list. heading2 blocks are month markers (no children of their
own); heading3 blocks are days (with bullets as children)."""
from __future__ import annotations

from .blocks import (
    block_children,
    block_type,
    heading_level,
    render_text,
)
from .update_log import _render_day


def _find_root(blocks: dict) -> str | None:
    """The archive doc's root is the page block whose children list is the
    longest. Feishu sets `obj_type:page` on the doc root."""
    best_id = None
    best_n = -1
    for bid, b in blocks.items():
        if block_type(b) == "page":
            n = len(block_children(b))
            if n > best_n:
                best_n = n
                best_id = bid
    return best_id


def render(blocks: dict, *, source_url: str) -> dict:
    root_id = _find_root(blocks)
    if not root_id:
        return {
            "schema_version": 1,
            "source_url": source_url,
            "heading": None,
            "heading_id": None,
            "found": False,
            "days": [],
        }

    current_month: str | None = None
    days: list[dict] = []
    for cid in block_children(blocks[root_id]):
        b = blocks.get(cid)
        if not b:
            continue
        lvl = heading_level(block_type(b))
        if lvl == 2:
            current_month = render_text(b).strip() or None
        elif lvl == 3:
            day = _render_day(blocks, cid)
            if day["heading"] or day["items"]:
                day["month"] = current_month
                days.append(day)

    return {
        "schema_version": 1,
        "source_url": source_url,
        "heading": render_text(blocks[root_id]).strip() or None,
        "heading_id": root_id,
        "found": True,
        "days": days,
    }
