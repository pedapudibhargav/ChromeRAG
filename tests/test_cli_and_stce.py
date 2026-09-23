"""CLI workflow (extract / learn / batch) and chrome-pruning regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from chromerag import ChromeRAG
from chromerag.cli import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "site"


def test_content_wrapper_with_sidebar_class_is_not_pruned() -> None:
    # Regression: class tokens like "has-sidebar" used to delete the whole article body.
    prose = "Vitest is a testing framework powered by Vite with a Jest compatible API. " * 20
    html = (
        "<html><body><aside>Guide Config API</aside>"
        f'<div class="VPContent has-sidebar"><div class="doc"><p>{prose}</p></div></div>'
        "</body></html>"
    )
    md = ChromeRAG().extract(html).markdown
    assert "Jest compatible API" in md


def test_small_sidebar_is_still_pruned() -> None:
    body = "Content paragraph about database migrations and schema versioning. " * 20
    html = (
        '<html><body><div class="sidebar"><p>Related links and other navigation</p></div>'
        f"<main><p>{body}</p></main></body></html>"
    )
    md = ChromeRAG().extract(html).markdown
    assert "database migrations" in md
    assert "Related links" not in md


def test_learn_creates_missing_output_dir_and_batch_uses_model(tmp_path: Path) -> None:
    model = tmp_path / "nested" / "dir" / "site.json"
    assert main(["learn", str(EXAMPLES), "-o", str(model), "--min-pages", "3"]) == 0
    payload = json.loads(model.read_text(encoding="utf-8"))
    assert payload["models"]["docs.example.com/docs"]["signatures"]

    out = tmp_path / "batch"
    assert main(["batch", str(EXAMPLES), "-o", str(out), "--chrome-model", str(model)]) == 0
    summary = json.loads((out / "batch_summary.json").read_text(encoding="utf-8"))
    assert len(summary) == 4
    assert all(row["stce_applied"] for row in summary)
    pricing = (out / "pricing" / "chromerag.md").read_text(encoding="utf-8")
    assert "Widget Summit" not in pricing  # repeated in-content strip removed by STCE
    assert "Monthly price (USD): 49" in pricing  # table linearized, content kept


def test_extract_writes_into_missing_dir(tmp_path: Path) -> None:
    out = tmp_path / "a" / "b" / "pricing.md"
    assert main(["extract", str(EXAMPLES / "pricing.html"), "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("---")


def test_missing_chrome_model_is_a_clean_error(tmp_path: Path) -> None:
    rc = main(
        ["batch", str(EXAMPLES), "-o", str(tmp_path / "o"), "--chrome-model", "nope.json"]
    )
    assert rc == 2
