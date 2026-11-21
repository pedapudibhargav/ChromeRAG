"""Offline tests for poc.final_run (synthetic pages only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from poc import final_run as fr


@pytest.fixture
def synthetic_pages(tmp_path: Path) -> Path:
    html = """<!DOCTYPE html><html><head><title>T</title></head>
    <body><main><p>Hello world content here for testing extraction.</p></main></body></html>"""
    (tmp_path / "syn1.html").write_text(html, encoding="utf-8")
    (tmp_path / "syn1.meta.json").write_text(
        json.dumps(
            {
                "url": "https://synthetic.test/page",
                "page_type": "article",
                "main_content": "Hello world content here for testing extraction.",
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_refuses_held_out_set(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(SystemExit, match="Refusing held-out"):
        fr.assert_set_allowed("wcxb_test", allow_held_out=False, ledger_path=ledger)


def test_refuses_new_pages_and_pages_dir(tmp_path: Path):
    """Finding 7: new_pages and data/final-style dirs are held-out."""
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(SystemExit, match="Refusing held-out"):
        fr.assert_set_allowed("new_pages", allow_held_out=False, ledger_path=ledger)
    final_dir = tmp_path / "data" / "final"
    final_dir.mkdir(parents=True)
    with pytest.raises(SystemExit, match="Refusing held-out"):
        fr.assert_set_allowed(
            "synthetic",
            allow_held_out=False,
            pages_dir=final_dir,
            ledger_path=ledger,
        )


def test_second_held_out_run_requires_resume(tmp_path: Path):
    """Finding 7: second scoring run refuses unless --resume-same-run matches."""
    ledger = tmp_path / "ledger.jsonl"
    run_id = fr.assert_set_allowed("new_pages", allow_held_out=True, ledger_path=ledger)
    assert run_id
    with pytest.raises(SystemExit, match="second scoring run"):
        fr.assert_set_allowed("new_pages", allow_held_out=True, ledger_path=ledger)
    with pytest.raises(SystemExit, match="does not match"):
        fr.assert_set_allowed(
            "new_pages",
            allow_held_out=True,
            resume_same_run="wrong-id",
            ledger_path=ledger,
        )
    assert (
        fr.assert_set_allowed(
            "new_pages",
            allow_held_out=False,
            resume_same_run=run_id,
            ledger_path=ledger,
        )
        == run_id
    )


def test_allows_synthetic_set(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    assert fr.assert_set_allowed("synthetic", allow_held_out=False, ledger_path=ledger) is None


def test_cache_key_includes_html_tool_version():
    """Finding 7: cache key includes html sha256, tool, tool version."""
    k1 = fr.cache_key(html="<p>a</p>", tool="trafilatura", version="1.0")
    k2 = fr.cache_key(html="<p>b</p>", tool="trafilatura", version="1.0")
    k3 = fr.cache_key(html="<p>a</p>", tool="readability", version="1.0")
    k4 = fr.cache_key(html="<p>a</p>", tool="trafilatura", version="2.0")
    assert len({k1, k2, k3, k4}) == 4


def test_error_rows_not_reused(tmp_path: Path, synthetic_pages: Path, monkeypatch):
    """Finding 7: cached error rows are not reused silently."""
    pages = fr.load_pages_from_dir(synthetic_pages)
    cache = tmp_path / "cache"
    tool = "trafilatura"
    version = fr.tool_version(tool)
    key = fr.cache_key(html=pages[0]["html"], tool=tool, version=version)
    cp = fr.cache_path(cache, tool, key)
    cp.parent.mkdir(parents=True)
    cp.write_text(
        json.dumps({"id": "syn1", "tool": tool, "error": "Boom", "text": "", "ms": 1, "sha256": "x"})
        + "\n",
        encoding="utf-8",
    )
    rows = fr.run_set(pages, tools=[tool], cache_root=cache, workers=1)
    assert len(rows) == 1
    assert "error" not in rows[0]
    assert rows[0]["chars"] > 0


def test_load_pages_from_dir(synthetic_pages: Path):
    pages = fr.load_pages_from_dir(synthetic_pages)
    assert len(pages) == 1
    assert pages[0]["id"] == "syn1"
    assert "Hello" in pages[0]["html"]


def test_run_set_caches(tmp_path: Path, synthetic_pages: Path, monkeypatch):
    monkeypatch.setattr(fr, "assert_chromerag_freeze", lambda: None)
    pages = fr.load_pages_from_dir(synthetic_pages)
    cache = tmp_path / "cache"
    tools = ["trafilatura", "readability"]
    rows = fr.run_set(pages, tools=tools, cache_root=cache, workers=1)
    assert len(rows) == 2
    rows2 = fr.run_set(pages, tools=tools, cache_root=cache, workers=1)
    assert rows2[0]["sha256"] == rows[0]["sha256"]
    assert (cache / "trafilatura").exists()


def test_summarize_includes_f1():
    rows = [{"tool": "trafilatura", "ms": 1.0, "f1": 0.5}, {"tool": "trafilatura", "ms": 3.0, "f1": 0.7}]
    summary = fr.summarize(rows)
    assert summary["trafilatura"]["mean_f1"] == pytest.approx(0.6)


def test_freeze_check_passes_at_repo_tag():
    errors = fr.freeze_check_errors()
    assert errors == []


def test_freeze_check_reports_missing_tag(monkeypatch):
    def fake_git(*args: str):
        if args[0] == "rev-parse":
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fr, "_git", fake_git)
    errors = fr.freeze_check_errors()
    assert any("missing git tag" in e for e in errors)


def test_recorded_dependency_versions():
    versions = fr.recorded_dependency_versions()
    assert versions["rs_trafilatura_ci_pin"] == fr.RS_TRAFILATURA_CI_VERSION
    assert "trafilatura" in versions


def test_main_synthetic(tmp_path: Path, synthetic_pages: Path, monkeypatch):
    monkeypatch.setattr(fr, "assert_chromerag_freeze", lambda: None)
    monkeypatch.setattr(fr, "HELD_OUT_LEDGER", tmp_path / "held.jsonl")
    out = tmp_path / "out.json"
    monkeypatch.setattr(
        __import__("sys"),
        "argv",
        [
            "final_run",
            "--set",
            "synthetic",
            "--pages-dir",
            str(synthetic_pages),
            "--tools",
            "trafilatura",
            "--out",
            str(out),
            "--cache",
            str(tmp_path / "cache"),
            "--skip-freeze-check",
            "--workers",
            "1",
        ],
    )
    fr.main()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["set"] == "synthetic"
    assert "trafilatura" in data["summary"]
