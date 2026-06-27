"""Minimal .env loader.

Deliberately does NOT walk up the filesystem — that would let unrelated project
.env files (or ~/.env) leak credentials into the skill process. Looks only in
the given skill directory and the current working directory.
"""
from __future__ import annotations
import os
from pathlib import Path


def load_dotenv(skill_dir: Path) -> None:
    for candidate in (skill_dir / ".env", Path.cwd() / ".env"):
        if not candidate.is_file():
            continue
        for line in candidate.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        return
