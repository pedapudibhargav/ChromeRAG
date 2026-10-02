"""Text blocks of a cleaned page and the numbers a block classifier needs.

A *block* is the smallest piece of the page that the Markdown writer emits as one unit: a
paragraph, a heading, a list item, a preformatted block, a quote, a data table, or a ``div`` that
carries its own text. ``find_blocks`` lists them in document order; ``block_features`` describes
each one with a fixed-length vector (see ``FEATURE_NAMES``) that depends only on the page itself:
the block's text, where it sits in the tree, what its ancestors are called, and its neighbours.
"""

from __future__ import annotations

import math
import re
import zlib
from dataclasses import dataclass

import numpy as np
from bs4 import Tag

from chromerag.treestats import TreeStats

_HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_LEAF_TAGS = frozenset({"p", *_HEADINGS, "li", "pre", "blockquote", "figcaption", "dt", "dd", "table"})
_CONTAINER_TAGS = frozenset({"div", "section", "article", "span"})
_TAG_GROUPS = ("p", "h1", "h2", "h3", "h456", "li", "pre", "blockquote", "div", "figcaption", "table", "other")
_ANCESTOR_FLAGS = ("main", "article", "header", "footer", "aside", "form", "ul", "ol", "blockquote", "section", "nav")

N_CLASS_BUCKETS = 192
N_TEXT_BUCKETS = 64
MAX_ANCESTORS = 8

_STOPWORDS = frozenset(
    "the of and to in a is that for it as with was on be by this are at from or an have not but they his her "
    "you we can all will their has more one if there been which when who would what about so out up your "
    "were than into them its our also only other some these may do how new".split()
)
_CHROME_WORDS = frozenset(
    "cookie cookies privacy subscribe newsletter copyright reserved share follow comment comments reply login "
    "signup sign register posted tags tag related menu search home contact terms policy facebook twitter "
    "linkedin instagram pinterest youtube email print advertisement sponsored read more click here "
    "download app cart checkout wishlist shipping returns account".split()
)
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_SENTENCE_END = re.compile(r"[.!?]['\")\]]?(\s|$)")
_DATEISH = re.compile(
    r"\b(\d{1,2}[:/.\-]\d{1,2}([:/.\-]\d{2,4})?|jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|june?|july?|"
    r"aug(ust)?|sep(t(ember)?)?|oct(ober)?|nov(ember)?|dec(ember)?)\b",
    re.I,
)
_SPLIT_NAME = re.compile(r"[^a-z]+")

_NUMERIC = (
    "log_chars", "log_words", "link_density", "n_links", "avg_word_len", "upper_frac", "digit_frac",
    "punct_frac", "ends_sentence", "n_sentences", "commas_per_word", "stopword_frac", "all_caps",
    "starts_capital", "has_separator", "dateish", "name_like", "ends_colon", "emphasis_frac", "chrome_word_frac",
    "idx_frac", "chars_before_frac", "chars_after_frac", "log_n_blocks", "log_page_chars",
    "dist_prev_heading", "seen_h1", "before_first_h1", "in_root", "depth",
    *(f"in_{f}" for f in _ANCESTOR_FLAGS),
    "box_link_density", "box_log_chars", "box_long_p", "box_blocks", "unit_share_of_box", "box_share_of_page",
    "box2_link_density", "box2_log_chars", "box2_long_p",
    "prev_log_chars", "prev_link_density", "next_log_chars", "next_link_density", "prev_same_box", "next_same_box",
    "same_tag_siblings", "pos_in_parent", "dup_count", "dup_earlier", "len_rel_page", "box_mean_chars",
    "title_overlap", "desc_overlap", "topic_overlap", "topic_overlap_strong",
)
FEATURE_NAMES: tuple[str, ...] = (
    *(f"tag_{g}" for g in _TAG_GROUPS),
    *_NUMERIC,
    *(f"cls_{i}" for i in range(N_CLASS_BUCKETS)),
    *(f"txt_{i}" for i in range(N_TEXT_BUCKETS)),
)
N_FEATURES = len(FEATURE_NAMES)
_IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}
_CLS0 = _IDX["cls_0"]
_TXT0 = _IDX["txt_0"]


