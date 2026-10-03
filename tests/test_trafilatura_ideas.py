"""Tests for Trafilatura-inspired density heuristics."""

from __future__ import annotations

from types import SimpleNamespace

from bs4 import BeautifulSoup

from chromerag.trafilatura_ideas import apply_trafilatura_ideas


def _cfg(**kwargs):
    defaults = {"trafilatura_link_blocks": True, "trafilatura_micro": True}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_link_blocks_drop_high_link_density_short_nav() -> None:
    html = (
        "<html><body><main>"
        '<div class="nav-chrome"><a href="/a">One</a> <a href="/b">Two</a> '
        '<a href="/c">Three</a></div>'
        "<p>Real article body with enough words to survive pruning and stay in output.</p>"
        "</main></body></html>"
    )
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main")
    removed = apply_trafilatura_ideas(soup, _cfg(), main)
    assert removed["link_blocks"] >= 1
    text = soup.get_text(" ", strip=True).lower()
    assert "real article body" in text
    assert "one" not in text or "two" not in text


def test_link_blocks_keep_editorial_list_in_main() -> None:
    html = (
        "<html><body><main><ul>"
        "<li><a href='/1'>Short</a></li>"
        "<li><a href='/2'>Also</a></li>"
        "<li><a href='/3'>Tiny</a></li>"
        "<li><a href='/4'>Links</a></li>"
        "<li><a href='/5'>Here</a></li>"
        "</ul><p>Article paragraph with substantive analysis of the topic.</p></main></body></html>"
    )
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main")
    removed = apply_trafilatura_ideas(soup, _cfg(), main)
    assert removed["link_blocks"] == 0
    assert soup.find("ul") is not None


def test_micro_drops_tiny_leaf_nodes() -> None:
    html = (
        "<html><body><main>"
        "<p>ok</p>"
        "<p>Substantive paragraph that should remain after micro-text cleanup runs.</p>"
        "</main></body></html>"
    )
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main")
    removed = apply_trafilatura_ideas(soup, _cfg(), main)
    assert removed["micro"] >= 1
    assert "substantive paragraph" in soup.get_text(" ", strip=True).lower()


def test_flags_disable_passes() -> None:
    html = (
        "<html><body><main><span>x</span>"
        '<div class="x"><a href="/">Link</a></div>'
        "<p>Keep this paragraph with enough words for the guard checks.</p>"
        "</main></body></html>"
    )
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main")
    off = apply_trafilatura_ideas(
        soup, _cfg(trafilatura_link_blocks=False, trafilatura_micro=False), main
    )
    assert off == {}
