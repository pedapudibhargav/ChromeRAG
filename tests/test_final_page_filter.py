"""Unit tests for poc.final_page_filter — synthetic pages only, no network."""

from __future__ import annotations

import json
from pathlib import Path

from poc import final_page_filter as f


def _write_page(root: Path, pid: str, html: str, url: str) -> None:
    (root / f"{pid}.html").write_text(html, encoding="utf-8")
    meta = {"id": pid, "url": url, "status": "ok", "page_type": "article"}
    (root / f"{pid}.meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_filter_duplicate_json_and_non_english(tmp_path: Path):
    pages = tmp_path / "final"
    pages.mkdir()
    en = (
        "<html><body>"
        + " ".join(
            [
                "The quick brown fox and the lazy dog are in the yard with their friends "
                "who can see that this is a story about the animals and the day."
            ]
            * 3
        )
        + "</body></html>"
    )
    # Italian-like visible text: almost no English stopwords, enough alpha tokens.
    it = (
        "<html><body>"
        + " ".join(
            [
                "Ciao benvenuti nella pagina principale del sito aziendale italiano "
                "con i prodotti e i servizi della azienda per le informazioni generali"
            ]
            * 4
        )
        + "</body></html>"
    )
    json_body = '[{"command":"insert","data":{"x":1}}]'
    _write_page(pages, "final-0001", en, "https://example.com/a")
    _write_page(pages, "final-0002", en, "https://example.com/a")  # dup of 0001
    _write_page(pages, "final-0003", it, "https://example.com/it")
    _write_page(pages, "final-0004", json_body, "https://example.com/api")
    # Thin login-ish English page must be kept (too few tokens for language rule).
    _write_page(
        pages,
        "final-0005",
        "<html><body>Login Password Submit</body></html>",
        "https://example.com/login",
    )

    report = f.filter_pages(pages)
    by_id = {r["id"]: r["reason"] for r in report["removed"]}
    assert by_id["final-0002"] == "duplicate_final_url"
    assert by_id["final-0003"] == "non_english_stopwords"
    assert by_id["final-0004"] == "non_html_json"
    assert "final-0001" in report["kept_ids"]
    assert "final-0005" in report["kept_ids"]


def test_english_list_page_with_few_common_words_is_kept():
    signals = f.language_signals("Shoes Boots Sandals Trainers Socks Laces Price Cart " * 6 + "the of")
    assert f.non_english_reason(signals) is None


def test_english_pronoun_and_web_addresses_are_not_foreign_evidence():
    text = "I bought it and I like it because I used https://shop.com/a www.shop.com " * 8
    assert f.non_english_reason(f.language_signals(text)) is None
    signals = f.language_signals("I use E mail and I read A B C D E index links " * 8)
    assert signals["best_other_stopwords"] == 0


def test_terse_list_with_language_switcher_is_kept():
    signals = f.language_signals("Sku Boots Sandals Trainers Socks Laces Price Cart " * 6 + "der die und")
    assert f.non_english_reason(signals) is None


def test_thai_body_under_english_menu_is_removed():
    signals = f.language_signals("Home About Contact the of " + "ราคาสินค้าวันนี้ดีมาก " * 40)
    assert f.non_english_reason(signals) == "non_english_script"


def test_json_inside_textarea(tmp_path: Path):
    pages = tmp_path / "final"
    pages.mkdir()
    html = '<html><body><textarea>[{"command":"insert","data":"x"}]</textarea></body></html>'
    _write_page(pages, "final-0152", html, "https://example.com/grid")
    report = f.filter_pages(pages)
    assert report["removed"][0]["reason"] == "non_html_json"


def test_main_writes_page_filter_json(tmp_path: Path):
    pages = tmp_path / "final"
    pages.mkdir()
    _write_page(
        pages,
        "final-0000",
        "<html><body>"
        + ("The cat and the dog are in the house with their toys and the ball. " * 8)
        + "</body></html>",
        "https://example.com/ok",
    )
    out = tmp_path / "page_filter.json"
    report = f.main(["--pages-dir", str(pages), "--out", str(out)])
    assert out.exists()
    assert report["n_kept"] == 1
