"""Persist and load normalized issue data.

Layout:
  <PRESSREADER_DATA_DIR>/
    v99e-2026-07-04.json       — normalized + match enrichment (schema_version)
    v99e-2026-07-04.raw.json   — verbatim TOC response (for re-normalization)

Atomic writes via temp file + os.rename so Ctrl-C never corrupts.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = 1

_DEFAULT_DIR = Path.home() / ".pressreader" / "issues"


def _data_dir() -> Path:
    override = os.environ.get("PRESSREADER_DATA_DIR")
    d = Path(override) if override else _DEFAULT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stem(cid: str, issue_date: date) -> str:
    return f"{cid}-{issue_date.strftime('%Y-%m-%d')}"


def _norm_path(cid: str, issue_date: date) -> Path:
    return _data_dir() / f"{_stem(cid, issue_date)}.json"


def _raw_path(cid: str, issue_date: date) -> Path:
    return _data_dir() / f"{_stem(cid, issue_date)}.raw.json"


def _atomic_write(path: Path, data: dict) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        prefix=".tmp.",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        tmp = Path(f.name)
    os.rename(tmp, path)


def save_raw(cid: str, issue_date: date, raw: dict) -> Path:
    path = _raw_path(cid, issue_date)
    _atomic_write(path, raw)
    return path


def save_normalized(cid: str, issue_date: date, entries: list[dict]) -> Path:
    path = _norm_path(cid, issue_date)
    doc = {"schema_version": SCHEMA_VERSION, "cid": cid,
           "issue_date": issue_date.isoformat(), "entries": entries}
    _atomic_write(path, doc)
    return path


def load_normalized(cid: str, issue_date: date) -> Optional[dict]:
    path = _norm_path(cid, issue_date)
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    if doc.get("schema_version") != SCHEMA_VERSION:
        return None  # caller should --refresh to re-normalize from raw
    return doc


def load_raw(cid: str, issue_date: date) -> Optional[dict]:
    path = _raw_path(cid, issue_date)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def normalized_exists(cid: str, issue_date: date) -> bool:
    path = _norm_path(cid, issue_date)
    if not path.exists():
        return False
    try:
        doc = json.loads(path.read_text())
        return doc.get("schema_version") == SCHEMA_VERSION
    except Exception:
        return False


def update_entries(cid: str, issue_date: date, updated: list[dict]) -> None:
    """Replace the entries list atomically (used by match to persist progress)."""
    doc = load_normalized(cid, issue_date) or {
        "schema_version": SCHEMA_VERSION,
        "cid": cid,
        "issue_date": issue_date.isoformat(),
    }
    doc["entries"] = updated
    _atomic_write(_norm_path(cid, issue_date), doc)
