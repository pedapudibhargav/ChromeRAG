"""Structural + density-based DOM block scoring (query-agnostic)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

from chromerag.models import BlockScore

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


def looks_like_noise(
    tag: Tag,
    *,
    max_noise_block_chars: int = 4000,
    page_text_len: int | None = None,
) -> bool:
    """Heuristic chrome detector with size guards (avoid sticky-subnav disasters)."""
    if not isinstance(tag, Tag) or not tag.name:
        return False
    text_len = len(tag.get_text(" ", strip=True))

    # Never treat the primary content landmark (or a wrapper around it) as chrome.
    if tag.name == "main" or (tag.get("role") or "").lower() == "main":
        return False
    if tag.find("main") or tag.find(attrs=MAIN_LANDMARK_ATTRS):
        return False
    if page_text_len and text_len > MAX_NOISE_PAGE_SHARE * page_text_len:
        return False

    if tag.name in STRIP_TAGS:
        # Huge <header>/<nav> sometimes wraps real page content — keep those.
        if tag.name in {"header", "nav", "footer", "aside"} and text_len > 8000:
            return False
        return True

    tokens = _attr_tokens(tag)
    if tokens & NOISE_TOKENS:
        if text_len > max_noise_block_chars:
            return False
        return True

    blob = _attrs_blob(tag)
    if blob and NOISE_ID_CLASS_RE.search(blob):
        if text_len > max_noise_block_chars:
            return False
        return True

    role = ""
    if getattr(tag, "attrs", None):
        role = (tag.get("role") or "").lower()
    if role in {"navigation", "banner", "complementary", "contentinfo", "search"}:
        return text_len < max_noise_block_chars
    return False


def link_density(tag: Tag) -> float:
    text = tag.get_text(" ", strip=True)
    if not text:
        return 1.0
    link_text = " ".join(a.get_text(" ", strip=True) for a in tag.find_all("a"))
    return min(1.0, len(link_text) / max(1, len(text)))


def text_density(tag: Tag) -> float:
    """Approx chars / serialized HTML length for the node."""
    text = tag.get_text("", strip=True)
    html = str(tag)
    if not html:
        return 0.0
    return len(text) / max(1, len(html))


def parse_html(html: str) -> BeautifulSoup:
    """Parse only — keep scripts so JSON-LD can be harvested."""
    return BeautifulSoup(html, "lxml")


def strip_non_content_tags(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove script/style/etc. Call AFTER schema harvest.

    JSON-LD lives in <script type=\"application/ld+json\">. Once fuse_front_matter
    has copied that data into a dict, these tags are safe to drop.
    """
    for tag in soup.find_all(list(NOISE_TAGS)):
        tag.decompose()
    for comment in soup.find_all(
        string=lambda t: isinstance(t, NavigableString) and t.__class__.__name__ == "Comment"
    ):
        comment.extract()
    return soup


def clean_soup(html: str) -> BeautifulSoup:
    """Backward-compatible helper: parse + strip (no schema harvest)."""
    return strip_non_content_tags(parse_html(html))


def candidate_blocks(soup: BeautifulSoup, cfg: DensityConfig | None = None) -> list[Tag]:
    cfg = cfg or DensityConfig()
    root: Tag | BeautifulSoup = soup
    if cfg.prefer_main:
        main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})
        if main and isinstance(main, Tag):
            root = main

    blocks: list[Tag] = []
    for tag in root.find_all(True):
        if not isinstance(tag, Tag):
            continue
        if tag.name in NOISE_TAGS:
            continue
        if looks_like_noise(tag):
            continue
        # Leaf-ish content containers: paragraphs, headings, list items, table rows, pre
        if tag.name in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "blockquote", "figcaption"}:
            blocks.append(tag)
        elif tag.name == "tr":
            blocks.append(tag)
        elif tag.name in {"div", "section"} and _is_shallow_text_block(tag):
            blocks.append(tag)
    return blocks


def _is_shallow_text_block(tag: Tag) -> bool:
    """True if div/section has direct text and few nested block children."""
    child_blocks = [
        c
        for c in tag.children
        if isinstance(c, Tag) and c.name in {"div", "section", "p", "ul", "ol", "table", "article"}
    ]
    text = tag.get_text(" ", strip=True)
    return len(text) >= 40 and len(child_blocks) <= 1


def score_blocks(blocks: list[Tag], cfg: DensityConfig | None = None) -> list[BlockScore]:
    cfg = cfg or DensityConfig()
    scored: list[BlockScore] = []
    for tag in blocks:
        text = tag.get_text(" ", strip=True)
        ld = link_density(tag)
        td = text_density(tag)
        keep = True
        reason = "ok"
        if len(text) < cfg.min_chars and tag.name not in {"h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            keep = False
            reason = "too_short"
        elif ld > cfg.max_link_density and tag.name not in {"tr", "table"}:
            keep = False
            reason = "high_link_density"
        elif td < cfg.min_text_density and tag.name in {"div", "section"}:
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
) -> BeautifulSoup:
    """In-place remove obvious chrome before conversion."""
    body = soup.body or soup
    page_text_len = len(body.get_text(" ", strip=True))
    for tag in list(body.find_all(True)):
        if not isinstance(tag, Tag) or getattr(tag, "attrs", None) is None:
            continue
        if looks_like_noise(
            tag,
            max_noise_block_chars=max_noise_block_chars,
            page_text_len=page_text_len,
        ):
            tag.decompose()
    return soup
