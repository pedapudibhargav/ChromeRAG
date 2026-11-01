"""Synthetic checks for reviewer fixes on rev1/p09b (no WCXB pages)."""

from __future__ import annotations

from pathlib import Path

from chromerag import ChromeRAG, PipelineConfig
from chromerag.markdown_out import consume_trim_notes as consume_md_notes
from chromerag.markdown_out import reset_trim_notes as reset_md_notes
from chromerag.tables import consume_trim_notes as consume_table_notes
from chromerag.tables import reset_trim_notes as reset_table_notes


def test_trim_notes_follow_winning_pass_not_rejected_retry(monkeypatch) -> None:
    """Carry notes from the pass finally used; rejected-retry notes must not win."""
    from chromerag.extractor import ChromeRAG as Extractor
    from chromerag.models import ExtractResult

    def fake_core(self, html, url, cfg, **kwargs):  # type: ignore[no-untyped-def]
        force = bool(kwargs.get("force_body_root"))
        if force:
            # Shorter than first on both words and tokens so the retry is rejected.
            md = "x\n"
            notes = ["rejected-retry-note"]
        else:
            # Collapsed vs body_words=500, but better than the retry.
            md = "first keep alpha beta\n"
            notes = ["first-pass-note"]
        result = ExtractResult(
            url=url,
            markdown=md,
            front_matter={},
            n_blocks_in=5,
            n_blocks_kept=1,
            n_tables=0,
            tokens_estimate=max(1, len(md) // 4),
            method="chromerag",
            warnings=[],
            input_quality={"is_thin": False, "warnings": []},
            diagnostics={},
        )
        meta = {
            "front": {},
            "input_quality": type("IQ", (), {"is_thin": False, "warnings": []})(),
            "body_words": 500,
            "trim_notes": notes,
        }
        return md, meta, result

    monkeypatch.setattr(Extractor, "_extract_core", fake_core)
    rag = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False))
    result = rag._extract_with_retries("<html></html>", None, rag.config)
    assert "first-pass-note" in result.warnings
    assert "rejected-retry-note" not in result.warnings


def test_trim_notes_context_isolated_across_resets() -> None:
    reset_table_notes()
    reset_md_notes()
    from chromerag import markdown_out as md_mod
    from chromerag import tables as tables_mod

    tables_mod._trim_notes().append("a")
    md_mod._trim_notes().append("b")
    assert consume_table_notes() == ["a"]
    assert consume_md_notes() == ["b"]
    assert consume_table_notes() == []
    assert consume_md_notes() == []


def test_fold_model_loader_raises_when_missing(tmp_path: Path, monkeypatch) -> None:
    import poc.run_strict_dev_cv as mod

    monkeypatch.setattr(mod, "_model_pattern", str(tmp_path / "fold_{fold}"))
    monkeypatch.setattr(mod, "_models", {})
    try:
        mod._model(0)
        raised = False
    except SystemExit as exc:
        raised = True
        assert "refusing the shipped model" in str(exc)
    assert raised


def test_empty_output_fold_model_raises_when_missing(tmp_path: Path, monkeypatch) -> None:
    import poc.empty_output_eval as mod

    monkeypatch.setattr(mod, "_model_pattern", str(tmp_path / "fold_{fold}"))
    monkeypatch.setattr(mod, "_models", {})
    try:
        mod._fold_model(1)
        raised = False
    except SystemExit as exc:
        raised = True
        assert "refusing the shipped model" in str(exc)
    assert raised


def test_site_bootstrap_is_page_weighted() -> None:
    from poc.empty_output_eval import site_bootstrap

    # Equal-site mean would be 0; page-weighted mean is 0.6.
    deltas = {"big": [1.0, 1.0, 1.0, 1.0], "small": [-1.0]}
    mean, lo, hi = site_bootstrap(deltas, iters=200)
    assert mean == 0.6
    assert lo <= mean <= hi


def test_half_uses_cv_site_of_not_hostname_only() -> None:
    import inspect

    from poc import lbc_data, learn_tokens, wcxb_diag
    from poc.learn_tokens import cv_site_of, half, site_of

    url = "https://docs.shop.example.com/a"
    assert site_of(url) == "docs.shop.example.com"
    assert cv_site_of(url) == "example.com"
    assert half(cv_site_of(url)) in {"learn", "valid"}
    assert "cv_site_of" in inspect.getsource(lbc_data._one)
    assert "cv_site_of" in inspect.getsource(learn_tokens.scan)
    assert "cv_site_of" in inspect.getsource(wcxb_diag.run)


def test_rebuild_strict_copies_assets_and_documents_test_url_use() -> None:
    script = Path("poc/rebuild_strict.sh").read_text(encoding="utf-8")
    assert "src/chromerag/assets/lbc_stage1.npz" in script
    assert "cp -f data/outputs/lbc/verify_a/lbc_stage1.npz" in script
    assert "exclude" in script.lower()
    assert "test URL" in script or "test URLs" in script


def test_strict_dev_cv_tool_row_omits_ms() -> None:
    from poc.run_strict_dev_cv import _tool_row

    row = _tool_row("hello world", "hello world", {"with_snippets": [], "without_snippets": []})
    assert "ms" not in row


def test_extract_does_not_raise_on_ordinary_page() -> None:
    html = (
        "<html><body><main><h1>Topic</h1><p>"
        + ("Body text for extraction thresholds. " * 20)
        + "</p></main></body></html>"
    )
    result = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html)
    assert "Body text" in result.markdown
