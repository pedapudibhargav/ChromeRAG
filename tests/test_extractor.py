"""Unit tests for ChromeRAG HTML → Markdown extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from chromerag import ChromeRAG, PipelineConfig, __version__
from chromerag.config import ContentPriority, Strictness
from chromerag.schema_fusion import fuse_front_matter
from chromerag.density import parse_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def docs_html() -> str:
    return (FIXTURES / "docs_page.html").read_text(encoding="utf-8")


def test_version_semver_shape() -> None:
    assert __version__
    assert __version__[0].isdigit()


def test_extract_keeps_main_content_drops_nav(docs_html: str) -> None:
    result = ChromeRAG(strictness=Strictness.BALANCED, enable_dvdf=False).extract(
        docs_html, url="https://docs.example.com/sla"
    )
    md = result.markdown.lower()
    assert "bandwidth" in md
    assert "99.99" in md or "sla" in md
    # Chrome should be heavily reduced
    assert md.count("sign in") <= 1
    assert "cookie settings" not in md or md.count("cookie") == 0


def test_schema_front_matter_before_script_strip(docs_html: str) -> None:
    result = ChromeRAG(enable_dvdf=False).extract(docs_html, url="https://docs.example.com/sla")
    assert result.front_matter
    blob = " ".join(str(v).lower() for v in result.front_matter.values())
    assert "bandwidth" in blob or "sla" in blob or "techarticle" in blob.lower()
    assert result.markdown.lstrip().startswith("---")


def test_table_linearization(docs_html: str) -> None:
    result = ChromeRAG(enable_dvdf=False, enable_tables=True).extract(docs_html)
    assert "srv.large" in result.markdown
    assert result.n_tables >= 1


def test_precision_vs_coverage_keeps_core_content(docs_html: str) -> None:
    precision = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.PRECISION, enable_dvdf=False)
    ).extract(docs_html)
    coverage = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.COVERAGE, enable_dvdf=False)
    ).extract(docs_html)
    assert "bandwidth" in coverage.markdown.lower()
    assert "bandwidth" in precision.markdown.lower()
    assert len(precision.markdown) > 50
    assert len(coverage.markdown) > 50


def test_fuse_front_matter_reads_json_ld(docs_html: str) -> None:
    soup = parse_html(docs_html)
    fm = fuse_front_matter(soup, url="https://docs.example.com/sla")
    assert fm
    assert any("bandwidth" in str(v).lower() or "sla" in str(v).lower() for v in fm.values())


def test_empty_html_does_not_crash() -> None:
    result = ChromeRAG(enable_dvdf=False).extract("<html><body></body></html>")
    assert isinstance(result.markdown, str)
    assert result.n_blocks_in >= 0
