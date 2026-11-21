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
    assert "this paragraph is visible" in md
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


# --- robustness added in 0.1.4 ---------------------------------------------------------------

def _deep(depth: int) -> str:
    return "<html><body>" + "<div>" * depth + "<p>" + "Deeply nested text that should still be found. " * 6 + "</p>" + "</div>" * depth + "</body></html>"


def test_very_deep_nesting_does_not_crash() -> None:
    md = ChromeRAG().extract(_deep(20000)).markdown
    assert isinstance(md, str)


def test_batch_survives_one_failing_page(tmp_path, monkeypatch) -> None:
    from chromerag.batch import BatchPage, learn_then_extract
    from chromerag.extractor import ChromeRAG as Extractor

    good = "<html><body><main><p>" + "Real paragraph about backups and restores. " * 10 + "</p></main></body></html>"
    original = Extractor.extract

    def flaky(self, html, url=None):
        if "BOOM" in html:
            raise RuntimeError("boom")
        return original(self, html, url=url)

    monkeypatch.setattr(Extractor, "extract", flaky)
    pages = [BatchPage(good, None, "a"), BatchPage("<html>BOOM</html>", None, "b"), BatchPage(good, None, "c")]
    results, _ = learn_then_extract(pages, learn=False)
    assert [r.error is None for r in results] == [True, False, True]
    assert results[1].result is None


def test_non_utf8_bytes_are_decoded_with_the_declared_charset() -> None:
    html = ("<html><head><meta charset='windows-1252'></head><body><main><p>"
            + "Café crème brûlée and a résumé about desserts for every season of the year. " * 6
            + "</p></main></body></html>").encode("cp1252")
    assert "Café crème brûlée" in ChromeRAG().extract(html).markdown


def test_learn_is_fast_on_unclosed_script_tags() -> None:
    import time

    from chromerag.site_chrome import mine_site_chrome

    page = "<html><body>" + "<script " * 20000 + "</body></html>"
    start = time.perf_counter()
    mine_site_chrome([(f"https://x.example/docs/{i}", page) for i in range(3)], min_pages=3)
    assert time.perf_counter() - start < 5


def test_output_is_deterministic() -> None:
    html = "<html><body><main>" + "".join(f"<p>Paragraph number {i} about configuration, retention and restores.</p>" for i in range(30)) + "</main></body></html>"
    assert len({ChromeRAG().extract(html).markdown for _ in range(3)}) == 1


def test_deep_emphasis_nesting_does_not_raise() -> None:
    # Text long enough to survive density filtering; must remain after depth-cap fallback.
    marker = "AAAADEEP_EMPHASIS_KEEP_ME_THROUGH_FILTERING_AAAA"
    html = (
        "<html><body><main><p>"
        + "<b>" * 1500
        + marker
        + "</b>" * 1500
        + "</p></main></body></html>"
    )
    result = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html)
    assert isinstance(result.markdown, str)
    assert marker in result.markdown


def test_deep_list_nesting_does_not_raise() -> None:
    marker = "AAAALIST_LEAF_KEEP_ME_THROUGH_FILTERING_AAAA"
    html = (
        "<html><body><main>"
        + "<ul><li>" * 500
        + marker
        + "</li></ul>" * 500
        + "</main></body></html>"
    )
    result = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html)
    assert isinstance(result.markdown, str)
    assert marker in result.markdown


def test_lone_surrogate_does_not_raise_on_encode() -> None:
    html = (
        "<html><body><main><p>hello \ud800 world with enough words for extraction "
        "thresholds easily today and tomorrow.</p></main></body></html>"
    )
    result = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html)
    result.markdown.encode("utf-8")  # must not raise


def _time_limit(seconds: float) -> float:
    """Wall-clock limit for timing tests; shared CI runners set CHROMERAG_TEST_TIME_SCALE (>1)."""
    import os

    return seconds * float(os.environ.get("CHROMERAG_TEST_TIME_SCALE", "1"))


def test_pathological_inputs_finish_under_two_seconds() -> None:
    import time

    cfg = PipelineConfig(enable_dvdf=False, enable_lbc=False)
    rag = ChromeRAG(config=cfg)

    def nested_tables(depth: int) -> str:
        opener = "<html><body><main>" + "<table><tr><td>" * depth
        closer = "</td></tr></table>" * depth + "</main></body></html>"
        return opener + "cell data value" + closer

    rows = "".join(f"<tr><td>A{i}</td><td>B{i}</td><td>C{i}</td></tr>" for i in range(30000))
    huge = (
        "<html><body><main><table><tr><th>A</th><th>B</th><th>C</th></tr>"
        + rows
        + "</table></main></body></html>"
    )
    deep_divs = (
        "<html><body><main>"
        + "<div>" * 20000
        + "<p>Text about widgets with enough words for extraction.</p>"
        + "</main></body></html>"
    )
    for html, limit in (
        (nested_tables(2000), 2.0),
        (huge, 5.0),
        (deep_divs, 2.0),
    ):
        start = time.perf_counter()
        result = rag.extract(html)
        assert time.perf_counter() - start < _time_limit(limit)
        assert isinstance(result.markdown, str)
