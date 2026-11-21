"""Offline tests for poc.final_collect and poc.final_domains."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import httpx

from poc.final_collect import (
    DOMAIN_DELAY_S,
    MAX_PAGES_PER_DOMAIN,
    MIN_VISIBLE_WORDS,
    SAMPLE_SEED,
    build_excluded,
    domain_for_url,
    is_excluded_domain,
    load_manifest,
    load_seed_pages,
    normalize_url,
    validate_fetched,
)
from poc.final_domains import load_inventory_excluded_domains
from poc.psl import load_psl


def test_protocol_constants():
    assert SAMPLE_SEED == 20261101
    assert MAX_PAGES_PER_DOMAIN == 3
    assert DOMAIN_DELAY_S >= 1.0
    assert MIN_VISIBLE_WORDS == 80


def test_normalize_url_keeps_query_drops_fragment():
    """Finding 5: keep query strings; drop only fragments."""
    assert normalize_url("https://WWW.Example.com/path/") == "https://example.com/path"
    assert normalize_url("https://example.com/path/#x") == "https://example.com/path"
    assert normalize_url("https://example.com/path?a=1&b=2#frag") == "https://example.com/path?a=1&b=2"
    assert normalize_url("https://example.com/path?q=1") == "https://example.com/path?q=1"


def test_load_seed_pages(tmp_path: Path):
    path = tmp_path / "seeds.json"
    path.write_text(
        json.dumps(
            {
                "pages": [
                    {"id": "a1", "url": "https://example.com/a", "page_type": "article"},
                    {"url": "https://example.com/b", "page_type": "forum"},
                ]
            }
        ),
        encoding="utf-8",
    )
    rows = load_seed_pages(path)
    assert len(rows) == 2
    assert rows[0]["id"] == "a1"
    assert rows[1]["page_type"] == "forum"


def test_inventory_applies_registrable_and_raw(tmp_path: Path):
    """Finding 4: registrable_domain on every inventory domain, plus raw form."""
    csv_path = tmp_path / "inv.csv"
    csv_path.write_text(
        "set,id,domain,url,use\n"
        "WCXB test,1,www.example.co.uk,,test\n"
        "WCXB test,2,sub.foo.test,https://deep.sub.foo.test/x,test\n"
        "other,3,ignored.com,https://ignored.com/,x\n",
        encoding="utf-8",
    )
    doms = load_inventory_excluded_domains(csv_path)
    assert "www.example.co.uk" in doms  # raw
    assert "example.co.uk" in doms  # registrable
    assert "sub.foo.test" in doms  # raw domain column
    assert "foo.test" in doms or "sub.foo.test" in doms
    assert "ignored.com" not in doms


def test_build_excluded_merges_inventory(tmp_path: Path):
    csv_path = tmp_path / "inv.csv"
    csv_path.write_text(
        "set,id,domain,url,use\nWCXB dev,1,foo.test,https://foo.test/,train\n",
        encoding="utf-8",
    )
    ex = build_excluded(csv_path, include_wcxb=False)
    assert "foo.test" in ex


def test_refuses_excluded_domain_in_seed_list(tmp_path: Path):
    csv_path = tmp_path / "inv.csv"
    csv_path.write_text(
        "set,id,domain,url,use\nWCXB test,1,bad.test,https://bad.test/,t\n",
        encoding="utf-8",
    )
    excluded = build_excluded(csv_path, include_wcxb=False)
    assert is_excluded_domain(domain_for_url("https://bad.test/page"), excluded)


def test_manifest_roundtrip(tmp_path: Path):
    manifest = tmp_path / "manifest.jsonl"
    row = {
        "id": "p1",
        "url": "https://example.com/",
        "domain": "example.com",
        "timestamp": "2026-11-01T00:00:00+00:00",
        "status": "ok",
        "sha256": "abc",
    }
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    loaded = load_manifest(manifest)
    assert loaded["p1"]["status"] == "ok"


def test_fetch_one_excluded_without_network(tmp_path: Path):
    from poc.final_collect import fetch_one

    excluded = frozenset({"example.com"})
    page = {"id": "x", "url": "https://example.com/", "page_type": "article"}

    with httpx.Client() as client:
        row = fetch_one(
            page,
            client=client,
            excluded=excluded,
            out_dir=tmp_path,
            robots_cache={},
            domain_locks={},
            domain_last={},
            domain_meta=threading.Lock(),
            psl=load_psl(),
        )
    assert row["status"] == "excluded_domain"
    assert not (tmp_path / "x.html").exists()


def test_fetch_one_applies_shared_english_word_rules(tmp_path: Path, monkeypatch):
    """Finding 6: collect uses shared validator (Content-Language + min words)."""
    from poc import final_collect as fc

    html = "<!DOCTYPE html><html><body>" + ("word " * 100) + "</body></html>"

    class FakeResp:
        status_code = 200
        url = "https://fresh.test/page"
        text = html
        headers = {"content-type": "text/html", "content-language": "en"}

    class FakeClient:
        def get(self, url, **kwargs):
            return FakeResp()

    monkeypatch.setattr(fc, "_robots_ok", lambda *a, **k: True)
    monkeypatch.setattr(fc, "_wait_domain", lambda *a, **k: None)

    row = fc.fetch_one(
        {"id": "p1", "url": "https://fresh.test/page", "page_type": "article"},
        client=FakeClient(),  # type: ignore[arg-type]
        excluded=frozenset(),
        out_dir=tmp_path,
        robots_cache={},
        domain_locks={},
        domain_last={},
        domain_meta=threading.Lock(),
        psl=load_psl(),
    )
    assert row["status"] == "ok"
    assert (tmp_path / "p1.html").exists()

    FakeResp.headers = {"content-type": "text/html", "content-language": "de"}
    FakeResp.text = "<!DOCTYPE html><html><body>" + ("word " * 100) + "</body></html>"
    row2 = fc.fetch_one(
        {"id": "p2", "url": "https://fresh.test/page2", "page_type": "article"},
        client=FakeClient(),  # type: ignore[arg-type]
        excluded=frozenset(),
        out_dir=tmp_path,
        robots_cache={},
        domain_locks={},
        domain_last={},
        domain_meta=threading.Lock(),
        psl=load_psl(),
    )
    assert row2["status"] == "not_english"


def test_shared_validator_same_module():
    """Finding 6: one shared validator path (final_collect.validate_fetched)."""
    from poc import final_collect as fc
    from poc import final_sample as fs

    assert fs.validate_fetched is fc.validate_fetched


def test_dry_run_cli(tmp_path: Path, monkeypatch):
    seeds = tmp_path / "seeds.json"
    seeds.write_text(
        json.dumps({"pages": [{"id": "ok", "url": "https://fresh.test/", "page_type": "article"}]}),
        encoding="utf-8",
    )
    inv = tmp_path / "inv.csv"
    inv.write_text("set,id,domain,url,use\n", encoding="utf-8")
    import sys

    from poc import final_collect as fc

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "final_collect",
            "--seeds",
            str(seeds),
            "--inventory-csv",
            str(inv),
            "--dry-run",
        ],
    )
    fc.main()


def test_validate_fetched_content_language():
    psl = load_psl()
    html = "<html><body>" + ("word " * 90) + "</body></html>"
    ok, _ = validate_fetched(
        url="https://a.test/",
        status=200,
        content_type="text/html",
        html=html,
        excluded=frozenset(),
        robots_ok=True,
        psl=psl,
        content_language="en",
    )
    assert ok
