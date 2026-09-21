"""Tests for thin / JS-shell input quality warnings."""

from __future__ import annotations

from chromerag import ChromeRAG
from chromerag.input_quality import assess_input_html


def test_js_shell_triggers_warning() -> None:
    html = """<!doctype html><html><head><title>App</title></head>
    <body><div id="root"></div>
    <noscript>Please enable JavaScript to continue.</noscript>
    <script>window.__BOOT__=true;""" + ("x" * 2000) + """</script>
    </body></html>"""
    report = assess_input_html(html)
    assert report.is_thin
    assert report.likely_js_shell
    assert report.warnings
    assert "Playwright" in report.warnings[0] or "render" in report.warnings[0].lower()


def test_rich_html_has_no_thin_warning() -> None:
    body = " ".join(["Bandwidth SLA is 99.99 percent for enterprise customers."] * 20)
    html = f"""<!doctype html><html><body>
    <main><article><h1>SLA</h1><p>{body}</p></article></main>
    <nav>Sign in</nav><footer>Cookie settings</footer>
    </body></html>"""
    report = assess_input_html(html)
    assert not report.is_thin
    assert not report.likely_js_shell
    assert report.warnings == []


def test_extract_result_surfaces_warnings() -> None:
    html = """<!doctype html><html><body>
    <div id="__next"></div>
    <script src="/bundle.js"></script>
    </body></html>"""
    result = ChromeRAG(enable_dvdf=False).extract(html, url="https://example.com/app")
    assert result.warnings
    assert result.input_quality.get("is_thin") is True
    assert result.input_quality.get("likely_js_shell") is True


def test_empty_html_warns() -> None:
    report = assess_input_html("")
    assert report.is_thin
    assert report.warnings