@dataclass
class Block:
    tag: Tag
    text: str


def _tag_group(name: str) -> str:
    if name in ("h4", "h5", "h6"):
        return "h456"
    if name in ("div", "section", "article", "span"):
        return "div"
    return name if name in _TAG_GROUPS else "other"


_NESTED_BLOCKS = ("div", "section", "article", "p", "ul", "ol", "li", "table", "pre", "blockquote", "dl", "form",
                  *_HEADINGS)


def _is_text_container(tag: Tag, stats: TreeStats) -> bool:
    """A div/section/span that holds only inline content (its own text), no nested blocks."""
    return stats.text_len(tag) >= 20 and tag.find(_NESTED_BLOCKS) is None


def find_blocks(body: Tag, stats: TreeStats) -> list[Block]:
    """Blocks of ``body`` in document order. A block is never listed together with one inside it."""
    blocks: list[Block] = []

    def walk(node: Tag) -> None:
        for child in node.children:
            if not isinstance(child, Tag):
                continue
            name = child.name
            take = False
            if name in _LEAF_TAGS:
                take = not (name == "li" and child.find("li")) and not (
                    name in ("p", "blockquote", "li") and child.find("table")
                )
            elif name in _CONTAINER_TAGS and _is_text_container(child, stats):
                take = True
            if take:
                text = child.get_text(" ", strip=True)
                if text:
                    blocks.append(Block(child, text))
                continue
            walk(child)

    walk(body)
    return blocks


def _bucket(word: str, n: int) -> int:
    return zlib.crc32(word.encode("utf-8")) % n


def _name_words(tag: Tag) -> list[str]:
    words: list[str] = []
    values = [str(c) for c in tag.get("class") or []] + [str(tag.get("id") or "")]
    for value in values:
        for part in _SPLIT_NAME.split(value.lower()):
            if len(part) > 2:
                words.append(part)
    return words


def _text_features(text: str) -> dict[str, float]:
    chars = len(text)
    words = _WORD.findall(text)
    n_words = max(1, len(words))
    low = [w.lower() for w in words]
    alpha = max(1, sum(1 for c in text if c.isalpha()))
    capitalised = sum(1 for w in words if w[0].isupper())
    return {
        "log_chars": math.log1p(chars),
        "log_words": math.log1p(len(words)),
        "avg_word_len": sum(len(w) for w in words) / n_words,
        "upper_frac": sum(1 for c in text if c.isupper()) / alpha,
        "digit_frac": sum(1 for c in text if c.isdigit()) / max(1, chars),
        "punct_frac": sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(1, chars),
        "ends_sentence": 1.0 if text.rstrip()[-1:] in ".!?\"'”’)" else 0.0,
        "n_sentences": float(min(10, len(_SENTENCE_END.findall(text)))),
        "commas_per_word": text.count(",") / n_words,
        "stopword_frac": sum(1 for w in low if w in _STOPWORDS) / n_words,
        "all_caps": 1.0 if text.upper() == text and any(c.isalpha() for c in text) else 0.0,
        "starts_capital": 1.0 if text[:1].isupper() else 0.0,
        "has_separator": 1.0 if any(sep in text for sep in ("|", "•", "»", "·", "©")) else 0.0,
        "dateish": 1.0 if _DATEISH.search(text) else 0.0,
        "name_like": 1.0 if len(words) <= 4 and capitalised == len(words) else 0.0,
        "ends_colon": 1.0 if text.rstrip().endswith(":") else 0.0,
        "chrome_word_frac": sum(1 for w in low if w in _CHROME_WORDS) / n_words,
    }


