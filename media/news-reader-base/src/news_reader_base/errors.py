"""Exception hierarchy with CLI exit codes.

Each reader skill subclasses ReaderError with its own concrete name (FTError,
NYTError, WSJError) so `except` blocks remain source-specific.
"""
from __future__ import annotations


class ReaderError(Exception):
    exit_code = 1
    code = "ERROR"


class SessionExpiredError(ReaderError):
    exit_code = 2
    code = "SESSION_EXPIRED"


class NotFoundError(ReaderError):
    exit_code = 3
    code = "NOT_FOUND"


class UpstreamError(ReaderError):
    exit_code = 4
    code = "NETWORK"
