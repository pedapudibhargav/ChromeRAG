"""Small DOM helpers that are faster than ``find_all`` (which runs a filter object per element)."""

from __future__ import annotations

from collections.abc import Iterable

from bs4 import Tag


def all_tags(root: Tag) -> list[Tag]:
    """Every element below ``root`` in document order (a snapshot, safe to modify the tree while looping)."""
    return [n for n in root.descendants if isinstance(n, Tag)]


def tags_named(root: Tag, names: Iterable[str]) -> list[Tag]:
    """Elements below ``root`` whose tag name is in ``names``."""
    wanted = names if isinstance(names, (set, frozenset)) else frozenset(names)
    return [n for n in root.descendants if isinstance(n, Tag) and n.name in wanted]
