"""Tests for HTML table → Markdown output."""

from __future__ import annotations

from bs4 import BeautifulSoup

from chromerag import ChromeRAG, PipelineConfig
from chromerag.tables import format_table, render_pipe_table


def _table(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    assert table is not None
    return format_table(table)


def test_rectangular_table_renders_pipe_markdown() -> None:
    text = _table(
        "<table><thead><tr><th>SKU</th><th>Cores</th><th>Monthly</th></tr></thead>"
        "<tbody><tr><td>srv.large</td><td>8</td><td>120</td></tr></tbody></table>"
    )
    lines = text.split("\n")
    assert lines[0] == "| SKU | Cores | Monthly |"
    assert lines[1] == "| --- | --- | --- |"
    assert lines[2] == "| srv.large | 8 | 120 |"


def test_colspan_table_stays_linearized() -> None:
    text = _table(
        "<table><tr><th>Name</th><th>Value</th></tr>"
        "<tr><td colspan='2'>Merged row</td></tr></table>"
    )
    assert text.startswith("[Table:")
    assert "Row 1 ->" in text


def test_table_format_linearized_kwarg() -> None:
    html = (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    assert table is not None
    text = format_table(table, table_format="linearized")
    assert text.startswith("[Table:")
    assert "A: 1" in text


def test_pipe_cell_escapes_pipes() -> None:
    soup = BeautifulSoup(
        "<table><tr><th>Key</th><th>Val</th></tr>"
        "<tr><td>a|b</td><td>ok</td></tr></table>",
        "lxml",
    )
    table = soup.find("table")
    assert table is not None
    text = render_pipe_table(table)
    assert r"a\|b" in text


def test_extractor_default_pipe_table() -> None:
    html = (
        "<html><body><main><table>"
        "<tr><th>Plan</th><th>Price</th></tr>"
        "<tr><td>Team</td><td>49</td></tr>"
        "</table></main></body></html>"
    )
    md = ChromeRAG(config=PipelineConfig(enable_dvdf=False)).extract(html).markdown
    assert "| Plan | Price |" in md
    assert "| Team | 49 |" in md


def test_extractor_linearized_table_format() -> None:
    html = (
        "<html><body><main><table>"
        "<tr><th>Plan</th><th>Price</th></tr>"
        "<tr><td>Team</td><td>49</td></tr>"
        "</table></main></body></html>"
    )
    md = ChromeRAG(
        config=PipelineConfig(enable_dvdf=False, table_format="linearized")
    ).extract(html).markdown
    assert "[Table:" in md
    assert "Plan: Team" in md


def test_table_without_rows_does_not_crash() -> None:
    from chromerag import ChromeRAG

    html = "<html><body><main><h1>Page</h1><p>" + "Body text with enough words. " * 30 + "</p><table></table><table><caption>Empty</caption></table></main></body></html>"
    assert "Body text" in ChromeRAG().extract(html).markdown


def test_empty_columns_omitted_from_linearized_and_pipe() -> None:
    text = _table(
        "<table><tr><th>A</th><th>B</th><th></th></tr>"
        "<tr><td>1</td><td>2</td><td></td></tr>"
        "<tr><td>3</td><td>4</td><td></td></tr></table>"
    )
    assert "col3" not in text
    assert "| A | B |" in text
    assert text.count("|") >= 6


def test_spacer_rows_still_allow_pipe_table() -> None:
    text = _table(
        "<table><tr><th>Svc</th><th>Pct</th></tr>"
        "<tr><td>Art</td><td>10%</td></tr>"
        "<tr><td></td><td></td></tr>"
        "<tr><td>Books</td><td>20%</td></tr>"
        "<tr><td>Cars</td><td>30%</td></tr>"
        "<tr><td>Desks</td><td>40%</td></tr></table>"
    )
    assert text.startswith("| Svc | Pct |")
    assert "| --- | --- |" in text
    assert "[Table:" not in text


def test_blank_header_row_does_not_emit_separator_only_pipe() -> None:
    text = _table(
        "<table><tr><th></th><th></th></tr>"
        "<tr><td>Excellent</td><td>Average</td></tr></table>"
    )
    assert not text.startswith("| ---")
    assert "Excellent" in text


def test_pipe_table_inside_list_keeps_header_above_separator() -> None:
    html = (
        "<html><body><main><ul><li>Rating 4.6"
        "<pre>| COVERAGE | AGE |\n| --- | --- |\n| Excellent | Average |</pre>"
        "</li></ul>"
        "<p>" + "Body text with enough words for extraction thresholds. " * 8 + "</p>"
        "</main></body></html>"
    )
    md = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html).markdown
    assert "| COVERAGE | AGE |" in md
    # Header line must appear before the separator (not glued away).
    assert md.index("| COVERAGE | AGE |") < md.index("| --- | --- |")
