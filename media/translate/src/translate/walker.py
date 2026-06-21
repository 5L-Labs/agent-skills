"""Walk a JSON document and identify string fields eligible for translation.

The default set of fields covers what reader skills emit: `title`, `headline`,
`heading`, `summary`, `text`. The walker leaves the document structure intact —
it just yields (parent_dict, key, value) tuples so the caller can mutate in place
after translation.
"""
from __future__ import annotations

from typing import Iterable, Iterator

DEFAULT_FIELDS = frozenset({"title", "headline", "heading", "summary", "text"})


def iter_strings(
    doc,
    *,
    fields: Iterable[str] | None = None,
) -> Iterator[tuple[dict, str, str]]:
    """Yield `(container, key, value)` for every translatable string in `doc`.

    `container` is the dict directly holding the key — letting the caller write
    sibling keys (e.g. `<key>_en`) or mutate in place."""
    keep = frozenset(fields) if fields is not None else DEFAULT_FIELDS
    if isinstance(doc, dict):
        for k, v in list(doc.items()):
            if k in keep and isinstance(v, str) and v.strip():
                yield doc, k, v
            else:
                yield from iter_strings(v, fields=keep)
    elif isinstance(doc, list):
        for item in doc:
            yield from iter_strings(item, fields=keep)


def is_already_translated(container: dict, key: str, lang: str) -> bool:
    sib = f"{key}_{lang}"
    return sib in container and container[sib] is not None
