"""Anchor-based extraction quality metrics.

Without human gold labels we measure two behaviours the product must expose:

  content_recall   — fraction of *content* anchors retained in the output
                     (proxy for “did we lose relevant chunks?”)
  noise_retention  — fraction of *chrome* anchors retained in the output
                     (proxy for “how much junk still pollutes vectors?”)

Anchors are derived from the raw HTML structure (main/article vs nav/footer),
not from any single extractor — so comparisons stay independent of our pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

from poc.baselines import estimate_tokens, noise_keyword_hits

_WS = re.compile(r"\s+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

NOISE_PHRASES = (
    "cookie",
    "subscribe",
    "newsletter",
    "follow us",
    "talk to sales",
    "accept all",
    "privacy policy",
    "sign up",
    "get a demo",
    "share this",
    "careers",
    "related products",
    "request a demo",
    "contact sales",
    "sign in",
)


def normalize_text(text: str) -> str:
    return _WS.sub(" ", text.lower()).strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", normalize_text(text))


def char_ngrams(text: str, n: int = 5) -> set[str]:
    """Word 5-grams — stable overlap unit for recall/retention."""
    toks = tokenize(text)
    if len(toks) < n:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def sentences(text: str, *, min_chars: int = 40) -> list[str]:
    parts = []
    for chunk in _SENT_SPLIT.split(text):
        s = _WS.sub(" ", chunk).strip()
        if len(s) >= min_chars:
            parts.append(s)
    return parts


def _tag_text(tag: Tag) -> str:
    return _WS.sub(" ", tag.get_text(" ", strip=True))


def extract_anchors(html: str) -> tuple[set[str], set[str], dict]:
    """Return (content_ngrams, noise_ngrams, diagnostics)."""
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(["script", "style", "noscript", "svg", "template"]):
        t.decompose()

    noise_nodes: list[Tag] = []
    for sel in ("nav", "footer", "header", "aside"):
        noise_nodes.extend(soup.find_all(sel))
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag) or not tag.attrs:
            continue
        role = (tag.get("role") or "").lower()
        if role in {"navigation", "banner", "contentinfo", "complementary"}:
            noise_nodes.append(tag)
        blob = " ".join(
            str(x)
            for x in (
                tag.get("id"),
                " ".join(tag.get("class") or []) if isinstance(tag.get("class"), list) else tag.get("class"),
            )
            if x
        ).lower()
        if any(
            k in blob
            for k in (
                "cookie",
                "consent",
                "newsletter",
                "subscribe",
                "global-footer",
                "global-header",
                "site-footer",
                "chat-widget",
            )
        ):
            noise_nodes.append(tag)

    noise_text_parts: list[str] = []
    seen_noise: set[int] = set()
    for node in noise_nodes:
        if id(node) in seen_noise:
            continue
        seen_noise.add(id(node))
        # skip enormous wrappers (mis-tagged content)
        text = _tag_text(node)
        if 20 <= len(text) <= 4000:
            noise_text_parts.append(text)

    # Content region: prefer main/article; fall back to body minus noise nodes
    content_root: Tag | BeautifulSoup = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    # Clone-ish: collect text from content_root but skip noise descendants
    content_parts: list[str] = []
    if isinstance(content_root, Tag):
        for el in content_root.find_all(
            ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "pre", "figcaption"]
        ):
            if not isinstance(el, Tag):
                continue
            if el.find_parent(["nav", "footer", "header", "aside"]):
                continue
            role_parent = el.find_parent(attrs={"role": True})
            if role_parent and (role_parent.get("role") or "").lower() in {
                "navigation",
                "banner",
                "contentinfo",
            }:
                continue
            text = _tag_text(el)
            if len(text) >= 30:
                content_parts.append(text)
        # shallow divs with prose
        for el in content_root.find_all(["div", "section"]):
            if not isinstance(el, Tag):
                continue
            if el.find_parent(["nav", "footer", "header", "aside"]):
                continue
            kids = [
                c
                for c in el.children
                if isinstance(c, Tag)
                and c.name in {"div", "section", "p", "ul", "ol", "table", "h1", "h2", "h3"}
            ]
            if kids:
                continue
            # direct text weight
            direct = " ".join(
                str(c).strip() for c in el.children if isinstance(c, NavigableString) and str(c).strip()
            )
            text = _tag_text(el) if not direct else direct
            if 40 <= len(text) <= 1200:
                content_parts.append(text)

    content_blob = "\n".join(content_parts)
    noise_blob = "\n".join(noise_text_parts)

    content_ng = char_ngrams(content_blob)
    noise_ng = char_ngrams(noise_blob)

    # Drop grams that appear in BOTH — ambiguous, don't punish either side
    overlap = content_ng & noise_ng
    content_ng -= overlap
    noise_ng -= overlap

    diag = {
        "content_chars": len(content_blob),
        "noise_chars": len(noise_blob),
        "content_ngrams": len(content_ng),
        "noise_ngrams": len(noise_ng),
        "ambiguous_ngrams_removed": len(overlap),
        "content_sentences": len(sentences(content_blob)),
    }
    return content_ng, noise_ng, diag


@dataclass
class ExtractionScores:
    method: str
    tokens: int
    chars: int
    content_recall: float
    noise_retention: float
    noise_keyword_total: int
    noise_per_1k_tokens: float
    f_precision: float  # favors low noise
    f_coverage: float  # favors high recall
    f_balanced: float
    anchor_diag: dict
    notes: str = ""


def score_extraction(
    method: str,
    text: str,
    content_ngrams: set[str],
    noise_ngrams: set[str],
    anchor_diag: dict,
) -> ExtractionScores:
    out_ng = char_ngrams(text)
    tokens = estimate_tokens(text)
    noise_hits = noise_keyword_hits(text)
    noise_total = sum(noise_hits.values())

    if content_ngrams:
        content_recall = len(out_ng & content_ngrams) / len(content_ngrams)
    else:
        content_recall = 0.0

    if noise_ngrams:
        noise_retention = len(out_ng & noise_ngrams) / len(noise_ngrams)
    else:
        noise_retention = 0.0

    # Clamp
    content_recall = max(0.0, min(1.0, content_recall))
    noise_retention = max(0.0, min(1.0, noise_retention))

    noise_clean = 1.0 - noise_retention  # higher = cleaner
    # F-beta style composites so modes are measurable
    # precision mode: weight cleanliness higher (beta < 1 on recall)
    eps = 1e-9
    f_precision = (1.25 * noise_clean * content_recall) / (0.25 * content_recall + noise_clean + eps)
    # coverage mode: weight recall higher
    f_coverage = (5.0 * noise_clean * content_recall) / (4.0 * noise_clean + content_recall + eps)
    f_balanced = (2.0 * noise_clean * content_recall) / (noise_clean + content_recall + eps)

    return ExtractionScores(
        method=method,
        tokens=tokens,
        chars=len(text),
        content_recall=round(content_recall, 4),
        noise_retention=round(noise_retention, 4),
        noise_keyword_total=noise_total,
        noise_per_1k_tokens=round(1000.0 * noise_total / max(1, tokens), 3),
        f_precision=round(f_precision, 4),
        f_coverage=round(f_coverage, 4),
        f_balanced=round(f_balanced, 4),
        anchor_diag=anchor_diag,
    )


def scores_to_dict(s: ExtractionScores) -> dict:
    return {
        "method": s.method,
        "tokens": s.tokens,
        "chars": s.chars,
        "content_recall": s.content_recall,
        "noise_retention": s.noise_retention,
        "noise_keyword_total": s.noise_keyword_total,
        "noise_per_1k_tokens": s.noise_per_1k_tokens,
        "f_precision": s.f_precision,
        "f_coverage": s.f_coverage,
        "f_balanced": s.f_balanced,
        "anchor_diag": s.anchor_diag,
        "notes": s.notes,
    }
