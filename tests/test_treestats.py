"""TreeStats must give exactly the numbers that live bs4 calls give."""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from chromerag.density import parse_html, strip_non_content_tags
from chromerag.treestats import TreeStats

FIXTURES = sorted(Path(__file__).parent.glob("fixtures/*.html")) + sorted(
    Path(__file__).parent.glob("rules/*.html")
)

TRICKY = """<html><body>
<main><p>Fish &amp; chips &lt;b&gt; "quoted" 'single' <a href="/x?a=1&b=2">link &amp; <a>nested</a></a></p>
<div class='x "y"' data-k="a'b&quot;c" hidden data-empty="">  spaced   <br>text<img src=a.png alt="">
<pre>  raw
 text </pre></div><a href="#"></a><a></a><!-- gone --><span>é ü 你好 &nbsp; nbsp</span>
<table><tr><td>1</td><td>2</td></tr></table></main><footer>foot <b>er</b></footer>
</body></html>"""


def _pages() -> list[str]:
    return [f.read_text(encoding="utf-8") for f in FIXTURES] + [TRICKY]


@pytest.mark.parametrize("html", _pages())
def test_stats_equal_live_bs4(html: str) -> None:
    soup = parse_html(html)
    strip_non_content_tags(soup)
    body = soup.body
    stats = TreeStats(body, serialized=True)
    for tag in [body, *body.find_all(True)]:
        assert stats.text_len(tag) == len(tag.get_text(" ", strip=True)), tag.name
        assert stats.text_nosep(tag) == len(tag.get_text("", strip=True)), tag.name
        links = " ".join(a.get_text(" ", strip=True) for a in tag.find_all("a"))
        assert stats.link_len(tag) == len(links), tag.name
        assert stats.has_main(tag) == bool(tag.find("main") or tag.find(attrs={"role": "main"})), tag.name
        assert stats.html_len(tag) == len(str(tag)), (tag.name, str(tag)[:80])


def test_stats_stay_valid_for_later_tags_when_visited_tag_is_removed() -> None:
    soup = BeautifulSoup(TRICKY, "lxml")
    body = soup.body
    stats = TreeStats(body)
    for tag in list(body.find_all(True)):
        if tag.attrs is None:
            continue
        assert stats.text_len(tag) == len(tag.get_text(" ", strip=True))
        if tag.name in {"footer", "div"}:
            tag.decompose()
