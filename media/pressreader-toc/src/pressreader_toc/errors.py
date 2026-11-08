from __future__ import annotations
from news_reader_base.errors import create_reader_errors

ERRORS = create_reader_errors("PressReader")
PressReaderError = ERRORS["PressReaderError"]
SessionExpiredError = ERRORS["PressReaderSessionExpiredError"]
NotFoundError = ERRORS["PressReaderNotFoundError"]
UpstreamError = ERRORS["PressReaderUpstreamError"]
