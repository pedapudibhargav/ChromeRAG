"""Remove non-rendered nodes and skip-navigation links before scoring."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from chromerag.density import NOISE_ID_CLASS_RE, NOISE_TOKENS, _attr_tokens, _attrs_blob
from chromerag.domutil import all_tags, tags_named

_PROTECTED = frozenset({"html", "body", "main", "article"})
_DISPLAY_NONE = re.compile(r"display\s*:\s*none", re.I)
_VISIBILITY_HIDDEN = re.compile(r"visibility\s*:\s*hidden", re.I)
_SKIP_LINK = re.compile(
    r"^skip to (main )?content$|^skip to navigation$|^jump to content$",
    re.I,
)
_ARIA_MODAL_TOKENS = frozenset({"modal", "dialog", "popup", "overlay"})
_CHROME_TAGS = frozenset({"nav", "aside", "header", "footer"})
_CHROME_ROLES = frozenset({"dialog", "navigation", "menu"})
# Extra chrome tokens beyond density.NOISE_TOKENS (drawer / off-canvas / dialog).
_CHROME_EXTRA_TOKENS = frozenset({"drawer", "offcanvas", "dialog"})
_CHROME_EXTRA_RE = re.compile(r"off-?canvas|drawer", re.I)

_HIDDEN_ARTICLE_MIN_CHARS = 1500
_HIDDEN_ARTICLE_MAX_LINK_SHARE = 0.25
# Visible body outside CSS-hidden nodes shorter than one short paragraph means the
# page has no readable main content yet (SPA/CSS still hiding the real body).
# 250 chars ≈ 40–50 words; sensitivity checked at half (125) and double (500).
_HIDDEN_VISIBLE_TOO_THIN = 250


def _class_tokens(tag: Tag) -> set[str]:
    raw = tag.get("class") or []
    tokens: set[str] = set()
    for item in raw:
        for part in re.split(r"[\s_\-:/]+", str(item).lower()):
            if part:
                tokens.add(part)
    return tokens


def _is_css_hidden(tag: Tag) -> bool:
    if not getattr(tag, "attrs", None):
        return False
    style = tag.get("style") or ""
    if isinstance(style, list):
        style = " ".join(str(s) for s in style)
    style = str(style)
    return bool(tag.has_attr("hidden") or _DISPLAY_NONE.search(style) or _VISIBILITY_HIDDEN.search(style))


def _is_chrome_by_meaning(tag: Tag) -> bool:
    """True when a node is chrome (nav/chrome tokens/dialog), never to be rescued."""
    if not isinstance(tag, Tag) or not tag.name:
        return False
    if tag.name in _CHROME_TAGS:
        return True
    role = ""
    if getattr(tag, "attrs", None):
        role = (tag.get("role") or "").lower()
    if role in _CHROME_ROLES:
        return True
    tokens = _attr_tokens(tag)
    if tokens & NOISE_TOKENS or tokens & _CHROME_EXTRA_TOKENS:
        return True
    blob = _attrs_blob(tag)
    if blob and (NOISE_ID_CLASS_RE.search(blob) or _CHROME_EXTRA_RE.search(blob)):
        return True
    return False


def _visible_body_chars(body: Tag) -> int:
    """Chars in ``body`` outside topmost CSS-hidden subtrees (no rescue)."""
    hidden_roots: list[Tag] = []
    for tag in all_tags(body):
        if not isinstance(tag, Tag) or tag.name in _PROTECTED or not _is_css_hidden(tag):
            continue
        if any(any(parent is h for h in hidden_roots) for parent in tag.parents):
            continue
        hidden_roots.append(tag)
    total = len(body.get_text(" ", strip=True))
    hidden = sum(len(h.get_text(" ", strip=True)) for h in hidden_roots)
    return max(0, total - hidden)


def _is_hidden_article(tag: Tag, *, visible_chars: int) -> bool:
    """A hidden block with long running text is page content that a script reveals
    (tab panels, expanders, lazy-shown articles), not a menu or a dialog.

    Link-dense hidden blocks are rescued only when visible body text outside hidden
    nodes is too thin to be the page (no visible main content).
    """
    if _is_chrome_by_meaning(tag):
        return False
    text_len = len(tag.get_text(" ", strip=True))
    if text_len < _HIDDEN_ARTICLE_MIN_CHARS:
        return False
    link_len = sum(len(a.get_text(" ", strip=True)) for a in tag.find_all("a"))
    link_share = link_len / text_len
    if link_share < _HIDDEN_ARTICLE_MAX_LINK_SHARE:
        return True
    # Meaning-based dominant rule: only when the unhidden page is not yet a page.
    if visible_chars < _HIDDEN_VISIBLE_TOO_THIN:
        return True
    return False


def _is_hidden(tag: Tag, *, visible_chars: int) -> bool:
    if not getattr(tag, "attrs", None):
        return False
    if _is_css_hidden(tag):
        return not _is_hidden_article(tag, visible_chars=visible_chars)
    if (tag.get("aria-hidden") or "").lower() == "true":
        # Chrome by meaning is never kept, matching the CSS-hidden rescue policy.
        if _is_chrome_by_meaning(tag):
            return True
        text_len = len(tag.get_text(" ", strip=True))
        if text_len < 120 or _class_tokens(tag) & _ARIA_MODAL_TOKENS:
            return True
    return False


def remove_hidden_nodes(soup: BeautifulSoup) -> int:
    """Drop non-rendered subtrees. Returns count removed.

    Rescued wrappers stay, but nested hidden chrome still decomposes on later visits.
    """
    body = soup.body if isinstance(soup.body, Tag) else soup
    visible_chars = _visible_body_chars(body) if isinstance(body, Tag) else 0
    removed = 0
    for tag in all_tags(soup):
        if not isinstance(tag, Tag) or tag.name in _PROTECTED:
            continue
        if _is_hidden(tag, visible_chars=visible_chars):
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
