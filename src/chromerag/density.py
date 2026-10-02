"""Structural + density-based DOM block scoring (query-agnostic)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

from chromerag.models import BlockScore
from chromerag.treestats import TreeStats

NOISE_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "template",
}

STRIP_TAGS = {
    "nav",
    "footer",
    "header",
    "aside",
    "menu",
}

NOISE_ID_CLASS_RE = re.compile(
    r"(cookie|consent|newsletter|subscribe|social-share|share-bar|"
    r"related-products|sidebar-nav|breadcrumb|pagination|"
    r"cookie-banner|promo-banner|chat-widget|advert|ads-|"
    r"global-header|global-footer|m-global-header|site-footer|"
    r"cookie-settings|privacy-banner)",
    re.I,
)

# Exact class/id tokens treated as chrome (avoid substring traps like "subnav").
NOISE_TOKENS = {
    "nav",
    "navbar",
    "navigation",
    "menu",
    "menubar",
    "footer",
    "header",
    "sidebar",
    "aside",
    "breadcrumb",
    "breadcrumbs",
    "cookie",
    "cookies",
    "consent",
    "promo",
    "banner",
    "modal",
    "popup",
    "newsletter",
    "subscribe",
    "social",
    "cta",
    "advert",
    "ads",
    "ad",
}


def _attr_tokens(tag: Tag) -> set[str]:
    tokens: set[str] = set()
    if not getattr(tag, "attrs", None):
        return tokens
    for key in ("id", "class", "role", "aria-label"):
        val = tag.get(key)
        if not val:
            continue
        values = val if isinstance(val, list) else [val]
        for item in values:
            for part in re.split(r"[\s_\-:/]+", str(item).lower()):
                if part:
                    tokens.add(part)
    return tokens


def _attrs_blob(tag: Tag) -> str:
    if not getattr(tag, "attrs", None):
        return ""
    bits: list[str] = []
    for key in ("id", "class", "role", "aria-label"):
        val = tag.get(key)
        if not val:
            continue
        if isinstance(val, list):
            bits.extend(str(v) for v in val)
        else:
            bits.append(str(val))
    return " ".join(bits)


CONTENT_TAGS = {
    "article",
    "main",
    "section",
    "div",
    "p",
    "li",
    "td",
    "th",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "pre",
    "code",
    "blockquote",
    "table",
    "figure",
    "figcaption",
    "ul",
    "ol",
    "dl",
}


@dataclass
class DensityConfig:
    min_chars: int = 40
    max_link_density: float = 0.55
    min_text_density: float = 0.12
    prefer_main: bool = True


MAIN_LANDMARK_ATTRS = {"role": "main"}

# A chrome-looking container holding more than this share of the page's visible
# text is almost always a content wrapper (e.g. class="VPContent has-sidebar").
MAX_NOISE_PAGE_SHARE = 0.5
PROSE_MIN_PARAGRAPHS = 2
PROSE_MAX_LINK_DENSITY = 0.35


@dataclass
class ElementCache:
    """Per-extract cache of id/class token sets and attribute blobs, keyed by id(tag)."""

    tokens: dict[int, set[str]] = field(default_factory=dict)
    blobs: dict[int, str] = field(default_factory=dict)

    def attr_tokens(self, tag: Tag) -> set[str]:
        key = id(tag)
        if key not in self.tokens:
            self.tokens[key] = _attr_tokens(tag)
        return self.tokens[key]

    def attrs_blob(self, tag: Tag) -> str:
        key = id(tag)
        if key not in self.blobs:
            self.blobs[key] = _attrs_blob(tag)
        return self.blobs[key]


def looks_like_noise(
    tag: Tag,
    *,
    max_noise_block_chars: int = 4000,
    page_text_len: int | None = None,
    cache: ElementCache | None = None,
    stats: TreeStats | None = None,
) -> bool:
    """Heuristic chrome detector with size guards (avoid sticky-subnav disasters).

    ``stats`` (see ``treestats``) gives the same answers as live ``get_text``/``find`` calls
    without walking the subtree again.
    """
    if not isinstance(tag, Tag) or not tag.name:
        return False

    # Never treat the primary content landmark (or a wrapper around it) as chrome.
    if tag.name == "main" or (tag.get("role") or "").lower() == "main":
        return False
    if stats is not None:
        if stats.has_main(tag):
            return False
        text_len = stats.text_len(tag)
    else:
        if tag.find("main") or tag.find(attrs=MAIN_LANDMARK_ATTRS):
            return False
        text_len = len(tag.get_text(" ", strip=True))
    if page_text_len and text_len > MAX_NOISE_PAGE_SHARE * page_text_len:
        return False

    if tag.name in STRIP_TAGS:
        # Huge <header>/<nav> sometimes wraps real page content — keep those.
        return not (tag.name in {"header", "nav", "footer", "aside"} and text_len > 8000)

    # Running prose with few links is content, whatever the layout classes say
    # (class="col-sm-9 sidebar-first-only" is a grid column, not a sidebar).
    if (
        stats is not None
        and stats.long_paragraphs(tag) >= PROSE_MIN_PARAGRAPHS
        and stats.link_density(tag) < PROSE_MAX_LINK_DENSITY
    ):
        return False

    tokens = cache.attr_tokens(tag) if cache else _attr_tokens(tag)
    if tokens & NOISE_TOKENS:
        return text_len <= max_noise_block_chars
    blob = cache.attrs_blob(tag) if cache else _attrs_blob(tag)
    if blob and NOISE_ID_CLASS_RE.search(blob):
        return text_len <= max_noise_block_chars
    role = ""
    if getattr(tag, "attrs", None):
        role = (tag.get("role") or "").lower()
    if role in {"navigation", "banner", "complementary", "contentinfo", "search"}:
        return text_len < max_noise_block_chars
    return False


def link_density(tag: Tag, stats: TreeStats | None = None) -> float:
    if stats is not None:
        return stats.link_density(tag)
    text = tag.get_text(" ", strip=True)
    if not text:
        return 1.0
    link_text = " ".join(a.get_text(" ", strip=True) for a in tag.find_all("a"))
    return min(1.0, len(link_text) / max(1, len(text)))


def text_density(tag: Tag, stats: TreeStats | None = None) -> float:
    """Approx chars / serialized HTML length for the node."""
    if stats is not None:
        text_len, html_len = stats.text_nosep(tag), stats.html_len(tag)
    else:
        text_len, html_len = len(tag.get_text("", strip=True)), len(str(tag))
    if not html_len:
        return 0.0
    return text_len / max(1, html_len)


def parse_html(html: str) -> BeautifulSoup:
    """Parse only — keep scripts so JSON-LD can be harvested."""
    soup = BeautifulSoup(_drop_early_end_tags(html), "lxml")
    _adopt_trailing_content(soup)
    return soup


_END_TAG = re.compile(r"</(body|html)\s*>", re.I)


def _drop_early_end_tags(html: str) -> str:
    """Remove ``</body>``/``</html>`` that are followed by more page content.

    Depending on the libxml2 version, lxml either drops everything after an early ``</html>`` or
    keeps it outside ``<body>``. Taking the early end tags out gives the same tree everywhere.
    """
    matches = list(_END_TAG.finditer(html))
    if len(matches) < 3:  # a normal page has exactly one of each
        return html
    tail = html[matches[0].end() :]
    if len(re.sub(r"<[^>]*>|\s+", "", tail)) < 200:
        return html
    last = {m.group(1).lower(): m.start() for m in matches}
    keep = set(last.values())
    return _END_TAG.sub(lambda m: m.group(0) if m.start() in keep else "", html)


def _adopt_trailing_content(soup: BeautifulSoup) -> None:
    """Move content that lxml left after ``</html>`` into ``<body>``.

    A stray ``</body></html>`` in the middle of a page makes lxml keep the rest of the document
    as siblings of ``<html>``; without this the rest of the page would never be looked at.
    """
    html = soup.find("html")
    body = soup.body
    if not isinstance(html, Tag) or not isinstance(body, Tag):
        return
    for node in list(soup.children):
        if node is html:
            continue
        if isinstance(node, Tag) or (isinstance(node, NavigableString) and node.strip() and type(node) is NavigableString):
            body.append(node.extract())


# Tags that normally hold a few words but that an unclosed tag or a page-wide <form> can turn
# into the parent of the whole article (ASP.NET forms, unclosed <button>, <noscript> in <head>).
_WRAPPER_TAGS = frozenset({"form", "button", "noscript"})
_WRAPPER_MIN_CHARS = 400
_WRAPPER_BLOCKS = ("p", "h1", "h2", "h3", "li", "article", "section", "div")


def _wraps_page_content(tag: Tag) -> bool:
    """True when a form/button/noscript holds article-sized text, so removing it would lose content."""
    text = tag.get_text(" ", strip=True)
    if len(text) < _WRAPPER_MIN_CHARS:
        return False
    if not tag.find(_WRAPPER_BLOCKS):
        return False
    return True


def strip_non_content_tags(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove script/style/etc. Call AFTER schema harvest.

    JSON-LD lives in <script type=\"application/ld+json\">. Once fuse_front_matter
    has copied that data into a dict, these tags are safe to drop.
    """
    for tag in soup.find_all(list(NOISE_TAGS)):
        if tag.attrs is None:  # inside a subtree removed earlier in this loop
            continue
        if tag.name in _WRAPPER_TAGS and _wraps_page_content(tag):
            tag.unwrap()
            continue
        tag.decompose()
    for comment in soup.find_all(
        string=lambda t: isinstance(t, NavigableString) and t.__class__.__name__ == "Comment"
    ):
        comment.extract()
    return soup


