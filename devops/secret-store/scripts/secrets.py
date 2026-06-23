"""
Secret store loader for Hermes skills and agent workflows.

Usage:
    from secrets import load_secret, load_env, list_secrets

    pat = load_secret("github.pat")
    ft = load_env("ft-cookie.env")
    all = list_secrets()
"""

import os
from pathlib import Path
from typing import Optional, Dict

STORE_ROOT = Path("/opt/data/secrets")


def _resolve(name: str) -> Path:
    """Resolve a secret name to its absolute path in the store."""
    path = STORE_ROOT / name

    # SECURITY: Prevent path traversal by checking if the resolved path is inside STORE_ROOT
    resolved_path = path.resolve(strict=False)
    resolved_root = STORE_ROOT.resolve(strict=False)
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError(f"Path traversal detected: {name}")

    if not path.exists():
        # Check subdirectories
        for sub in STORE_ROOT.iterdir():
            if sub.is_dir():
                candidate = sub / name
                if candidate.exists():
                    # SECURITY: also check traversal for the candidate
                    resolved_cand = candidate.resolve(strict=False)
                    if not resolved_cand.is_relative_to(resolved_root):
                        continue
                    return candidate
        raise FileNotFoundError(f"Secret '{name}' not found in {STORE_ROOT}")
    return path


def load_secret(name: str) -> str:
    """Load a raw secret file (single value, no KEY= format). Returns stripped string."""
    path = _resolve(name)
    return path.read_text(encoding="utf-8").strip()


def load_env(name: str) -> Dict[str, str]:
    """Load an env-style secret file (KEY=VALUE lines). Returns dict."""
    path = _resolve(name)
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def list_secrets() -> Dict[str, str]:
    """List all available secrets. Returns dict of name → absolute path."""
    secrets = {}
    for entry in STORE_ROOT.iterdir():
        if entry.name == "README.md" or entry.name.startswith("."):
            continue
        if entry.is_dir():
            for sub in entry.iterdir():
                if not sub.name.startswith("."):
                    secrets[f"{entry.name}/{sub.name}"] = str(sub)
        else:
            if not entry.name.startswith("."):
                secrets[entry.name] = str(entry)
    return secrets


def inject_env(name: str) -> None:
    """Load an env-style secret and inject into os.environ. Use before running subprocess tools."""
    env_vars = load_env(name)
    os.environ.update(env_vars)
