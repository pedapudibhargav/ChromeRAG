"""Shared metadata helper for the framework integrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def path_key(path: str | Path) -> str:
    """Normalize path strings for URL lookup (forward slashes on all platforms)."""
    return Path(path).as_posix()


def flat(value: Any) -> str | int | float | bool | None:
    """Vector stores accept scalar metadata only; lists (e.g. breadcrumbs) become 'a > b'."""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(v, (str, int, float)) for v in value):
        return " > ".join(str(v) for v in value)
    return None
