"""Remove non-rendered nodes and skip-navigation links before scoring."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from chromerag.domutil import all_tags, tags_named

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


_HIDDEN_ARTICLE_MIN_CHARS = 1500
_HIDDEN_ARTICLE_MAX_LINK_SHARE = 0.25


def _is_hidden_article(tag: Tag) -> bool:
    """A hidden block with long running text and few links is page content that a script reveals
    (tab panels, expanders, lazy-shown articles), not a menu or a dialog."""
    text_len = len(tag.get_text(" ", strip=True))
    if text_len < _HIDDEN_ARTICLE_MIN_CHARS:
        return False
    link_len = sum(len(a.get_text(" ", strip=True)) for a in tag.find_all("a"))
    return link_len / text_len < _HIDDEN_ARTICLE_MAX_LINK_SHARE


def _is_hidden(tag: Tag) -> bool:
    if not getattr(tag, "attrs", None):
        return False
    style = tag.get("style") or ""
    if isinstance(style, list):
        style = " ".join(str(s) for s in style)
    style = str(style)
    if tag.has_attr("hidden") or _DISPLAY_NONE.search(style) or _VISIBILITY_HIDDEN.search(style):
        return not _is_hidden_article(tag)
    if (tag.get("aria-hidden") or "").lower() == "true":
        text_len = len(tag.get_text(" ", strip=True))
        if text_len < 120 or _class_tokens(tag) & _ARIA_MODAL_TOKENS:
            return True
    return False


def remove_hidden_nodes(soup: BeautifulSoup) -> int:
    """Drop non-rendered subtrees. Returns count removed."""
    removed = 0
    for tag in all_tags(soup):
        if not isinstance(tag, Tag) or tag.name in _PROTECTED:
            continue
        if _is_hidden(tag):
            tag.decompose()
            removed += 1
    return removed


def remove_skip_links(soup: BeautifulSoup) -> int:
    """Drop skip-navigation anchors and empty wrappers."""
    removed = 0
    for anchor in tags_named(soup, ("a",)):
        # An earlier iteration may have removed this anchor's wrapper; decomposed tags have no attrs.
        if not isinstance(anchor, Tag) or anchor.attrs is None:
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
