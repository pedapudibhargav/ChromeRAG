"""CLI workflow (extract / learn / batch) and chrome-pruning regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from chromerag import ChromeRAG, mine_site_chrome
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
    assert [p.name for p in (out / "pricing").iterdir()] == ["chromerag.md"]
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


def _page(path: str, block: str, body: str) -> tuple[str, str]:
    return (
        f"https://docs.example.com/docs/{path}",
        f"<html><body>{block}<main><p>{body}</p></main></body></html>",
    )


PROMO = (
    '<div class="css-x1y2z3"><a href="/signup">Get started free</a> and deploy '
    "your first widget in minutes</div>"
)


def test_stce_keeps_match_far_larger_than_learned_block() -> None:
    # Regression: a CSS-in-JS class learned from a small promo also wrapped a whole
    # article on another page, and STCE deleted the article.
    pages = [_page(f"p{i}", PROMO, f"Distinct page {i} body text. " * 30) for i in range(3)]
    model = mine_site_chrome(pages, min_pages=3)["docs.example.com/docs"]
    assert model.signatures

    article = "Configuring retries for webhook delivery with exponential backoff. " * 40
    html = f'<html><body>{PROMO}<div class="css-x1y2z3"><p>{article}</p></div></body></html>'
    md = ChromeRAG(site_chrome=model).extract(html, url="https://docs.example.com/docs/x").markdown
    assert "exponential backoff" in md


def test_stce_does_not_learn_shared_class_with_different_text() -> None:
    # Link cards share a class on every page but carry different text: content, not chrome.
    pages = [
        _page(
            f"p{i}",
            f'<div class="CardGroup"><a href="/a{i}">Guide {i}: accept payments online</a>'
            f'<a href="/b{i}">Tutorial {i}: build a checkout flow</a></div>',
            f"Distinct page {i} body text. " * 30,
        )
        for i in range(3)
    ]
    model = mine_site_chrome(pages, min_pages=3)["docs.example.com/docs"]
    assert not model.signatures


def test_stce_counts_a_repeated_url_once() -> None:
    first = _page("pricing", PROMO, "Pricing body. " * 30)
    pages = [first, (first[0] + "/", first[1]), _page("other", PROMO, "Other body. " * 30)]
    model = mine_site_chrome(pages, min_pages=3)["docs.example.com/docs"]
    assert model.n_pages == 2
    assert not model.signatures


def test_stce_learns_identical_short_text_without_chrome_markup() -> None:
    # A tagline repeated verbatim on every page is template even without nav/footer markup.
    tagline = '<div id="siteSub">From Example Docs, the free handbook</div>'
    pages = [_page(f"p{i}", tagline, f"Distinct page {i} body text. " * 30) for i in range(3)]
    model = mine_site_chrome(pages, min_pages=3)["docs.example.com/docs"]
    assert model.signatures
    html = pages[0][1]
    md = ChromeRAG(site_chrome=model).extract(html, url=pages[0][0]).markdown
    assert "free handbook" not in md
    assert "Distinct page 0" in md


def test_stce_keeps_content_that_only_shares_a_utility_class() -> None:
    # Utility CSS classes give unrelated blocks one signature; the learned block is a link bar,
    # the later match is prose with different text, so it must stay.
    bar = (
        '<div class="flex gap-4"><a href="/a">Home</a> <a href="/b">Guides and tutorials</a> '
        '<a href="/c">API reference</a> <a href="/d">Changelog</a></div>'
    )
    pages = [_page(f"p{i}", bar, f"Distinct page {i} body text. " * 30) for i in range(3)]
    model = mine_site_chrome(pages, min_pages=3)["docs.example.com/docs"]
    assert model.signatures
    prose = "Retry failed webhook deliveries with exponential backoff and jitter."
    html = f'<html><body>{bar}<main><div class="flex gap-4"><p>{prose}</p></div></main></body></html>'
    md = ChromeRAG(site_chrome=model).extract(html, url="https://docs.example.com/docs/x").markdown
    assert "exponential backoff" in md
    assert "API reference" not in md


def test_stce_counts_near_duplicate_pages_once() -> None:
    # The same page published for several versions must not turn its content into "template".
    body = "Django documentation: tutorials, topic guides, reference and how-to guides. " * 20
    pages = [
        (f"https://docs.example.com/docs/{v}/", f'<html><body><div class="intro">{body}</div></body></html>')
        for v in ("5.2", "5.1", "5.0", "4.2")
    ]
    model = mine_site_chrome(pages, min_pages=3)["docs.example.com/docs"]
    assert model.n_pages == 1
    assert not model.signatures


def test_stce_keeps_link_list_content_that_only_shares_a_layout_class() -> None:
    # A list of resource links shares a layout class with a learned link bar; link density
    # alone must not make it removable when its text differs from what was learned.
    bar = (
        '<div class="grid-row"><a href="/a">Home</a> <a href="/b">Guides and tutorials</a> '
        '<a href="/c">API reference</a> <a href="/d">Changelog</a></div>'
    )
    pages = [_page(f"p{i}", bar, f"Distinct page {i} body text. " * 30) for i in range(3)]
    model = mine_site_chrome(pages, min_pages=3)["docs.example.com/docs"]
    assert model.signatures
    profiles = (
        '<div class="grid-row"><a href="/p1">Cloud Security Community Profile</a> '
        '<a href="/p2">Financial Sector CSF Profile</a></div>'
    )
    html = f"<html><body>{bar}<main><p>Community profiles:</p>{profiles}</main></body></html>"
    md = ChromeRAG(site_chrome=model).extract(html, url="https://docs.example.com/docs/x").markdown
    assert "Financial Sector CSF Profile" in md