def clean_soup(html: str) -> BeautifulSoup:
    """Backward-compatible helper: parse + strip (no schema harvest)."""
    return strip_non_content_tags(parse_html(html))


def candidate_blocks(
    soup: BeautifulSoup,
    cfg: DensityConfig | None = None,
    *,
    cache: ElementCache | None = None,
    content_root: Tag | None = None,
    stats: TreeStats | None = None,
) -> list[Tag]:
    cfg = cfg or DensityConfig()
    root: Tag | BeautifulSoup = soup
    if cfg.prefer_main:
        if content_root is not None:
            root = content_root
        else:
            main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})
            if main and isinstance(main, Tag):
                root = main

    blocks: list[Tag] = []
    for tag in root.find_all(True):
        if not isinstance(tag, Tag):
            continue
        name = tag.name
        if name in NOISE_TAGS:
            continue
        if looks_like_noise(tag, cache=cache, stats=stats):
            continue
        # Leaf-ish content containers: paragraphs, headings, list items, table rows, pre
        if name in _LEAF_BLOCK_TAGS or name == "tr":
            blocks.append(tag)
        elif name in {"div", "section"} and _is_shallow_text_block(tag, stats):
            blocks.append(tag)
    return blocks


_LEAF_BLOCK_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "blockquote", "figcaption"})
_SHALLOW_CHILD_TAGS = frozenset({"div", "section", "p", "ul", "ol", "table", "article"})


