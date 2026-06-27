from __future__ import annotations

import json

from news_reader_base import emit, wrap
from news_reader_base.errors import NotFoundError, SessionExpiredError


def test_wrap_adds_schema_version():
    assert wrap({"a": 1}, schema_version=2) == {"schema_version": 2, "a": 1}


def test_wrap_passthrough_when_schema_version_present():
    payload = {"schema_version": 1, "x": 1}
    assert wrap(payload, schema_version=2) is payload


def test_wrap_scalar_wraps_under_value():
    assert wrap("hi", schema_version=1) == {"schema_version": 1, "value": "hi"}


def test_emit_success_returns_zero(capsys):
    rc = emit({"ok": True})
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out) == {"ok": True}


def test_emit_error_returns_exit_code(capsys):
    rc = emit(None, error=SessionExpiredError("expired"))
    cap = capsys.readouterr()
    assert rc == 2
    assert "SESSION_EXPIRED" in cap.err


def test_emit_json_errors_writes_stdout(capsys):
    rc = emit(None, json_errors=True, error=NotFoundError("missing"))
    cap = capsys.readouterr()
    assert rc == 3
    parsed = json.loads(cap.out)
    assert parsed == {"error": {"code": "NOT_FOUND", "message": "missing"}}
