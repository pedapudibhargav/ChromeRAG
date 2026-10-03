"""Optional density heuristics adapted from Trafilatura htmlprocessing (Apache-2.0)."""

from __future__ import annotations

import re
from typing import Any

from bs4 import Tag

from chromerag.domutil import all_tags
from chromerag.treestats import TreeStats

_BLOCK_TAGS = frozenset({"div", "p", "section", "aside", "nav"})
_MICRO_TAGS = frozenset({"p", "li"})
_ALNUM = re.compile(r"[A-Za-z0-9]")
_SUBSTANTIVE = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "pre", "table", "article", "blockquote"})


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _alnum_count(text: str) -> int:
    return len(_ALNUM.findall(text))


def _page_h1_ancestor_ids(root: Tag | None) -> frozenset[int]:
    """Ids of the page's first ``h1`` and of every element that contains it: the ones a pass must keep."""
    if root is None:
        return frozenset()
    h1 = root.find("h1")
    if h1 is None or not isinstance(h1, Tag):
        return frozenset()
    ids = {id(h1)}
    ids.update(id(p) for p in h1.parents if isinstance(p, Tag))
    return frozenset(ids)


def _substantive_ancestor_ids(scope: Tag, stats: TreeStats) -> frozenset[int]:
    """Ids of the elements that have a substantive descendant (heading, pre, table... with >= 40 chars of text)."""
    ids: set[int] = set()
    for tag in all_tags(scope):
        if tag.name in _SUBSTANTIVE and stats.text_len(tag) >= 40:
            ids.update(id(p) for p in tag.parents if isinstance(p, Tag))
    return frozenset(ids)


def _in_main_article(tag: Tag) -> bool:
    for parent in tag.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in ("main", "article"):
            return True
        role = (parent.get("role") or "").lower()
        if role in ("main", "article"):
            return True
    return False


def _is_editorial_list(tag: Tag, stats: TreeStats) -> bool:
    """Keep short link lists with many items inside main/article (Trafilatura GH #788)."""
    if tag.name not in ("ul", "ol"):
        return False
    if not _in_main_article(tag):
        return False
    items = [c for c in tag.children if isinstance(c, Tag) and c.name == "li"]
    if len(items) < 5:
        return False
    short = sum(1 for li in items if stats.text_len(li) < 60)
    return short >= 5


def _has_substantive_descendant(tag: Tag, stats: TreeStats, substantive_ancestors: frozenset[int]) -> bool:
    if stats.long_paragraphs(tag) > 0:
        return True
    return id(tag) in substantive_ancestors


def _too_large(
    tag: Tag, root: Tag | None, root_words: int, stats: TreeStats, h1_keep: frozenset[int]
) -> bool:
    if root is not None and tag is root:
        return True
    if id(tag) in h1_keep:
        return True
    return root_words > 0 and stats.words(tag) > 0.4 * root_words


def _drop_link_dense_blocks(
    soup_tag: Tag,
    *,
    root: Tag | None,
    root_words: int,
    stats: TreeStats,
) -> int:
    removed = 0
    h1_keep = _page_h1_ancestor_ids(root)
    substantive = _substantive_ancestor_ids(soup_tag, stats)
    for tag in list(all_tags(soup_tag)):
        if tag.attrs is None or tag.name not in _BLOCK_TAGS:
            continue
        if _too_large(tag, root, root_words, stats, h1_keep):
            continue
        if _has_substantive_descendant(tag, stats, substantive):
            continue
        if _is_editorial_list(tag, stats):
            continue
        text_len = stats.text_len(tag)
        if text_len == 0 or stats.words(tag) >= 40:
            continue
        link_len = stats.link_len(tag)
        if text_len == 0 or link_len < 0.8 * text_len:
            continue
        tag.decompose()
        removed += 1
    return removed


def _drop_micro_leaves(
    soup_tag: Tag,
    *,
    root: Tag | None,
    root_words: int,
    stats: TreeStats,
) -> int:
    removed = 0
    h1_keep = _page_h1_ancestor_ids(root)
    for tag in list(all_tags(soup_tag)):
        if tag.attrs is None or tag.name not in _MICRO_TAGS:
            continue
        if any(isinstance(c, Tag) for c in tag.children):
            continue
        if _too_large(tag, root, root_words, stats, h1_keep):
            continue
        text = tag.get_text(" ", strip=True)
        if _alnum_count(text) >= 8:
            continue
        tag.decompose()
        removed += 1
    return removed


def apply_trafilatura_ideas(
    soup_tag: Tag,
    cfg: Any,
    content_root: Tag | None,
    *,
    stats: TreeStats | None = None,
) -> dict[str, int]:
    """Run optional Trafilatura-inspired density passes. Returns per-pass removal counts."""
    root = content_root
    body = soup_tag if soup_tag.name == "body" else soup_tag.find("body")
    scope = body if isinstance(body, Tag) else soup_tag
    stats = stats or TreeStats(scope)
    root_words = _word_count(scope.get_text(" ", strip=True))

    out: dict[str, int] = {}
    if getattr(cfg, "trafilatura_link_blocks", True):
        out["link_blocks"] = _drop_link_dense_blocks(scope, root=root, root_words=root_words, stats=stats)
        if out["link_blocks"]:
            stats = TreeStats(scope)
    if getattr(cfg, "trafilatura_micro", True):
        out["micro"] = _drop_micro_leaves(scope, root=root, root_words=root_words, stats=stats)
    return out
