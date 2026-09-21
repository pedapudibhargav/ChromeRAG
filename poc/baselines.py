"""Baseline extractors for comparison."""

from __future__ import annotations

from typing import Callable

import tiktoken


def estimate_tokens(text: str) -> int:
    try:
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return max(1, len(text) // 4)


def baseline_beautifulsoup(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return soup.get_text("\n", strip=True)


def baseline_markdownify(html: str) -> str:
    from markdownify import markdownify as md

    return md(html, heading_style="ATX")


def baseline_readability(html: str) -> str:
    from readability import Document
    from bs4 import BeautifulSoup

    doc = Document(html)
    summary = doc.summary()
    title = doc.title()
    text = BeautifulSoup(summary, "lxml").get_text("\n", strip=True)
    return f"# {title}\n\n{text}\n"


def baseline_trafilatura(html: str) -> str:
    import trafilatura

    out = trafilatura.extract(
        html,
        include_tables=True,
        include_comments=False,
        include_links=False,
        output_format="markdown",
    )
    return out or ""


def baseline_html2text(html: str) -> str:
    import html2text

    h = html2text.HTML2Text()
    h.ignore_links = False
    h.body_width = 0
    return h.handle(html)


def baseline_markitdown(html: str, path_hint: str | None = None) -> str:
    try:
        from markitdown import MarkItDown
    except ImportError:
        return "[markitdown not installed]"

    import tempfile
    from pathlib import Path

    md = MarkItDown()
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        tmp = Path(f.name)
    try:
        result = md.convert(str(tmp))
        return result.text_content or ""
    finally:
        tmp.unlink(missing_ok=True)


BASELINES: dict[str, Callable[..., str]] = {
    "beautifulsoup_text": baseline_beautifulsoup,
    "markdownify": baseline_markdownify,
    "readability": baseline_readability,
    "trafilatura": baseline_trafilatura,
    "html2text": baseline_html2text,
    "markitdown": baseline_markitdown,
}


def noise_keyword_hits(text: str) -> dict[str, int]:
    keywords = [
        "cookie",
        "subscribe",
        "newsletter",
        "follow us",
        "related products",
        "talk to sales",
        "accept all",
        "privacy policy",
        "sign up",
        "get a demo",
        "share this",
        "careers",
    ]
    low = text.lower()
    return {k: low.count(k) for k in keywords}
