"""Minimal dotenv loader for local API key configuration."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | None = None) -> list[str]:
    """Load missing environment variables from a ``.env`` file."""
    env_path = path or _default_env_path()
    if env_path is None or not env_path.exists():
        return []

    loaded: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        cleaned_value = _clean_value(value)
        if not key or not cleaned_value or key in os.environ:
            continue
        os.environ[key] = cleaned_value
        loaded.append(key)
    return loaded


def _default_env_path() -> Path | None:
    """Find the nearest project-level ``.env`` file."""
    candidates = (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _clean_value(value: str) -> str:
    """Trim whitespace and matching quotes from an environment value."""
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]
    return cleaned
