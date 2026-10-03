"""Generic structural chrome removal (TOC, pager, comments, related, placeholders)."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from chromerag.config import PipelineConfig
from chromerag.domutil import all_tags, tags_named
from chromerag.schema_fusion import parse_json_ld, parse_microdata
from chromerag.treestats import TreeStats

_TOC_LABELS = frozenset(
    {
        "table of contents",
        "contents",
        "on this page",
        "in this article",
        "jump to",
        "outline",
    }
)
_TOC_LIST_TAGS = frozenset({"ul", "ol", "nav"})
_FRAGMENT_HREF = re.compile(r"^#[^#]+$")

_PAGER_LINK = re.compile(
    r"^(previous|next|older|newer|back|forward|prev\.?|"
    r"go to next lesson|next page|previous page|next\s+»|«\s+prev)\b",
    re.I,
)
_PAGER_CLASS = re.compile(r"pagination|pager|prev[-_]?next", re.I)

_ARTICLE_TYPES = frozenset({"Article", "NewsArticle", "BlogPosting", "TechArticle"})
_FORUM_TYPES = frozenset(
    {"DiscussionForumPosting", "QAPage", "Question", "Answer", "Comment"}
)
_COMMENT_TOKENS = frozenset(
    {
        "comments",
        "comment-list",
        "commentlist",
        "disqus_thread",
        "respond",
        "comment-respond",
    }
)

_RELATED_HEADING = re.compile(
    r"^(related( posts| articles| stories| reading)?|"
    r"you (may|might) also like|more from|read next|read more|"
    r"recommended|popular posts|latest posts|keep reading)\b",
    re.I,
)

_PLACEHOLDER_ONLY = re.compile(
    r"^(\$\{[^}]+\}|\{\{[^}]+\}\}|\{%[^%]+%\}|__\w+__|#\{[^}]+\})\s*$"
)
_PLACEHOLDER_TOKEN = re.compile(
    r"\$\{[^}]+\}|\{\{[^}]+\}\}|\{%[^%]+%\}|__\w+__|#\{[^}]+\}"
)

_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_LEAF_TEXT_TAGS = frozenset({"p", "li", "div"})
_MICRO_LEAF_TAGS = frozenset({"p", "li", "div", "span"})
_CONTENT_BLOCK_TAGS = frozenset(
    {
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "pre",
        "table",
        "blockquote",
    }
)
_FOOTERISH = re.compile(
    r"(?:copyright|©|all rights reserved|privacy policy|terms of (?:use|service)|"
    r"posted in|tags?:|filed under|\bshare\b|\brelated\b|"
    r"\b\d+\s*(?:min(?:ute)?s?)\s+read\b|"
    r"^(?:disclaimer|this article is for informational purposes))",
    re.I,
)
_FOOTER_ZONE_HEADING = re.compile(
    r"^(?:more on (?:this )?topic|see .+ in action|ready to see|"
    r"you (?:may|might) also like|keep reading|popular posts|latest posts)\b",
    re.I,
)
_DATE_STAMP = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    re.I,
)
_MICRO_JUNK = re.compile(r"^[\d\W_]{1,6}$")
_FORUM_NOISE = frozenset(
    {
        "member",
        "moderator",
        "admin",
        "top contributor",
        "votes",
        "like",
        "reply",
        "report",
        "permalink",
    }
)
_ATTR_KV = re.compile(r"^\w[\w-]*=\S+$")
_DATA_ARIA = re.compile(r"^(?:data|aria)-[\w-]+", re.I)
_IMG_FILE = re.compile(r"\.(?:jpe?g|png|webp|svg)\b", re.I)
_CLASS_TOKEN = re.compile(r"^[a-z][\w-]*$")
_CTA_LEAF_TAGS = frozenset({"a", "button", "p", "li", "div"})
_CTA_PHRASE = re.compile(
    r"^(sign up|subscribe|get started|contact us|learn more|read more|"
    r"get a quote|book(?: your)?(?: move| now)?|request a demo|download|"
    r"buy now|shop now|add to cart|call now|free trial|log in|register|"
    r"donate|write a review|see more|continue reading|reply)\s*[.!»]*$",
    re.I,
)
_SHARE_TOKENS = frozenset(
    {
        "facebook",
        "twitter",
        "x",
        "linkedin",
        "pinterest",
        "whatsapp",
        "email",
        "copy link",
        "print",
        "share",
        "tweet",
        "instagram",
        "reddit",
        "copy",
    }
)
_NEWSLETTER_TEXT = re.compile(r"\b(subscribe|newsletter|sign up for)\b", re.I)
_AUTHOR_MARKERS = re.compile(r"(?:^|[-_])(author|bio|byline-box|about-author)(?:$|[-_])", re.I)
_SKIP_TOP = re.compile(r"^(back to top|top of page|top|skip to\b)", re.I)
_LANG_CODE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$", re.I)
_KNOWN_LANGS = frozenset(
    {
        "english",
        "español",
        "spanish",
        "français",
        "french",
        "deutsch",
        "german",
        "italiano",
        "italian",
        "português",
        "portuguese",
        "中文",
        "日本語",
        "한국어",
        "nederlands",
        "dutch",
        "polski",
        "polish",
        "русский",
        "russian",
        "العربية",
        "arabic",
        "हिन्दी",
        "hindi",
    }
)


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text.lower()))


def _alive(tag: Tag) -> bool:
    return isinstance(tag, Tag) and tag.parent is not None and getattr(tag, "attrs", None) is not None


def _class_id_tokens(tag: Tag) -> set[str]:
    out: set[str] = set()
    ident = tag.get("id")
    if ident:
        out.add(str(ident).lower())
    cls = tag.get("class") or []
    if isinstance(cls, str):
        cls = cls.split()
    for c in cls:
        out.add(str(c).lower())
    return out


def _schema_types(soup: BeautifulSoup) -> set[str]:
    types: set[str] = set()
    for node in parse_json_ld(soup):
        t = node.get("@type") or node.get("type") or ""
        if isinstance(t, list):
            types.update(str(x).rstrip("/").split("/")[-1] for x in t)
        elif t:
            types.add(str(t).rstrip("/").split("/")[-1])
    for node in parse_microdata(soup):
        t = node.get("@type") or node.get("type") or ""
        if t:
            types.add(str(t).rstrip("/").split("/")[-1])
    for el in soup.find_all(attrs={"itemtype": True}):
        if not isinstance(el, Tag):
            continue
        it = el.get("itemtype") or ""
        types.add(str(it).rstrip("/").split("/")[-1])
    return types


def infer_page_kind_hint(soup: BeautifulSoup) -> str | None:
    """Coarse page kind for comment/pager guards (forum vs article)."""
    types = _schema_types(soup)
    if types & _FORUM_TYPES:
        return "forum"
    articles = [t for t in soup.find_all("article") if isinstance(t, Tag)]
    if len(articles) == 1 and articles[0].find("h1") is not None:
        if types & _ARTICLE_TYPES:
            return "article"
        return "article"
    if types & _ARTICLE_TYPES:
        return "article"
    return None


def _looks_like_article(soup: BeautifulSoup, page_kind_hint: str | None) -> bool:
    if page_kind_hint == "forum":
        return False
    types = _schema_types(soup)
    if types & _FORUM_TYPES:
        return False
    if types & _ARTICLE_TYPES:
        return True
    articles = [t for t in soup.find_all("article") if isinstance(t, Tag)]
    return len(articles) == 1 and articles[0].find("h1") is not None


def _list_items(tag: Tag) -> list[Tag]:
    if tag.name == "nav":
        items = tag.find_all("li")
        return [li for li in items if isinstance(li, Tag)]
    if tag.name in {"ul", "ol"}:
        return [li for li in tag.find_all("li", recursive=False) if isinstance(li, Tag)]
    return []


def _is_fragment_toc_list(tag: Tag, stats: TreeStats, root_words: int) -> bool:
    if tag.name not in _TOC_LIST_TAGS:
        return False
    items = _list_items(tag)
    if len(items) < 5:
        return False
    frag = 0
    list_text = stats.text_len(tag)
    if list_text <= 0:
        return False
    if root_words > 0 and _word_count(tag.get_text(" ", strip=True)) > 0.35 * root_words:
        return False
    outside = 0
    for li in items:
        anchors = [a for a in li.find_all("a", href=True) if isinstance(a, Tag)]
        frag_hit = any(_FRAGMENT_HREF.match(str(a.get("href", "")).strip()) for a in anchors)
        if frag_hit:
            frag += 1
        li_text = stats.text_len(li)
        li_link = stats.link_len(li)
        outside += max(0, li_text - li_link)
    if frag < 0.7 * len(items):
        return False
    if outside >= 0.2 * max(1, list_text):
        return False
    return True


def _toc_label_sibling(tag: Tag) -> Tag | None:
    prev = tag.find_previous_sibling()
    if prev is None or not isinstance(prev, Tag):
        return None
    if prev.name in _HEADING_TAGS or prev.name in {"p", "span", "div", "label"}:
        text = prev.get_text(" ", strip=True).lower()
        if text in _TOC_LABELS or any(text == lab for lab in _TOC_LABELS):
            return prev
        if len(text) <= 40 and any(lab in text for lab in _TOC_LABELS):
            return prev
    return None


def _drop_toc(
    root: Tag, stats: TreeStats, root_words: int, counts: dict[str, int]
) -> None:
    for tag in list(tags_named(root, _TOC_LIST_TAGS)):
        if not _is_fragment_toc_list(tag, stats, root_words):
            continue
        label = _toc_label_sibling(tag)
        tag.decompose()
        counts["toc"] += 1
        if label is not None:
            label.decompose()


def _drop_orphan_toc_labels(root: Tag, counts: dict[str, int]) -> None:
    """A "table of contents" label whose list was removed earlier (by a rule) has nothing under it."""
    for tag in list(tags_named(root, _HEADING_TAGS | {"p", "span", "div", "label"})):
        if tag.get_text(" ", strip=True).lower() not in _TOC_LABELS or tag.find(["a", "ul", "ol"]):
            continue
        following = tag.find_next_sibling()
        if following is None or following.name in _HEADING_TAGS:
            tag.decompose()
            counts["toc"] += 1


def _in_content_tail(tag: Tag, root: Tag, stats: TreeStats) -> bool:
    """True when less than 15% of root text follows ``tag`` (outside its subtree)."""
    root_text = stats.text_len(root)
    if root_text <= 0:
        return True
    total_after = 0
    found = False
    for t in all_tags(root):
        if t is tag:
            found = True
            continue
        if not found or tag in t.parents:
            continue
        total_after += stats.text_len(t)
    return total_after / max(1, root_text) <= 0.15


def _is_pager(tag: Tag, stats: TreeStats, root: Tag) -> bool:
    if tag.name not in {"nav", "ul", "div"}:
        return False
    anchors = [a for a in tag.find_all("a") if isinstance(a, Tag)]
    if not anchors or len(anchors) > 3:
        return False
    total = stats.text_len(tag)
    if total >= 120:
        return False
    hits = 0
    for a in anchors:
        t = a.get_text(" ", strip=True)
        if _PAGER_LINK.match(t):
            hits += 1
    if hits == 0:
        return False
    aria = str(tag.get("aria-label") or "")
    cls = " ".join(tag.get("class") or [])
    iden = str(tag.get("id") or "")
    if _PAGER_CLASS.search(f"{aria} {cls} {iden}"):
        return True
    return _in_content_tail(tag, root, stats)


def _drop_pager(root: Tag, stats: TreeStats, counts: dict[str, int]) -> None:
    for tag in list(all_tags(root)):
        if tag.name not in {"nav", "ul", "div"}:
            continue
        if _is_pager(tag, stats, root):
            tag.decompose()
            counts["pager"] += 1


def _inside_comment_container(tag: Tag) -> bool:
    for parent in tag.parents:
        if not isinstance(parent, Tag):
            continue
        if _comment_match(parent):
            return True
    return False


def _primary_article_end_index(root: Tag, ordered: list[Tag]) -> int:
    articles = [t for t in root.find_all("article") if isinstance(t, Tag)]
    scope = articles[0] if len(articles) == 1 else (root.find("main") or root)
    if not isinstance(scope, Tag):
        return len(ordered) // 2
    content_tags: list[Tag] = []
    for tag in scope.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "table"]):
        if not isinstance(tag, Tag) or _inside_comment_container(tag):
            continue
        if _comment_match(tag):
            continue
        content_tags.append(tag)
    if content_tags:
        last = content_tags[-1]
        for i, t in enumerate(ordered):
            if t is last:
                return i
    return len(ordered) // 2


def _comment_match(tag: Tag) -> bool:
    tokens = _class_id_tokens(tag)
    if tokens & _COMMENT_TOKENS:
        return True
    for tok in tokens:
        if any(ct in tok for ct in _COMMENT_TOKENS):
            return True
    it = tag.get("itemtype") or ""
    if "Comment" in str(it):
        return True
    return False


def _drop_comments(
    soup: BeautifulSoup,
    root: Tag,
    page_kind_hint: str | None,
    counts: dict[str, int],
) -> None:
    if not _looks_like_article(soup, page_kind_hint):
        return
    ordered = all_tags(root)
    end_idx = _primary_article_end_index(root, ordered)
    for i, tag in enumerate(list(ordered)):
        if not _alive(tag) or i <= end_idx:
            continue
        if not _comment_match(tag):
            continue
        if tag.name not in {"section", "div", "aside", "ol", "ul", "nav"}:
            continue
        tag.decompose()
        counts["comments"] += 1


def _related_sibling(heading: Tag) -> Tag | None:
    sib = heading.find_next_sibling()
    while sib is not None:
        if isinstance(sib, Tag):
            if sib.name in {"ul", "ol", "div", "section", "nav"}:
                return sib
            if sib.name in _HEADING_TAGS:
                return None
        sib = sib.find_next_sibling()
    return None


def _drop_related(root: Tag, stats: TreeStats, root_words: int, counts: dict[str, int]) -> None:
    for tag in list(tags_named(root, _HEADING_TAGS)):
        if tag.name not in {"h2", "h3", "h4", "h5", "h6"}:
            continue
        text = tag.get_text(" ", strip=True)
        if not _RELATED_HEADING.match(text):
            continue
        sib = _related_sibling(tag)
        if sib is None:
            continue
        sib_text = stats.text_len(sib)
        if sib_text <= 0:
            continue
        if stats.link_len(sib) / max(1, sib_text) <= 0.6:
            continue
        drop_words = _word_count(tag.get_text(" ", strip=True)) + _word_count(
            sib.get_text(" ", strip=True)
        )
        if root_words > 0 and drop_words > 0.25 * root_words:
            continue
        tag.decompose()
        sib.decompose()
        counts["related"] += 1


def _is_leaf_text_block(tag: Tag) -> bool:
    if tag.name not in _LEAF_TEXT_TAGS:
        return False
    for child in tag.children:
        if isinstance(child, Tag):
            return False
    return True


def _contains_page_h1(tag: Tag, root: Tag) -> bool:
    h1 = root.find("h1")
    if h1 is None or not isinstance(h1, Tag):
        return False
    return h1 is tag or h1 in tag.descendants


def _has_long_paragraph(tag: Tag) -> bool:
    if tag.name == "p" and _word_count(tag.get_text(" ", strip=True)) >= 25:
        return True
    for p in tag.find_all("p"):
        if isinstance(p, Tag) and _word_count(p.get_text(" ", strip=True)) >= 25:
            return True
    return False


def _drop_budget_ok(drop_words: int, already_dropped: int, root_words: int) -> bool:
    if drop_words <= 0:
        return False
    if root_words <= 0:
        return already_dropped + drop_words <= 200
    return (already_dropped + drop_words) / root_words <= 0.20


def _try_decompose(
    tag: Tag,
    root: Tag,
    root_words: int,
    state: dict[str, int],
    counts: dict[str, int],
    key: str,
) -> bool:
    if not _alive(tag):
        return False
    if _contains_page_h1(tag, root):
        return False
    if _has_long_paragraph(tag):
        return False
    drop_words = _word_count(tag.get_text(" ", strip=True))
    if not _drop_budget_ok(drop_words, state["dropped"], root_words):
        return False
    tag.decompose()
    state["dropped"] += drop_words
    counts[key] += 1
    return True


def _is_cta_text(text: str) -> bool:
    text = text.strip()
    if not text or _word_count(text) > 6:
        return False
    return bool(_CTA_PHRASE.match(text))


def _alone_in_block(tag: Tag) -> bool:
    parent = tag.parent
    if not isinstance(parent, Tag):
        return False
    visible = 0
    for child in parent.children:
        if isinstance(child, Tag):
            visible += 1
        elif isinstance(child, NavigableString) and str(child).strip():
            visible += 1
    return visible <= 1


def _is_cta_block(tag: Tag) -> bool:
    if tag.name not in _CTA_LEAF_TAGS:
        return False
    text = tag.get_text(" ", strip=True)
    if not _is_cta_text(text):
        return False
    if tag.name in {"a", "button"}:
        return True
    if str(tag.get("role") or "").lower() == "button":
        return True
    return _alone_in_block(tag)


def _strip_share_token(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def _is_share_item(text: str) -> bool:
    cleaned = _strip_share_token(text)
    if not cleaned or _word_count(cleaned) > 3:
        return False
    if cleaned in _SHARE_TOKENS:
        return True
    return any(tok in cleaned.split() for tok in _SHARE_TOKENS if len(tok) > 2)


def _share_strip_items(tag: Tag) -> list[str]:
    if tag.name in {"ul", "ol", "nav"}:
        return [
            li.get_text(" ", strip=True)
            for li in tag.find_all("li", recursive=False)
            if isinstance(li, Tag) and li.get_text(strip=True)
        ]
    if tag.name == "div":
        texts: list[str] = []
        for child in tag.find_all(["a", "span", "li"], recursive=False):
            if isinstance(child, Tag):
                t = child.get_text(" ", strip=True)
                if t:
                    texts.append(t)
        if texts:
            return texts
        t = tag.get_text(" ", strip=True)
        return [t] if t else []
    return []


def _is_share_strip(tag: Tag) -> bool:
    if tag.name not in {"ul", "ol", "div", "nav"}:
        return False
    items = _share_strip_items(tag)
    if len(items) < 2:
        return False
    hits = sum(1 for item in items if _is_share_item(item))
    return hits >= max(2, int(0.7 * len(items)))


def _has_email_input(tag: Tag) -> bool:
    for inp in tag.find_all("input"):
        if not isinstance(inp, Tag):
            continue
        itype = str(inp.get("type") or "").lower()
        name = str(inp.get("name") or "").lower()
        if itype == "email" or "email" in name:
            return True
    return False


def _has_submit_control(tag: Tag) -> bool:
    for btn in tag.find_all(["button", "input"]):
        if not isinstance(btn, Tag):
            continue
        if btn.name == "button":
            return True
        if str(btn.get("type") or "").lower() in {"submit", "button"}:
            return True
    return False


def _is_newsletter_block(tag: Tag) -> bool:
    if tag.name not in {"form", "div", "section", "aside", "fieldset"}:
        return False
    scope = tag if tag.name == "form" else tag
    if _has_email_input(scope) and _has_submit_control(scope):
        return True
    text = scope.get_text(" ", strip=True)
    if not text or _word_count(text) > 60:
        return False
    return bool(_NEWSLETTER_TEXT.search(text))


def _author_marker(tag: Tag) -> bool:
    tokens = _class_id_tokens(tag)
    for tok in tokens:
        if _AUTHOR_MARKERS.search(tok):
            return True
    if str(tag.get("itemprop") or "").lower() == "author":
        return True
    for el in tag.find_all(attrs={"itemprop": True}):
        if str(el.get("itemprop") or "").lower() == "author":
            return True
    return False


def _is_author_bio(tag: Tag, root: Tag, stats: TreeStats) -> bool:
    if not _author_marker(tag):
        return False
    if not _in_content_tail(tag, root, stats):
        return False
    text = tag.get_text(" ", strip=True)
    if not text or _word_count(text) >= 80:
        return False
    if tag.find("h1") is not None:
        return False
    return True


def _is_back_to_top(tag: Tag) -> bool:
    if tag.name != "a":
        return False
    text = tag.get_text(" ", strip=True)
    if not text or _word_count(text) > 6:
        return False
    return bool(_SKIP_TOP.match(text))


def _is_language_label(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned or _word_count(cleaned) > 3:
        return False
    low = cleaned.lower()
    if _LANG_CODE.match(low):
        return True
    return low in _KNOWN_LANGS


def _is_language_switcher(tag: Tag) -> bool:
    if tag.name not in {"ul", "ol", "div", "nav"}:
        return False
    items = _share_strip_items(tag)
    if len(items) < 4:
        return False
    hits = sum(1 for item in items if _is_language_label(item))
    return hits >= 4


def _drop_cta(root: Tag, root_words: int, counts: dict[str, int]) -> None:
    state = {"dropped": 0}
    for tag in list(all_tags(root)):
        if not _alive(tag) or not _is_cta_block(tag):
            continue
        _try_decompose(tag, root, root_words, state, counts, "cta")


def _drop_share(root: Tag, root_words: int, counts: dict[str, int]) -> None:
    state = {"dropped": 0}
    for tag in list(all_tags(root)):
        if not _alive(tag) or not _is_share_strip(tag):
            continue
        _try_decompose(tag, root, root_words, state, counts, "share")


def _drop_newsletter(root: Tag, root_words: int, counts: dict[str, int]) -> None:
    state = {"dropped": 0}
    for tag in list(all_tags(root)):
        if not _alive(tag) or not _is_newsletter_block(tag):
            continue
        _try_decompose(tag, root, root_words, state, counts, "newsletter")


def _drop_author_bio(root: Tag, stats: TreeStats, root_words: int, counts: dict[str, int]) -> None:
    state = {"dropped": 0}
    for tag in list(all_tags(root)):
        if not _alive(tag) or not _is_author_bio(tag, root, stats):
            continue
        _try_decompose(tag, root, root_words, state, counts, "author_bio")


def _drop_nav_misc(root: Tag, root_words: int, counts: dict[str, int]) -> None:
    state = {"dropped": 0}
    for tag in list(all_tags(root)):
        if not _alive(tag):
            continue
        if _is_back_to_top(tag) or _is_language_switcher(tag):
            _try_decompose(tag, root, root_words, state, counts, "nav_misc")


def _inside_pre_table_code(tag: Tag) -> bool:
    for parent in tag.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in {"pre", "table", "code", "textarea"}:
            return True
    return False


def _outer_blocks(root: Tag) -> list[Tag]:
    blocks: list[Tag] = []
    for tag in all_tags(root):
        if tag.name not in _CONTENT_BLOCK_TAGS or _inside_pre_table_code(tag):
            continue
        if any(
            isinstance(p, Tag) and p is not root and p.name in _CONTENT_BLOCK_TAGS
            for p in tag.parents
        ):
            continue
        blocks.append(tag)
    return blocks


def _link_density(tag: Tag, stats: TreeStats) -> float:
    text = stats.text_len(tag)
    if text <= 0:
        return 0.0
    return stats.link_len(tag) / text


def _is_substantive_block(tag: Tag, blocks: list[Tag], idx: int) -> bool:
    if tag.name in {"pre", "table", "p", "ul", "ol", "blockquote"}:
        return _word_count(tag.get_text(" ", strip=True)) >= 25
    if tag.name in {"h2", "h3", "h4", "h5", "h6"}:
        for j in range(idx + 1, len(blocks)):
            nxt = blocks[j]
            if nxt.name in _HEADING_TAGS:
                break
            if nxt.name in {"pre", "table", "p", "ul", "ol", "blockquote"}:
                return _word_count(nxt.get_text(" ", strip=True)) >= 25
        return False
    return False


def _is_footerish_block(tag: Tag) -> bool:
    text = tag.get_text(" ", strip=True)
    if not text:
        return False
    low = text.lower()
    if _FOOTERISH.search(low):
        return True
    if _DATE_STAMP.search(text) and _word_count(text) <= 12:
        return True
    return False


def _is_trimmable_tail_block(tag: Tag, stats: TreeStats) -> bool:
    if tag.name in {"pre", "table"}:
        return False
    text = tag.get_text(" ", strip=True)
    if not text:
        return True
    words = _word_count(text)
    if words <= 12:
        return True
    if _link_density(tag, stats) > 0.5:
        return True
    return _is_footerish_block(tag)


def _footer_zone_start(blocks: list[Tag]) -> int | None:
    tail_start = max(0, int(0.75 * len(blocks)))
    for i in range(tail_start, len(blocks)):
        tag = blocks[i]
        if tag.name not in _HEADING_TAGS:
            continue
        text = tag.get_text(" ", strip=True)
        if (
            _RELATED_HEADING.match(text)
            or _FOOTER_ZONE_HEADING.match(text)
            or _FOOTERISH.search(text)
        ):
            return i
    return None


def _trim_tail(root: Tag, stats: TreeStats, counts: dict[str, int]) -> None:
    blocks = _outer_blocks(root)
    if not blocks:
        return
    substantive = [i for i, b in enumerate(blocks) if _is_substantive_block(b, blocks, i)]
    if len(substantive) < 3:
        return
    root_words = _word_count(root.get_text(" ", strip=True))
    if root_words <= 0:
        return
    max_drop_words = int(0.10 * root_words)
    dropped_words = 0
    to_drop: list[Tag] = []

    zone = _footer_zone_start(blocks)
    if zone is not None:
        substantive_before = sum(
            1 for i, b in enumerate(blocks[:zone]) if _is_substantive_block(b, blocks, i)
        )
        if substantive_before >= 3:
            zone_tags = [
                blocks[i]
                for i in range(zone, len(blocks))
                if _alive(blocks[i]) and blocks[i].name not in {"pre", "table"}
            ]
            if len(zone_tags) >= 2:
                for tag in zone_tags:
                    words = _word_count(tag.get_text(" ", strip=True))
                    if dropped_words + words > max_drop_words:
                        break
                    to_drop.append(tag)
                    dropped_words += words

    if len(to_drop) < 2:
        to_drop = []
        dropped_words = 0
        last_sub = substantive[-1]
        tail_candidates: list[Tag] = []
        for i in range(len(blocks) - 1, last_sub, -1):
            tag = blocks[i]
            if not _alive(tag):
                continue
            if tag.name in {"pre", "table"}:
                break
            text = tag.get_text(" ", strip=True)
            words = _word_count(text)
            if words >= 25 and _link_density(tag, stats) <= 0.5:
                break
            if not _is_trimmable_tail_block(tag, stats):
                break
            tail_candidates.append(tag)
        if len(tail_candidates) >= 2:
            for tag in tail_candidates:
                words = _word_count(tag.get_text(" ", strip=True))
                if dropped_words + words > max_drop_words:
                    break
                to_drop.append(tag)
                dropped_words += words

    for tag in to_drop:
        if _alive(tag):
            tag.decompose()
            counts["trim_tail"] += 1


def _is_micro_leaf(tag: Tag) -> bool:
    if tag.name not in _MICRO_LEAF_TAGS:
        return False
    if tag.name == "div":
        for child in tag.children:
            if isinstance(child, Tag) and child.name in _MICRO_LEAF_TAGS:
                return False
    for child in tag.children:
        if isinstance(child, Tag):
            return False
    return True


def _in_long_numbered_list(tag: Tag) -> bool:
    if tag.name != "li":
        return False
    parent = tag.parent
    if not isinstance(parent, Tag) or parent.name != "ol":
        return False
    items = [li for li in parent.find_all("li", recursive=False) if isinstance(li, Tag)]
    return len(items) >= 3


def _is_micro_block(tag: Tag) -> bool:
    if not _is_micro_leaf(tag) or _inside_pre_table_code(tag):
        return False
    if _in_long_numbered_list(tag):
        return False
    text = tag.get_text(" ", strip=True)
    if not text:
        return True
    if len(text) <= 2:
        return True
    if len(text) <= 6 and _MICRO_JUNK.match(text):
        return True
    if _word_count(text) <= 4:
        cleaned = re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()
        if cleaned in _FORUM_NOISE:
            return True
    return False


def _drop_micro_blocks(root: Tag, counts: dict[str, int]) -> None:
    for tag in list(all_tags(root)):
        if not _alive(tag) or not _is_micro_block(tag):
            continue
        tag.decompose()
        counts["micro_blocks"] += 1


def _has_repeated_word(text: str) -> bool:
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) < 4:
        return False
    run = 1
    for i in range(1, len(tokens)):
        if tokens[i] == tokens[i - 1]:
            run += 1
            if run >= 4:
                return True
        else:
            run = 1
    return False


def _is_attr_junk_token(tok: str) -> bool:
    if not tok:
        return False
    if _ATTR_KV.match(tok):
        return True
    if _DATA_ARIA.match(tok):
        return True
    if _IMG_FILE.search(tok):
        return True
    if _CLASS_TOKEN.match(tok) and "-" in tok and len(tok) >= 4:
        return True
    return False


def _is_attr_junk_block(tag: Tag) -> bool:
    if tag.name not in _LEAF_TEXT_TAGS | {"span"}:
        return False
    if not _is_micro_leaf(tag) or _inside_pre_table_code(tag):
        return False
    text = tag.get_text(" ", strip=True)
    if not text or _word_count(text) > 25:
        return False
    if _has_repeated_word(text):
        return True
    tokens = text.split()
    if not tokens:
        return False
    junk = sum(1 for t in tokens if _is_attr_junk_token(t))
    return junk / len(tokens) >= 0.6


def _drop_attr_junk(root: Tag, counts: dict[str, int]) -> None:
    for tag in list(all_tags(root)):
        if not _alive(tag) or not _is_attr_junk_block(tag):
            continue
        tag.decompose()
        counts["attr_junk"] += 1


def _drop_placeholders(root: Tag, counts: dict[str, int]) -> None:
    for tag in list(all_tags(root)):
        if not _is_leaf_text_block(tag):
            continue
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if _PLACEHOLDER_ONLY.match(text):
            tag.decompose()
            counts["placeholder"] += 1
            continue
        if len(text) < 80 and _PLACEHOLDER_TOKEN.search(text):
            new_parts: list[Any] = []
            changed = False
            for child in list(tag.children):
                if isinstance(child, NavigableString):
                    cleaned = _PLACEHOLDER_TOKEN.sub("", str(child)).strip()
                    if cleaned != str(child).strip():
                        changed = True
                    if cleaned:
                        new_parts.append(cleaned)
                else:
                    new_parts.append(child)
            if changed:
                tag.clear()
                for part in new_parts:
                    tag.append(part if isinstance(part, Tag) else NavigableString(part))
                counts["placeholder"] += 1
                if not tag.get_text(strip=True):
                    tag.decompose()


def drop_generic_chrome(
    soup: BeautifulSoup,
    content_root: Tag | None,
    page_kind_hint: str | None,
    *,
    cfg: PipelineConfig,
) -> dict[str, int]:
    """Remove generic in-page chrome; returns per-rule drop counts."""
    counts = {
        "toc": 0,
        "pager": 0,
        "comments": 0,
        "related": 0,
        "placeholder": 0,
        "cta": 0,
        "share": 0,
        "newsletter": 0,
        "author_bio": 0,
        "nav_misc": 0,
        "trim_tail": 0,
        "micro_blocks": 0,
        "attr_junk": 0,
    }
    root = content_root if isinstance(content_root, Tag) else soup.body
    if root is None or not isinstance(root, Tag):
        return counts

    stats = TreeStats(root)
    root_words = _word_count(root.get_text(" ", strip=True))

    if cfg.chrome_drop_toc:
        _drop_toc(root, stats, root_words, counts)
        _drop_orphan_toc_labels(root, counts)
        stats = TreeStats(root)
        root_words = _word_count(root.get_text(" ", strip=True))

    if cfg.chrome_drop_pager:
        _drop_pager(root, stats, counts)
        stats = TreeStats(root)

    if cfg.chrome_drop_comments:
        _drop_comments(soup, root, page_kind_hint, counts)
        stats = TreeStats(root)

    if cfg.chrome_drop_related:
        root_words = _word_count(root.get_text(" ", strip=True))
        _drop_related(root, stats, root_words, counts)
        stats = TreeStats(root)

    if cfg.chrome_drop_cta:
        _drop_cta(root, root_words, counts)
        stats = TreeStats(root)
        root_words = _word_count(root.get_text(" ", strip=True))

    if cfg.chrome_drop_share:
        _drop_share(root, root_words, counts)
        stats = TreeStats(root)
        root_words = _word_count(root.get_text(" ", strip=True))

    if cfg.chrome_drop_newsletter:
        _drop_newsletter(root, root_words, counts)
        stats = TreeStats(root)
        root_words = _word_count(root.get_text(" ", strip=True))

    if cfg.chrome_drop_author_bio:
        _drop_author_bio(root, stats, root_words, counts)
        stats = TreeStats(root)
        root_words = _word_count(root.get_text(" ", strip=True))

    if cfg.chrome_drop_nav_misc:
        _drop_nav_misc(root, root_words, counts)

    if cfg.chrome_trim_tail:
        _trim_tail(root, stats, counts)
        stats = TreeStats(root)
        root_words = _word_count(root.get_text(" ", strip=True))

    if cfg.chrome_drop_micro_blocks:
        _drop_micro_blocks(root, counts)
        stats = TreeStats(root)

    if cfg.chrome_drop_attr_junk:
        _drop_attr_junk(root, counts)

    _drop_placeholders(root, counts)
    return counts
