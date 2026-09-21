"""Detect thin / JS-shell HTML so callers can fix their fetch/render pipeline.

ChromeRAG does not execute JavaScript. When the input document is mostly an empty
SPA shell, extraction will correctly yield little text — and we warn loudly so
operators do not mistake that for a ChromeRAG bug.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# Heuristic thresholds — tuned for corporate docs/marketing shells.
_MIN_VISIBLE_CHARS = 280
_MIN_VISIBLE_WORDS = 40
_SCRIPT_HEAVY_RATIO = 0.35  # script text / (script + visible) when visible is tiny
_ROOT_MARKERS = (
    "id=\"root\"",
    "id='root'",
    'id="app"',
    "id='app'",
    'id="__next"',
    "id='__next'",
    'id="__nuxt"',
    "data-reactroot",
    "ng-version=",
)


@dataclass
class InputQualityReport:
    """Assessment of whether the HTML looks render-ready for extraction."""

    is_thin: bool
    likely_js_shell: bool
    visible_chars: int
    visible_words: int
    script_chars: int
    noscript_hint: bool
    root_marker: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "is_thin": self.is_thin,
            "likely_js_shell": self.likely_js_shell,
            "visible_chars": self.visible_chars,
            "visible_words": self.visible_words,
            "script_chars": self.script_chars,
            "noscript_hint": self.noscript_hint,
            "root_marker": self.root_marker,
            "warnings": list(self.warnings),
        }


def _visible_text(html: str) -> tuple[str, int]:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    script_soup = BeautifulSoup(html, "lxml")
    script_chars = sum(len(s.get_text() or "") for s in script_soup.find_all("script"))
    return text, script_chars


def assess_input_html(html: str) -> InputQualityReport:
    """Return warnings when HTML looks like an unrendered JS shell or is otherwise thin."""
    if not html or not html.strip():
        return InputQualityReport(
            is_thin=True,
            likely_js_shell=False,
            visible_chars=0,
            visible_words=0,
            script_chars=0,
            noscript_hint=False,
            warnings=[
                "Empty HTML input. ChromeRAG needs a full HTML document string/file. "
                "If this came from a crawler, verify the fetch pipeline."
            ],
        )

    text, script_chars = _visible_text(html)
    words = [w for w in re.findall(r"[A-Za-z0-9]{2,}", text)]
    visible_chars = len(text)
    visible_words = len(words)
    low = html.lower()
    noscript_hint = "<noscript" in low and (
        "enable javascript" in low or "requires javascript" in low or "turn on javascript" in low
    )
    root_marker = next((m for m in _ROOT_MARKERS if m in low), None)

    is_thin = visible_chars < _MIN_VISIBLE_CHARS or visible_words < _MIN_VISIBLE_WORDS
    denom = max(script_chars + visible_chars, 1)
    script_heavy = (script_chars / denom) >= _SCRIPT_HEAVY_RATIO and visible_chars < 800
    likely_js_shell = is_thin and (bool(root_marker) or noscript_hint or script_heavy)

    warnings: list[str] = []
    if likely_js_shell:
        warnings.append(
            "Input HTML looks like a JavaScript-rendered shell (little visible text"
            + (f"; marker `{root_marker}`" if root_marker else "")
            + "). ChromeRAG does not execute JS. Render the page first "
            "(Playwright / Puppeteer / your crawler), then pass the rendered HTML here "
            "so your fetch pipeline can be verified."
        )
    elif is_thin:
        warnings.append(
            f"Input HTML is thin for RAG ingest (visible≈{visible_chars} chars, "
            f"{visible_words} words). Verify the upstream fetch/render step served "
            "full page content — ChromeRAG only cleans the HTML it receives."
        )

    return InputQualityReport(
        is_thin=is_thin,
        likely_js_shell=likely_js_shell,
        visible_chars=visible_chars,
        visible_words=visible_words,
        script_chars=script_chars,
        noscript_hint=noscript_hint,
        root_marker=root_marker,
        warnings=warnings,
    )
