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
