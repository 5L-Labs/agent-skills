"""Extract the inline Feishu block-tree JSON from SSR HTML.

Feishu serializes every docx block as `"<token>":{"id":"<same-token>","version":N,"data":{...}}`
embedded in the HTML. We anchor on that pattern and balance-parse each object."""
from __future__ import annotations

import json
import re

_ANCHOR = re.compile(r'"([A-Za-z0-9_]{10,})":\{"id":"\1"')


def extract_blocks(html: str) -> dict[str, dict]:
    blocks: dict[str, dict] = {}
    for m in _ANCHOR.finditer(html):
        start = m.end() - len('{"id":"' + m.group(1) + '"')
        end = _find_balanced_end(html, start)
        if end is None:
            continue
        try:
            blocks[m.group(1)] = json.loads(html[start:end])
        except json.JSONDecodeError:
            continue
    return blocks


def _find_balanced_end(s: str, start: int) -> int | None:
    depth = 0
    i = start
    in_str = False
    esc = False
    while i < len(s):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return None
