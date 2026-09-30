"""Locate the primary content root in a page."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from chromerag.config import PageType

_BODY_CLASS_RE = re.compile(
    r"(^|[\s\"'])"
    r"(entry|post|article|page|text)[-_]?(content|body)"
    r"([\s\"']|$)|"
    r"article-?body|story-?body|main-?content|content-?main|page-content|"
    r"markdown|theme-doc-markdown|md-content|rst-content|vp-doc|td-content|"
    r"sl-markdown-content|prose",
    re.I,
)
_CONTENT_EXACT = re.compile(r"^content$", re.I)


def _word_count(tag: Tag) -> int:
    return len(re.findall(r"\w+", tag.get_text(" ", strip=True).lower()))


def _accept(tag: Tag, body_words: int, cache: dict[int, int]) -> bool:
    key = id(tag)
    if key not in cache:
        cache[key] = _word_count(tag)
    words = cache[key]
    if words < 100:
        return False
    return body_words == 0 or words >= 0.4 * body_words


def _attr_blob(tag: Tag) -> str:
    bits = [str(tag.get("id") or "")]
    bits.extend(str(c) for c in (tag.get("class") or []))
    return " ".join(bits)


def _iter_candidates(body: Tag) -> list[tuple[Tag, str]]:
    found: list[tuple[Tag, str]] = []
    for tag in body.find_all("main"):
        if isinstance(tag, Tag):
            found.append((tag, "main"))
    for tag in body.find_all(attrs={"role": "main"}):
        if isinstance(tag, Tag):
            found.append((tag, "role=main"))
    for tag in body.find_all("article"):
        if isinstance(tag, Tag):
            found.append((tag, "article"))
    for tag in body.find_all(True):
        if not isinstance(tag, Tag):
            continue
        if tag.get("itemprop") == "articleBody":
            found.append((tag, "itemprop=articleBody"))
            continue
        blob = _attr_blob(tag)
        if blob and _BODY_CLASS_RE.search(blob):
            found.append((tag, "content-class"))
    for tag in body.find_all(True):
        if not isinstance(tag, Tag):
            continue
        ident = (tag.get("id") or "").strip()
        classes = tag.get("class") or []
        if _CONTENT_EXACT.match(ident) or any(_CONTENT_EXACT.match(str(c)) for c in classes):
            found.append((tag, "id/class=content"))
    return found


def find_content_root(
    soup: BeautifulSoup,
    page_type: PageType | str = PageType.UNKNOWN,
) -> tuple[Tag, str]:
    """Return (root tag, candidate label). Falls back to body."""
    del page_type  # reserved for platform-specific overrides in WP6
    body = soup.body
    if body is None or not isinstance(body, Tag):
        fallback = soup.find("body")
        if isinstance(fallback, Tag):
            return fallback, "body"
        return soup, "body"  # type: ignore[return-value]

    cache: dict[int, int] = {id(body): _word_count(body)}
    body_words = cache[id(body)]

    seen: set[int] = set()
    for tag, label in _iter_candidates(body):
        key = id(tag)
        if key in seen:
            continue
        seen.add(key)
        if _accept(tag, body_words, cache):
            return tag, label
    return body, "body"