def block_features(
    blocks: list[Block], body: Tag, stats: TreeStats, root: Tag | None
) -> tuple[np.ndarray, np.ndarray]:
    """Feature matrix (len(blocks), N_FEATURES) and, per block, the id of its box (-1: none).

    Blocks with the same box id share their nearest ancestor that holds at least two blocks.
    """
    n = len(blocks)
    out = np.zeros((n, N_FEATURES), dtype=np.float32)
    if n == 0:
        return out, np.zeros(0, dtype=np.int32)
    page_chars = max(1, stats.text_len(body))
    chars = [len(b.text) for b in blocks]
    total_chars = max(1, sum(chars))
    cum = np.cumsum([0, *chars])
    link_dens = [stats.link_density(b.tag) for b in blocks]

    root_ids: set[int] | None = None
    if root is not None and root is not body:
        root_ids = {id(root)} | {id(t) for t in root.find_all(True)}

    top = body.parent
    box_blocks: dict[int, int] = {}
    for b in blocks:
        for parent in b.tag.parents:
            if parent is top:
                break
            box_blocks[id(parent)] = box_blocks.get(id(parent), 0) + 1

    html = body.parent
    title_words: set[str] = set()
    desc_words: set[str] = set()
    if isinstance(html, Tag):
        for t in html.find_all(["title", "h1"]):
            title_words.update(w for w in _WORD.findall(t.get_text(" ", strip=True).lower()) if w not in _STOPWORDS)
        for m in html.find_all("meta"):
            if str(m.get("name") or m.get("property") or "").lower() in ("description", "og:description", "og:title"):
                desc_words.update(
                    w for w in _WORD.findall(str(m.get("content") or "").lower()) if w not in _STOPWORDS
                )
    block_words = [{w for w in _WORD.findall(b.text.lower()) if w not in _STOPWORDS} for b in blocks]
    long_df: dict[str, int] = {}
    for ws, c in zip(block_words, chars, strict=True):
        if c >= 200:
            for w in ws:
                long_df[w] = long_df.get(w, 0) + 1
    keys = [" ".join(b.text.lower().split()) for b in blocks]
    key_count: dict[str, int] = {}
    for k in keys:
        key_count[k] = key_count.get(k, 0) + 1
    seen_keys: set[str] = set()
    median_chars = float(np.median(chars)) if chars else 1.0
    first_h1 = next((i for i, b in enumerate(blocks) if b.tag.name == "h1"), -1)
    seen_h1 = 0.0
    last_heading = -1
    box_of: list[Tag | None] = []

    for i, block in enumerate(blocks):
        tag = block.tag
        row = out[i]
        row[_IDX["tag_" + _tag_group(tag.name)]] = 1.0
        for name, value in _text_features(block.text).items():
            row[_IDX[name]] = value
        emph = sum(len(e.get_text(" ", strip=True)) for e in tag.find_all(("strong", "b", "em", "i")))
        row[_IDX["link_density"]] = link_dens[i]
        row[_IDX["n_links"]] = float(min(50, len(tag.find_all("a"))))
        row[_IDX["emphasis_frac"]] = min(1.0, emph / max(1, chars[i]))
        row[_IDX["idx_frac"]] = i / max(1, n - 1)
        row[_IDX["chars_before_frac"]] = cum[i] / total_chars
        row[_IDX["chars_after_frac"]] = (cum[n] - cum[i + 1]) / total_chars
        row[_IDX["log_n_blocks"]] = math.log1p(n)
        row[_IDX["log_page_chars"]] = math.log1p(page_chars)
        if tag.name in _HEADINGS:
            last_heading = i
        row[_IDX["dist_prev_heading"]] = math.log1p(i - last_heading) if last_heading >= 0 else math.log1p(n)
        if tag.name == "h1":
            seen_h1 = 1.0
        row[_IDX["seen_h1"]] = seen_h1
        row[_IDX["before_first_h1"]] = 1.0 if first_h1 >= 0 and i < first_h1 else 0.0
        row[_IDX["in_root"]] = 1.0 if (root_ids is None or id(tag) in root_ids) else 0.0

        depth = 0
        flags: set[str] = set()
        boxes: list[Tag] = []
        words = _name_words(tag)
        named = 0
        for parent in tag.parents:
            if parent is top:
                break
            depth += 1
            pname = parent.name
            if pname in _ANCESTOR_FLAGS:
                flags.add(pname)
            if pname in ("body", "html"):
                continue
            if named < MAX_ANCESTORS:
                words.extend(_name_words(parent))
                named += 1
            if len(boxes) < 2 and box_blocks.get(id(parent), 0) >= 2:
                boxes.append(parent)
        row[_IDX["dup_count"]] = float(min(10, key_count[keys[i]]))
        row[_IDX["dup_earlier"]] = 1.0 if keys[i] in seen_keys else 0.0
        seen_keys.add(keys[i])
        row[_IDX["len_rel_page"]] = math.log1p(chars[i]) - math.log1p(median_chars)
        ws = block_words[i]
        if ws:
            row[_IDX["title_overlap"]] = len(ws & title_words) / len(ws)
            row[_IDX["desc_overlap"]] = len(ws & desc_words) / len(ws)
            own = 1 if chars[i] >= 200 else 0
            row[_IDX["topic_overlap"]] = sum(1 for w in ws if long_df.get(w, 0) - own >= 1) / len(ws)
            row[_IDX["topic_overlap_strong"]] = sum(1 for w in ws if long_df.get(w, 0) - own >= 3) / len(ws)
        row[_IDX["depth"]] = float(min(40, depth))
        for f in flags:
            row[_IDX["in_" + f]] = 1.0
        for w in set(words):
            row[_CLS0 + _bucket(w, N_CLASS_BUCKETS)] = 1.0
        for w in set(_WORD.findall(block.text.lower())[:2]):
            row[_TXT0 + _bucket(w, N_TEXT_BUCKETS)] = 1.0
        if boxes:
            b1 = boxes[0]
            bc = stats.text_len(b1)
            row[_IDX["box_link_density"]] = stats.link_density(b1)
            row[_IDX["box_log_chars"]] = math.log1p(bc)
            row[_IDX["box_long_p"]] = float(min(30, stats.long_paragraphs(b1)))
            row[_IDX["box_blocks"]] = float(min(200, box_blocks.get(id(b1), 0)))
            row[_IDX["unit_share_of_box"]] = chars[i] / max(1, bc)
            row[_IDX["box_share_of_page"]] = bc / page_chars
            row[_IDX["box_mean_chars"]] = math.log1p(bc / max(1, box_blocks.get(id(b1), 1)))
        if len(boxes) > 1:
            b2 = boxes[1]
            row[_IDX["box2_link_density"]] = stats.link_density(b2)
            row[_IDX["box2_log_chars"]] = math.log1p(stats.text_len(b2))
            row[_IDX["box2_long_p"]] = float(min(30, stats.long_paragraphs(b2)))
        box_of.append(boxes[0] if boxes else None)

        parent = tag.parent
        if isinstance(parent, Tag):
            sibs = [c for c in parent.children if isinstance(c, Tag)]
            pos = next((k for k, c in enumerate(sibs) if c is tag), 0)
            row[_IDX["same_tag_siblings"]] = float(min(50, sum(1 for c in sibs if c.name == tag.name)))
            row[_IDX["pos_in_parent"]] = pos / max(1, len(sibs) - 1)

    for i in range(n):
        if i > 0:
            out[i, _IDX["prev_log_chars"]] = math.log1p(chars[i - 1])
            out[i, _IDX["prev_link_density"]] = link_dens[i - 1]
            out[i, _IDX["prev_same_box"]] = float(box_of[i] is not None and box_of[i] is box_of[i - 1])
        if i < n - 1:
            out[i, _IDX["next_log_chars"]] = math.log1p(chars[i + 1])
            out[i, _IDX["next_link_density"]] = link_dens[i + 1]
            out[i, _IDX["next_same_box"]] = float(box_of[i] is not None and box_of[i] is box_of[i + 1])
    ids: dict[int, int] = {}
    box = np.full(n, -1, dtype=np.int32)
    for i, b in enumerate(box_of):
        if b is not None:
            box[i] = ids.setdefault(id(b), len(ids))
    return out, box
