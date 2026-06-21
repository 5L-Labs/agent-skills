"""Deterministic no-op backend. Useful for pipeline testing — no network, no LLM."""
from __future__ import annotations


class NoopBackend:
    name = "noop"
    model = "noop"

    def translate(self, text: str, *, source: str, target: str) -> str:
        return f"[{target}] {text}"

    def cache_signature(self) -> str:
        return "noop:v1"
