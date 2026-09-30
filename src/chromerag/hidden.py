"""Remove non-rendered nodes and skip-navigation links before scoring."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

_PROTECTED = frozenset({"html", "body", "main", "article"})
_DISPLAY_NONE = re.compile(r"display\s*:\s*none", re.I)
_VISIBILITY_HIDDEN = re.compile(r"visibility\s*:\s*hidden", re.I)
_SKIP_LINK = re.compile(
    r"^skip to (main )?content$|^skip to navigation$|^jump to content$",
    re.I,
)
_ARIA_MODAL_TOKENS = frozenset({"modal", "dialog", "popup", "overlay"})


def _class_tokens(tag: Tag) -> set[str]:
    raw = tag.get("class") or []
    tokens: set[str] = set()
    for item in raw:
        for part in re.split(r"[\s_\-:/]+", str(item).lower()):
            if part:
                tokens.add(part)
    return tokens


def _is_hidden(tag: Tag) -> bool:
    if not getattr(tag, "attrs", None):
        return False
    if tag.has_attr("hidden"):
        return True
    style = tag.get("style") or ""
    if isinstance(style, list):
        style = " ".join(str(s) for s in style)
    style = str(style)
    if _DISPLAY_NONE.search(style) or _VISIBILITY_HIDDEN.search(style):
        return True
    if (tag.get("aria-hidden") or "").lower() == "true":
        text_len = len(tag.get_text(" ", strip=True))
        if text_len < 120 or _class_tokens(tag) & _ARIA_MODAL_TOKENS:
            return True
    return False


def remove_hidden_nodes(soup: BeautifulSoup) -> int:
    """Drop non-rendered subtrees. Returns count removed."""
    removed = 0
    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag) or tag.name in _PROTECTED:
            continue
        if _is_hidden(tag):
            tag.decompose()
            removed += 1
    return removed


def remove_skip_links(soup: BeautifulSoup) -> int:
    """Drop skip-navigation anchors and empty wrappers."""
    removed = 0
    for anchor in list(soup.find_all("a")):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href") or ""
        if not str(href).startswith("#"):
            continue
        text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip().lower()
        if not _SKIP_LINK.match(text):
            continue
        parent = anchor.parent
        anchor.decompose()
        removed += 1
        if isinstance(parent, Tag) and parent.name not in _PROTECTED:
            parent_text = parent.get_text(" ", strip=True)
            if len(parent_text) < 15:
                parent.decompose()
                removed += 1
    return removed
