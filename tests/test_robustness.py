"""Tests for WP2 robustness: per-call config, hidden nodes, skip links."""

from __future__ import annotations

from pathlib import Path

from chromerag import ChromeRAG, PipelineConfig
from chromerag.config import PageType

FIXTURES = Path(__file__).parent / "fixtures"


def test_per_call_config_uses_inferred_type_per_url() -> None:
    rag = ChromeRAG(config=PipelineConfig(page_type=PageType.UNKNOWN))
    docs_html = """<!doctype html><html><body><main><h1>Guide</h1>
    <p>Documentation paragraph with enough words to pass extraction thresholds easily.</p>
    </main></body></html>"""
    marketing_html = """<!doctype html><html><body><main><h1>Platform</h1>
    <p>Enterprise platform overview with enough words to pass extraction thresholds easily.</p>
    </main></body></html>"""
    docs = rag.extract(docs_html, url="https://example.com/documentation/guide")
    marketing = rag.extract(marketing_html, url="https://example.com/products/platform")
    assert docs.diagnostics["page_type"] == PageType.DOCS.value
    assert marketing.diagnostics["page_type"] == PageType.MARKETING.value


def test_hidden_nodes_removed_from_output() -> None:
    html = FIXTURES.joinpath("hidden_nodes.html").read_text(encoding="utf-8")
    md = ChromeRAG(enable_dvdf=False).extract(html).markdown.lower()
    assert "visible guide" in md
    assert "environment variable api_key" in md
    assert "sign up now for 50 percent off" not in md
    assert "modal overlay marketing" not in md


def test_skip_link_removed() -> None:
    html = """<!doctype html><html><body>
    <a href="#main">Skip to main content</a>
    <main id="main"><p>Real article body with enough words for extraction tests.</p></main>
    </body></html>"""
    md = ChromeRAG(enable_dvdf=False).extract(html).markdown.lower()
    assert "skip to main content" not in md
    assert "real article body" in md


def test_content_root_in_diagnostics() -> None:
    html = FIXTURES.joinpath("docs_page.html").read_text(encoding="utf-8")
    result = ChromeRAG(enable_dvdf=False).extract(html, url="https://docs.example.com/sla")
    assert result.diagnostics.get("content_root") in {"main", "article", "body", "role=main"}
