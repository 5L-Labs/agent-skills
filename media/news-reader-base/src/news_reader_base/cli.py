"""CLI helpers shared by reader skills.

Each skill builds its own argparse subcommand tree but uses these helpers for
consistent error emission, --json-errors / --no-cache flags, and stdout wrapping.
"""
from __future__ import annotations
import argparse
import json
import sys
from typing import Any, Optional

from .errors import ReaderError


def add_common_flags(sp: argparse.ArgumentParser) -> None:
    """Per-subcommand: --json-errors and --no-cache."""
    sp.add_argument(
        "--json-errors",
        action="store_true",
        help="Also emit structured {'error': ...} JSON on stdout when failing.",
    )
    sp.add_argument("--no-cache", action="store_true")


def emit(
    payload: Any,
    *,
    json_errors: bool = False,
    error: Optional[ReaderError] = None,
) -> int:
    """Print JSON payload or error and return the CLI exit code."""
    if error is None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"{error.code}: {error}", file=sys.stderr)
    if json_errors:
        print(json.dumps({"error": {"code": error.code, "message": str(error)}}))
    return error.exit_code


def wrap(payload: Any, schema_version: int) -> dict:
    """Ensure the payload is a dict with `schema_version` set."""
    if isinstance(payload, dict) and "schema_version" in payload:
        return payload
    if isinstance(payload, dict):
        return {"schema_version": schema_version, **payload}
    return {"schema_version": schema_version, "value": payload}
