"""Ollama backend. Hits the local Ollama HTTP API (default localhost:11434).

Stdlib-only — uses urllib so the package has zero install-time dependencies.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request


_SYSTEM_PROMPT = (
    "You are a precise translator. Translate the user's text into the target language. "
    "Preserve proper nouns, product names, code identifiers, URLs, and numbers exactly. "
    "Do not add commentary or wrap the output in quotes — return only the translated text."
)

_DEFAULT_MAX_RETRIES = 2
_BACKOFF_BASE_SEC = 0.5


def _is_retryable(exc: Exception) -> bool:
    """5xx, connection errors, and timeouts are retryable. 4xx and parse errors are not."""
    if isinstance(exc, urllib.error.HTTPError):
        return 500 <= exc.code < 600
    return isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError))


class OllamaBackend:
    name = "ollama"

    def __init__(self, *, model: str | None = None, host: str | None = None, timeout: float | None = None):
        self.model = model or os.environ.get("TRANSLATE_MODEL", "qwen2.5:7b-instruct")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        timeout_ms = int(os.environ.get("TRANSLATE_TIMEOUT_MS", "30000"))
        self.timeout = (timeout if timeout is not None else timeout_ms / 1000.0)
        self.max_retries = int(os.environ.get("TRANSLATE_MAX_RETRIES", str(_DEFAULT_MAX_RETRIES)))

    def cache_signature(self) -> str:
        prompt_digest = hashlib.sha256(_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]
        return f"ollama:{self.model}:{prompt_digest}"

    def translate(self, text: str, *, source: str, target: str) -> str:
        prompt = (
            f"Source language: {source}\n"
            f"Target language: {target}\n"
            f"Text:\n{text}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        body = self._post_with_retry(f"{self.host}/api/chat", payload)
        return (body.get("message") or {}).get("content", "").strip()

    def _post_with_retry(self, url: str, payload: dict) -> dict:
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("Invalid URL scheme: only HTTP and HTTPS are permitted")
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310
                    return json.loads(resp.read())
            except Exception as exc:  # noqa: BLE001
                if attempt >= self.max_retries or not _is_retryable(exc):
                    raise
                time.sleep(_BACKOFF_BASE_SEC * (2 ** attempt))
        raise RuntimeError("unreachable")  # pragma: no cover