def _is_shallow_text_block(tag: Tag, stats: TreeStats | None = None) -> bool:
    """True if div/section has direct text and few nested block children."""
    child_blocks = 0
    for child in tag.children:
        if isinstance(child, Tag) and child.name in _SHALLOW_CHILD_TAGS:
            child_blocks += 1
            if child_blocks > 1:
                return False
    text_len = stats.text_len(tag) if stats is not None else len(tag.get_text(" ", strip=True))
    return text_len >= 40


def score_blocks(
    blocks: list[Tag],
    cfg: DensityConfig | None = None,
    *,
    cache: ElementCache | None = None,
    stats: TreeStats | None = None,
) -> list[BlockScore]:
    cfg = cfg or DensityConfig()
    scored: list[BlockScore] = []
    for tag in blocks:
        text = tag.get_text(" ", strip=True)
        ld = link_density(tag, stats)
        keep = True
        reason = "ok"
        td = -1.0  # not computed: only div/section that pass the earlier checks need it
        if len(text) < cfg.min_chars and tag.name not in {"h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            keep = False
            reason = "too_short"
        elif ld > cfg.max_link_density and tag.name not in {"tr", "table"}:
            keep = False
            reason = "high_link_density"
        elif tag.name in {"div", "section"}:
            td = text_density(tag, stats)
            if td < cfg.min_text_density:
                keep = False
                reason = "low_text_density"
        scored.append(
            BlockScore(
                text=text,
                tag=tag.name or "div",
                link_density=ld,
                text_density=td,
                keep=keep,
                reason=reason,
            )
        )
    return scored


def prune_noise_subtrees(
    soup: BeautifulSoup,
    *,
    max_noise_block_chars: int = 4000,
    cache: ElementCache | None = None,
    stats: TreeStats | None = None,
) -> BeautifulSoup:
    """In-place remove obvious chrome before conversion.

    Tags are visited in document order (ancestors first) and only the visited tag is removed,
    so ``stats`` computed before the loop stays exact for every tag still to be visited.
    """
    body = soup.body or soup
    stats = stats or TreeStats(body)
    page_text_len = stats.text_len(body)
    for tag in list(body.find_all(True)):
        if not isinstance(tag, Tag) or getattr(tag, "attrs", None) is None:
            continue
        if looks_like_noise(
            tag,
            max_noise_block_chars=max_noise_block_chars,
            page_text_len=page_text_len,
            cache=cache,
            stats=stats,
        ):
            tag.decompose()
    return soup
